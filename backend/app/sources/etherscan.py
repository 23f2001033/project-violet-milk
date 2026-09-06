"""
EtherscanSource — live Ethereum mainnet.  Owner: BE1

Implements the same DataSource contract as SyntheticSource, so the graph, risk,
dilution, timeline and report engines are untouched by which one is active.
That is what lets a judge hand over a real address mid-demo.

THE DETAIL THAT DECIDES WHETHER THIS WORKS: Indian crypto-fraud proceeds move
as USDT, not native ETH. Querying only `txlist` returns almost nothing on a
real scam wallet and live mode looks broken. Both `txlist` and `tokentx` are
fetched and merged, and ERC-20 values are scaled by the token's own decimals -
USDT has 6, not 18, so skipping that step reports a 5,200 USDT transfer as
5.2 billion.

Every response is written to `data/live_cache/`. On a rate limit, a timeout or
a dead network the cache is replayed, so a pre-tested address still traces with
the wifi unplugged.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import httpx

from .. import config
from ..models import (
    Asset, Chain, Confidence, Edge, EvidenceType, Label, LabelSource, Node,
    NodeType,
)
from .base import DataSource

log = logging.getLogger(__name__)

CACHE_DIR = config.LIVE_CACHE_DIR
LABELS_PATH = config.DATA_DIR / "known_addresses.json"

# Etherscan's free tier is rate limited per second. Serialising every call
# behind a fixed sleep made a depth-2 trace take ~28s - far too slow to hold a
# room. Instead: a shared connection pool (no TLS handshake per request) and a
# token bucket that permits controlled concurrency while staying under the
# limit. Same number of calls, a fraction of the wall clock.
_RATE_PER_SECOND = 3
_MAX_WORKERS = 3
_MAX_RETRIES = 2

_bucket_lock = threading.Lock()
_call_times: deque[float] = deque(maxlen=_RATE_PER_SECOND)

_client = httpx.Client(
    timeout=20,
    limits=httpx.Limits(max_connections=_MAX_WORKERS,
                        max_keepalive_connections=_MAX_WORKERS),
)


def _throttle() -> None:
    """Block until another call is allowed under the per-second budget."""
    while True:
        with _bucket_lock:
            now = time.monotonic()
            if len(_call_times) < _RATE_PER_SECOND or now - _call_times[0] >= 1.0:
                _call_times.append(now)
                return
            wait = 1.0 - (now - _call_times[0])
        time.sleep(max(wait, 0.01))


# --------------------------------------------------------- circuit breaker
#
# Retrying is right for a transient throttle and catastrophically wrong for a
# dead network: with retries and backoff on every call, a depth-2 trace on an
# unreachable host took 62 SECONDS to fall through to cache. Correct results,
# but a demo that appears frozen for a minute is a demo that has failed.
#
# So: count consecutive connection failures, and once the network is clearly
# down, stop calling it for a cool-off period and serve cache immediately. The
# breaker resets on the first success, so a flaky venue wifi recovers on its own.
_FAILURE_THRESHOLD = 3
_COOLOFF_SECONDS = 30.0

_breaker_lock = threading.Lock()
_consecutive_failures = 0
_open_until = 0.0


def _circuit_open() -> bool:
    with _breaker_lock:
        return time.monotonic() < _open_until


def _record_failure() -> None:
    global _consecutive_failures, _open_until
    with _breaker_lock:
        _consecutive_failures += 1
        if _consecutive_failures >= _FAILURE_THRESHOLD:
            _open_until = time.monotonic() + _COOLOFF_SECONDS
            log.warning(
                "Etherscan unreachable after %d attempts; serving from cache "
                "for %.0fs", _consecutive_failures, _COOLOFF_SECONDS)


def _record_success() -> None:
    global _consecutive_failures, _open_until
    with _breaker_lock:
        _consecutive_failures = 0
        _open_until = 0.0


def reset_breaker() -> None:
    """Test hook, and a manual override if the network comes back mid-demo."""
    _record_success()


def _load_labels() -> dict[str, dict[str, Any]]:
    if not LABELS_PATH.exists():
        return {}
    try:
        return json.loads(LABELS_PATH.read_text(encoding="utf-8")).get("labels", {})
    except json.JSONDecodeError:
        log.warning("known_addresses.json is malformed; continuing unlabelled")
        return {}


LABELS = _load_labels()


def _iso(unix_ts: str) -> str:
    return datetime.fromtimestamp(int(unix_ts), tz=timezone.utc).isoformat()


class EtherscanSource(DataSource):
    def __init__(self, case_id: str, chain_id: int | None = None):
        self.case_id = case_id
        self.chain_id = chain_id or config.ETHERSCAN_CHAIN_ID
        self.used_cache = False

    # ------------------------------------------------------------- plumbing

    def _cache_file(self, action: str, address: str):
        return CACHE_DIR / f"{self.chain_id}_{action}_{address.lower()}.json"

    def _fetch(self, action: str, address: str, offset: int = 100) -> list[dict]:
        """One Etherscan call: retry on throttle, fall back to cache only when
        the network genuinely cannot answer.

        A rate limit is TRANSIENT. Treating it as a hard failure and dropping
        straight to cache silently returned empty results for exactly the
        `tokentx` calls that carry the USDT movement - live mode appeared to
        work while showing no token transfers at all. Back off and retry first.
        """
        cache = self._cache_file(action, address)

        if not config.ETHERSCAN_CONFIGURED or _circuit_open():
            self.used_cache = True
            return self._read_cache(cache)

        # Stage mode: replay a pre-tested address rather than gamble on venue
        # wifi. Only ever serves a file that is actually there - an address
        # nobody pre-tested still goes to the network.
        if config.LIVE_CACHE_FIRST and cache.exists():
            self.used_cache = True
            return self._read_cache(cache)

        params = {
            "chainid": self.chain_id, "module": "account", "action": action,
            "address": address, "page": 1, "offset": offset, "sort": "desc",
            "apikey": config.ETHERSCAN_API_KEY,
        }

        for attempt in range(_MAX_RETRIES + 1):
            try:
                _throttle()
                r = _client.get(config.ETHERSCAN_BASE_URL, params=params)
                r.raise_for_status()
                result = r.json().get("result")

                _record_success()
                if isinstance(result, list):
                    CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    cache.write_text(json.dumps(result), encoding="utf-8")
                    return result

                # status 0 with a string result: either "No transactions found"
                # (benign, genuinely empty) or a rate limit (retryable).
                if "rate limit" in str(result).lower():
                    if attempt < _MAX_RETRIES:
                        time.sleep(1.1 * (attempt + 1))
                        continue
                    log.warning("Etherscan still throttled for %s; using cache",
                                address)
                    self.used_cache = True
                    return self._read_cache(cache)
                return []

            except Exception as exc:  # noqa: BLE001 - degrade, never raise
                _record_failure()
                # Once the breaker trips, stop burning wall-clock on a network
                # that is not answering - go straight to cache.
                if attempt < _MAX_RETRIES and not _circuit_open():
                    time.sleep(0.4 * (attempt + 1))
                    continue
                log.warning("Etherscan %s failed (%s); serving from cache",
                            action, exc.__class__.__name__)
                self.used_cache = True
                return self._read_cache(cache)

        return self._read_cache(cache)

    @staticmethod
    def _read_cache(path) -> list[dict]:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return []
        return []

    # ------------------------------------------------------------ interface

    def get_transactions(self, address: str, limit: int = 100) -> list[Edge]:
        native = self._fetch("txlist", address, offset=limit)
        tokens = self._fetch("tokentx", address, offset=limit)
        return self._to_edges(native, tokens)

    def get_balance(self, address: str) -> float:
        # Balances are not used for live dilution: a current balance is not the
        # balance held at the time funds arrived, and pretending otherwise
        # would produce confidently wrong ratios.
        return 0.0

    def get_label(self, address: str) -> Label | None:
        entry = LABELS.get(address.lower())
        if not entry:
            return None
        return Label(
            address=address,
            label=entry["label"],
            node_type=NodeType(entry.get("node_type", "unknown")),
            source=LabelSource.CURATED,
            confidence=Confidence(entry.get("confidence", "inferred")),
            reference=entry.get("source"),
        )

    def source_name(self) -> str:
        return "EtherscanSource" + (" (cached)" if self.used_cache else "")

    def is_live(self) -> bool:
        return True

    # ----------------------------------------------------------- conversion

    def _to_edges(self, native: list[dict], tokens: list[dict]) -> list[Edge]:
        edges: list[Edge] = []

        for tx in native:
            try:
                value = int(tx["value"]) / 1e18
            except (KeyError, ValueError):
                continue
            if value <= 0:            # contract calls carrying no value
                continue
            edges.append(Edge(
                edge_id=tx["hash"], case_id=self.case_id,
                from_node=tx["from"].lower(), to_node=(tx.get("to") or "").lower(),
                amount=round(value, 8), asset=Asset.ETH,
                timestamp=_iso(tx["timeStamp"]),
                evidence_type=EvidenceType.CONFIRMED_ONCHAIN,
                tx_hash=tx["hash"], block_number=int(tx["blockNumber"]),
            ))

        for tx in tokens:
            try:
                # USDT is 6 decimals, not 18. Assuming 18 turns 5,200 USDT into
                # 0.0000000000052 - or, inverted, a rounding error into billions.
                decimals = int(tx.get("tokenDecimal") or 18)
                value = int(tx["value"]) / (10 ** decimals)
            except (KeyError, ValueError, TypeError):
                continue
            if value <= 0:
                continue
            symbol = (tx.get("tokenSymbol") or "").upper()
            asset = Asset.USDT if symbol in {"USDT", "USDC", "DAI"} else Asset.ETH
            edges.append(Edge(
                edge_id=f"{tx['hash']}:{tx.get('logIndex', '0')}",
                case_id=self.case_id,
                from_node=tx["from"].lower(), to_node=(tx.get("to") or "").lower(),
                amount=round(value, 6), asset=asset,
                timestamp=_iso(tx["timeStamp"]),
                evidence_type=EvidenceType.CONFIRMED_ONCHAIN,
                tx_hash=tx["hash"], block_number=int(tx["blockNumber"]),
            ))

        edges = [e for e in edges if e.from_node and e.to_node]
        edges.sort(key=lambda e: e.timestamp)
        return edges

    def _node_for(self, address: str, is_seed: bool = False) -> Node:
        lbl = self.get_label(address)
        return Node(
            node_id=address, case_id=self.case_id,
            node_type=lbl.node_type if lbl else NodeType.UNKNOWN,
            label=lbl.label if lbl else None,
            label_source=LabelSource.CURATED if lbl else LabelSource.NONE,
            # No label means UNKNOWN, never "clean". Rendering an unlabelled
            # address as safe would be the single most misleading thing this
            # tool could do.
            label_confidence=lbl.confidence if lbl else Confidence.UNKNOWN,
            chain=Chain.ETHEREUM, balance=None, prior_balance=0.0,
            is_seed=is_seed,
        )

    # ----------------------------------------------------------- expansion

    def expand(
        self, seed: str, max_depth: int = 2, max_edges_per_node: int = 20
    ) -> tuple[list[Node], list[Edge]]:
        """Breadth-first expansion, one API round per address.

        Depth is capped hard: a real wallet at depth 3 fans out to thousands of
        addresses, and each one costs two API calls. The engines apply their own
        bounds afterwards; this limit is about not exhausting the rate limit
        before the trace finishes.
        """
        seed = seed.lower()
        depth_cap = min(max_depth, 2)

        seen: dict[str, int] = {seed: 0}
        frontier = [seed]
        all_edges: dict[str, Edge] = {}

        for depth in range(depth_cap):
            nxt: list[str] = []
            # One address = two API calls. Fetching a whole level in parallel
            # (under the token bucket) is what brings a depth-2 trace from
            # ~28s down to something that holds a room's attention.
            with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
                results = list(pool.map(
                    lambda a: (a, self.get_transactions(
                        a, limit=max_edges_per_node * 3)),
                    frontier,
                ))
            for addr, txs in results:
                for e in txs:
                    all_edges[e.edge_id] = e
                    other = e.to_node if e.from_node == addr else e.from_node
                    if other and other not in seen:
                        seen[other] = depth + 1
                        nxt.append(other)
            # Expand only the largest counterparties at the next level.
            by_volume = sorted(
                nxt,
                key=lambda a: sum(x.amount for x in all_edges.values()
                                  if a in (x.from_node, x.to_node)),
                reverse=True,
            )
            frontier = by_volume[:max_edges_per_node]

        nodes = [self._node_for(a, is_seed=(a == seed)) for a in seen]
        edges = [e for e in all_edges.values()
                 if e.from_node in seen and e.to_node in seen]
        edges.sort(key=lambda e: e.timestamp)
        return nodes, edges
