"""
Phase 6 acceptance gate - live mainnet mode.

These tests run OFFLINE. They exercise the conversion, ranking, labelling and
degradation logic with fixture payloads shaped exactly like Etherscan's, so the
whole team can run the suite without spending API quota or needing a network.
"""

import json

from backend.app import config
from backend.app.engines.graph_engine import _rank_incident, bounded_trace
from backend.app.models import (
    Asset, Chain, Confidence, Edge, EvidenceType, Node, NodeType,
)
from backend.app.sources.etherscan import EtherscanSource

CASE = "LIVE-TEST"
SEED = "0x28c6c06298d514db089934071355e5743bf21d60"   # publicly-labelled
MIXER = "0x12d66f87a04a9e220743712ce6d9bb1b5616b8fc"  # OFAC-designated
UNKNOWN = "0x1111111111111111111111111111111111111111"


def _edge(eid, frm, to, amount, asset, ts="2026-09-01T10:00:00+00:00"):
    return Edge(edge_id=eid, case_id=CASE, from_node=frm, to_node=to,
                amount=amount, asset=asset, timestamp=ts,
                evidence_type=EvidenceType.CONFIRMED_ONCHAIN,
                tx_hash="0x" + "a" * 64)


def _node(nid, seed=False):
    return Node(node_id=nid, case_id=CASE, node_type=NodeType.UNKNOWN,
                chain=Chain.ETHEREUM, is_seed=seed)


# ------------------------------------------------------- ERC-20 decimals

def test_usdt_is_scaled_by_its_own_decimals():
    """USDT has 6 decimals, not 18. Assuming 18 turns a 5,200 USDT transfer
    into 0.0000000000052 - and inverted, a rounding error into billions. This
    is the single most consequential unit bug in live mode."""
    src = EtherscanSource(CASE)
    tokentx = [{
        "hash": "0x" + "b" * 64, "logIndex": "1",
        "from": SEED, "to": UNKNOWN,
        "value": "5200000000",          # 5,200 USDT at 6 decimals
        "tokenDecimal": "6", "tokenSymbol": "USDT",
        "timeStamp": "1788000000", "blockNumber": "19204512",
    }]
    edges = src._to_edges([], tokentx)
    assert len(edges) == 1
    assert edges[0].amount == 5200.0
    assert edges[0].asset == Asset.USDT


def test_eighteen_decimal_token_also_scales():
    src = EtherscanSource(CASE)
    tokentx = [{
        "hash": "0x" + "c" * 64, "logIndex": "0",
        "from": SEED, "to": UNKNOWN,
        "value": "2" + "0" * 18,        # 2.0 at 18 decimals
        "tokenDecimal": "18", "tokenSymbol": "DAI",
        "timeStamp": "1788000000", "blockNumber": "19204513",
    }]
    assert src._to_edges([], tokentx)[0].amount == 2.0


def test_native_eth_uses_wei():
    src = EtherscanSource(CASE)
    txlist = [{
        "hash": "0x" + "d" * 64, "from": SEED, "to": UNKNOWN,
        "value": "1" + "0" * 18, "timeStamp": "1788000000",
        "blockNumber": "19204514",
    }]
    edges = src._to_edges(txlist, [])
    assert edges[0].amount == 1.0
    assert edges[0].asset == Asset.ETH


def test_zero_value_contract_calls_are_dropped():
    src = EtherscanSource(CASE)
    txlist = [{"hash": "0x" + "e" * 64, "from": SEED, "to": UNKNOWN,
               "value": "0", "timeStamp": "1788000000", "blockNumber": "1"}]
    assert src._to_edges(txlist, []) == []


def test_both_endpoints_are_merged():
    """Querying only txlist returns almost nothing on a real scam wallet,
    because the proceeds move as USDT."""
    src = EtherscanSource(CASE)
    txlist = [{"hash": "0x" + "1" * 64, "from": SEED, "to": UNKNOWN,
               "value": "1" + "0" * 18, "timeStamp": "1788000000",
               "blockNumber": "1"}]
    tokentx = [{"hash": "0x" + "2" * 64, "logIndex": "0", "from": SEED,
                "to": UNKNOWN, "value": "1000000", "tokenDecimal": "6",
                "tokenSymbol": "USDT", "timeStamp": "1788000001",
                "blockNumber": "2"}]
    assets = {e.asset for e in src._to_edges(txlist, tokentx)}
    assert assets == {Asset.ETH, Asset.USDT}


# --------------------------------------------------- cross-asset ranking

def test_minority_asset_survives_the_per_node_cap():
    """Regression: ranking incident edges by raw `amount` across mixed assets
    is meaningless - 1,000 ETH and 47 USDT are quantities of different things.
    Large native-ETH figures starved USDT out of live traces entirely, losing
    exactly the evidence that matters for Indian fraud cases."""
    edges = ([_edge(f"eth{i}", SEED, f"0x{i:040x}", 1000.0 + i, Asset.ETH)
              for i in range(20)]
             + [_edge(f"usdt{i}", SEED, f"0x{i + 100:040x}", 47.0 + i, Asset.USDT)
                for i in range(5)])
    kept = _rank_incident(edges, 8)
    assert len(kept) == 8
    assert any(e.asset == Asset.USDT for e in kept), \
        "the smaller-denominated asset must not be starved out"
    assert any(e.asset == Asset.ETH for e in kept)


def test_ranking_is_a_noop_below_the_cap():
    edges = [_edge("a", SEED, UNKNOWN, 1.0, Asset.ETH)]
    assert _rank_incident(edges, 8) == edges


def test_single_asset_ranking_keeps_the_largest():
    edges = [_edge(f"e{i}", SEED, f"0x{i:040x}", float(i), Asset.ETH)
             for i in range(10)]
    kept = _rank_incident(edges, 3)
    assert len(kept) == 3
    assert min(e.amount for e in kept) >= 7.0


def test_bounded_trace_preserves_both_assets():
    nodes = [_node(SEED, seed=True)] + [_node(f"0x{i:040x}") for i in range(25)]
    edges = ([_edge(f"eth{i}", SEED, f"0x{i:040x}", 900.0 + i, Asset.ETH)
              for i in range(20)]
             + [_edge(f"usdt{i}", SEED, f"0x{i + 20:040x}", 10.0, Asset.USDT)
                for i in range(5)])
    _, kept, _, truncated = bounded_trace(
        nodes, edges, SEED, max_depth=1, max_edges_per_node=8)
    assert truncated is True
    assert {e.asset for e in kept} == {Asset.ETH, Asset.USDT}


# ------------------------------------------------------------- labelling

def test_curated_label_resolves_with_provenance():
    lbl = EtherscanSource(CASE).get_label(MIXER)
    assert lbl is not None
    assert lbl.node_type == NodeType.MIXER
    assert lbl.confidence == Confidence.CONFIRMED
    assert lbl.reference, "a label without a source is not usable in a dossier"


def test_unlabelled_address_is_unknown_not_clean():
    """Rendering an unlabelled address as safe would be the most misleading
    thing this tool could do. Absence of a label means UNKNOWN."""
    src = EtherscanSource(CASE)
    assert src.get_label(UNKNOWN) is None
    node = src._node_for(UNKNOWN)
    assert node.label_confidence == Confidence.UNKNOWN
    assert node.node_type == NodeType.UNKNOWN
    assert node.label is None


def test_every_curated_label_declares_a_source():
    blob = json.loads(
        (config.DATA_DIR / "known_addresses.json").read_text(encoding="utf-8"))
    assert blob["labels"], "the curated list must not be empty"
    for addr, entry in blob["labels"].items():
        if addr.startswith("0x"):
            # Ethereum hex is case-insensitive, so it is normalised to lower.
            assert addr == addr.lower(), f"{addr} must be lowercase for lookup"
        else:
            # Tron Base58 is case-SENSITIVE. Lowercasing it makes every
            # curated Tron label silently miss.
            assert addr != addr.lower(),                 f"{addr} looks like Tron and must keep its casing"
        assert entry.get("source"), f"{addr} has a label with no provenance"
        assert "verified_by_team" in entry, f"{addr} missing verification flag"


# ----------------------------------------------------------- degradation

def test_source_identifies_itself_as_live():
    src = EtherscanSource(CASE)
    assert src.is_live() is True
    assert src.source_name().startswith("EtherscanSource")


def test_missing_key_degrades_to_cache_without_raising(monkeypatch, tmp_path):
    """With no key and a cold cache the source must return empty, not explode.
    A live trace failing is acceptable; the app crashing on stage is not."""
    monkeypatch.setattr(config, "ETHERSCAN_CONFIGURED", False)
    monkeypatch.setattr("backend.app.sources.etherscan.CACHE_DIR", tmp_path)
    src = EtherscanSource(CASE)
    assert src.get_transactions(SEED) == []
    assert src.used_cache is True
    assert "cached" in src.source_name()


# ------------------------------------------------------- circuit breaker

def test_breaker_short_circuits_a_dead_network(monkeypatch, tmp_path):
    """Regression: retry-with-backoff on every call meant an unreachable host
    took 62 SECONDS to fall through to cache. Results were correct but the UI
    appeared frozen for a minute - a failed demo. After a few consecutive
    connection failures the breaker opens and cache is served immediately.
    """
    import time as _time

    import httpx

    import backend.app.sources.etherscan as ES

    ES.reset_breaker()
    monkeypatch.setattr(config, "ETHERSCAN_CONFIGURED", True)
    monkeypatch.setattr(config, "ETHERSCAN_BASE_URL", "http://127.0.0.1:9/api")
    monkeypatch.setattr(ES, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(ES, "_client", httpx.Client(timeout=1))

    src = ES.EtherscanSource(CASE)
    for _ in range(ES._FAILURE_THRESHOLD):
        src._fetch("txlist", SEED)

    assert ES._circuit_open(), "breaker must open once the network is clearly down"

    t0 = _time.time()
    for i in range(10):
        src._fetch("txlist", f"0x{i:040x}")
    elapsed = _time.time() - t0
    assert elapsed < 1.0, (
        f"10 calls took {elapsed:.1f}s with the breaker open - it is not "
        "short-circuiting"
    )
    ES.reset_breaker()


def test_breaker_resets_after_a_success():
    import backend.app.sources.etherscan as ES
    ES.reset_breaker()
    ES._record_failure()
    ES._record_failure()
    ES._record_success()
    assert ES._consecutive_failures == 0
    assert not ES._circuit_open()
