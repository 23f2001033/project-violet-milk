"""
TronSource - live Tron mainnet (TRC-20).  Owner: BE1

WHY TRON MATTERS MORE THAN ETHEREUM HERE
The dominant rail for Indian crypto-fraud proceeds is USDT on Tron, not on
Ethereum. A TRC-20 transfer costs cents; the same movement on Ethereum costs
far more, so the money goes where the fees are low. A tool that traces only
Ethereum will miss most of what an Indian investigator is actually chasing.

Implements the same DataSource contract as the other two sources, so the
graph, risk, dilution, timeline, report and anchoring engines are untouched.
That was the point of the interface.

FOUR THINGS TRON DOES DIFFERENTLY, each of which silently corrupts data if
missed:
  1. Addresses are Base58Check beginning with "T" (34 chars), not 0x-hex.
  2. Timestamps arrive in MILLISECONDS. Treating them as seconds dates every
     transaction to 1970.
  3. Token amounts scale by `token_info.decimals` - USDT is 6 on Tron, as on
     Ethereum. Assuming 18 understates a transfer by a factor of a trillion.
  4. Native TRX amounts are in "sun": 1 TRX = 1_000_000 sun, and the transfer
     fields sit inside raw_data.contract[0].parameter.value.

TronGrid needs no API key for read access. A key raises the rate limit and is
used when TRONGRID_API_KEY is set.
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

SUN_PER_TRX = 1_000_000

# VERIFIED BY CONTRACT ADDRESS, NEVER BY TICKER.
#
# Anyone can deploy a TRC-20 contract whose symbol is "USDT". Live traffic on
# a real address shows exactly that - alongside genuine USDT sit lookalikes
# such as "USDTT" at different contracts. A scammer can mint a fake USDT and
# send it to a victim to distort any tool that trusts the symbol, and that is
# a known poisoning technique, not a hypothetical.
#
# So a transfer is only reported as USDT when its CONTRACT matches below.
# Everything else is reported as an unverified TOKEN.
VERIFIED_TOKENS = {
    "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t": "USDT",   # Tether USD (TRC-20)
    "TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8": "USDC",   # Circle USD Coin
    "TPYmHEhy5n8TCEfYGqW2rPxsghSfzghPDn": "USDD",   # Decentralized USD
}

_RATE_PER_SECOND = 5
_MAX_WORKERS = 4

_bucket_lock = threading.Lock()
_call_times: deque[float] = deque(maxlen=_RATE_PER_SECOND)

_client = httpx.Client(
    timeout=25,
    limits=httpx.Limits(max_connections=_MAX_WORKERS,
                        max_keepalive_connections=_MAX_WORKERS),
)


def _throttle() -> None:
    """Stay inside TronGrid's per-second budget while running concurrently."""
    while True:
        with _bucket_lock:
            now = time.monotonic()
            if len(_call_times) < _RATE_PER_SECOND or now - _call_times[0] >= 1.0:
                _call_times.append(now)
                return
            wait = 1.0 - (now - _call_times[0])
        time.sleep(max(wait, 0.01))


def is_tron_address(value: str) -> bool:
    """Base58Check addresses start with T and are 34 characters.

    Used to route a pasted address to the right chain, so an investigator
    never has to know or declare which network they are looking at.
    """
    v = (value or "").strip()
    return len(v) == 34 and v.startswith("T") and v.isalnum()


def _iso_from_ms(ms: Any) -> str:
    """Tron reports milliseconds. Reading them as seconds dates everything
    to 1970 and destroys every timeline delta in the case."""
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()


def _load_labels() -> dict[str, dict[str, Any]]:
    if not LABELS_PATH.exists():
        return {}
    try:
        return json.loads(LABELS_PATH.read_text(encoding="utf-8")).get("labels", {})
    except json.JSONDecodeError:
        return {}


LABELS = _load_labels()


class TronSource(DataSource):
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.used_cache = False

    # ------------------------------------------------------------- plumbing

    def _cache_file(self, kind: str, address: str):
        return CACHE_DIR / f"tron_{kind}_{address}.json"

    def _fetch(self, kind: str, address: str, limit: int = 50) -> list[dict]:
        """One TronGrid call, cached on success and replayed on failure."""
        cache = self._cache_file(kind, address)
        path = (f"/v1/accounts/{address}/transactions/trc20"
                if kind == "trc20" else f"/v1/accounts/{address}/transactions")

        headers = {}
        if config.TRONGRID_API_KEY:
            headers["TRON-PRO-API-KEY"] = config.TRONGRID_API_KEY

        for attempt in range(3):
            try:
                _throttle()
                r = _client.get(
                    f"{config.TRONGRID_BASE_URL.rstrip('/')}{path}",
                    params={"limit": min(limit, 200), "only_confirmed": "true"},
                    headers=headers,
                )
                if r.status_code == 429:
                    time.sleep(1.2 * (attempt + 1))
                    continue
                r.raise_for_status()
                body = r.json()
                data = body.get("data")
                if not isinstance(data, list):
                    return []
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps(data), encoding="utf-8")
                return data
            except Exception as exc:  # noqa: BLE001 - degrade, never raise
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                log.warning("TronGrid %s failed (%s); serving from cache",
                            kind, exc.__class__.__name__)
                self.used_cache = True
                if cache.exists():
                    try:
                        return json.loads(cache.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        return []
                return []
        return []

    # ------------------------------------------------------------ interface

    def get_transactions(self, address: str, limit: int = 100) -> list[Edge]:
        trc20 = self._fetch("trc20", address, limit)
        native = self._fetch("native", address, limit)
        return self._to_edges(trc20, native)

    def get_balance(self, address: str) -> float:
        # As on Ethereum: a current balance is not the balance held when funds
        # arrived, so it is deliberately not fed into the dilution denominator.
        return 0.0

    def get_label(self, address: str) -> Label | None:
        entry = LABELS.get(address) or LABELS.get(address.lower())
        if not entry:
            return None
        return Label(
            address=address, label=entry["label"],
            node_type=NodeType(entry.get("node_type", "unknown")),
            source=LabelSource.CURATED,
            confidence=Confidence(entry.get("confidence", "inferred")),
            reference=entry.get("source"),
        )

    def source_name(self) -> str:
        return "TronSource" + (" (cached)" if self.used_cache else "")

    def is_live(self) -> bool:
        return True

    # ----------------------------------------------------------- conversion

    def _to_edges(self, trc20: list[dict], native: list[dict]) -> list[Edge]:
        edges: list[Edge] = []

        for tx in trc20:
            try:
                info = tx.get("token_info") or {}
                decimals = int(info.get("decimals", 6))
                value = int(tx["value"]) / (10 ** decimals)
                if value <= 0:
                    continue
                # Contract, not ticker. A symbol reading "USDT" from an
                # unrecognised contract is reported as an unverified token.
                verified = VERIFIED_TOKENS.get(info.get("address", ""))
                edges.append(Edge(
                    edge_id=f"{tx['transaction_id']}:trc20",
                    case_id=self.case_id,
                    from_node=tx["from"], to_node=tx["to"],
                    amount=round(value, 6),
                    asset=Asset.USDT if verified else Asset.TOKEN,
                    timestamp=_iso_from_ms(tx["block_timestamp"]),
                    evidence_type=EvidenceType.CONFIRMED_ONCHAIN,
                    tx_hash=tx["transaction_id"],
                ))
            except (KeyError, ValueError, TypeError, ZeroDivisionError):
                continue

        for tx in native:
            try:
                contract = (tx.get("raw_data") or {}).get("contract") or []
                if not contract:
                    continue
                c = contract[0]
                if c.get("type") != "TransferContract":
                    continue          # not a value transfer
                v = (c.get("parameter") or {}).get("value") or {}
                amount = int(v.get("amount", 0)) / SUN_PER_TRX
                if amount <= 0:
                    continue
                edges.append(Edge(
                    edge_id=f"{tx['txID']}:trx",
                    case_id=self.case_id,
                    from_node=v.get("owner_address", ""),
                    to_node=v.get("to_address", ""),
                    amount=round(amount, 6), asset=Asset.TRX,
                    timestamp=_iso_from_ms(tx["raw_data"]["timestamp"]),
                    evidence_type=EvidenceType.CONFIRMED_ONCHAIN,
                    tx_hash=tx["txID"],
                ))
            except (KeyError, ValueError, TypeError):
                continue

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
            # No label means UNKNOWN, never "clean".
            label_confidence=lbl.confidence if lbl else Confidence.UNKNOWN,
            chain=Chain.TRON, balance=None, prior_balance=0.0, is_seed=is_seed,
        )

    # ----------------------------------------------------------- expansion

    def expand(
        self, seed: str, max_depth: int = 2, max_edges_per_node: int = 20
    ) -> tuple[list[Node], list[Edge]]:
        """Breadth-first expansion, bounded the same way as Ethereum.

        A busy Tron address fans out fast and TronGrid rate-limits, so depth is
        capped at 2 and only the highest-volume counterparties are expanded.
        """
        seed = seed.strip()
        depth_cap = min(max_depth, 2)

        seen: dict[str, int] = {seed: 0}
        frontier = [seed]
        all_edges: dict[str, Edge] = {}

        for depth in range(depth_cap):
            nxt: list[str] = []
            # Two calls per address. Fetching a level concurrently, under the
            # token bucket, is what keeps a depth-2 Tron trace demo-speed.
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
