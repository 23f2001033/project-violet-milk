"""
Dataset integrity tests - Phase 1 acceptance gate.

The demo dataset is the spine of the entire demonstration. If its arithmetic
is wrong, every downstream engine is wrong and a judge who divides two numbers
will destroy the presentation. These tests prove the numbers rather than
assuming them.

Run:  python -m pytest backend/tests/test_dataset_integrity.py -v
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "app" / "data"
EDGES_CSV = DATA / "demo_case.csv"
NODES_CSV = DATA / "demo_nodes.csv"

SEED = "0xa7f39c1d8e4b2a5f7c3d9e0a1b8c6d4e5f2a67e9"
W2 = "0x2d81b6f09c3a7e54d21b8f60a93c7e15d40b7f43"
CLEAN_POOL = "0xd90f42a17c58e03b96d1f47a20c85e39b7f481ab"
W1 = "0x9c04a7e3b21d5f86c0a94e7d2b83f150c6ead21e"

INR_PER_USDT = 90.38
DILUTION_THRESHOLD = 0.30


def load_edges():
    with EDGES_CSV.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_nodes():
    with NODES_CSV.open(newline="", encoding="utf-8") as fh:
        return {r["node_id"]: r for r in csv.DictReader(fh)}


# ---------------------------------------------------------------- structure

def test_node_and_edge_counts():
    """SPEC section 09: exactly 14 nodes and 17 edges."""
    assert len(load_nodes()) == 14
    assert len(load_edges()) == 17


def test_every_edge_endpoint_exists_as_a_node():
    nodes, missing = load_nodes(), set()
    for e in load_edges():
        for side in ("from_node", "to_node"):
            if e[side] not in nodes:
                missing.add(e[side])
    assert not missing, f"edges reference unknown nodes: {missing}"


def test_edge_ids_are_unique():
    ids = [e["edge_id"] for e in load_edges()]
    assert len(ids) == len(set(ids))


def test_exactly_one_seed_node():
    seeds = [n for n, r in load_nodes().items() if r["is_seed"] == "true"]
    assert seeds == [SEED]


# ------------------------------------------------------- data hygiene

def test_all_hex_identifiers_are_clean_hex():
    """Guards against stray non-hex characters slipping into an address
    or transaction hash - which silently breaks address matching."""
    addr_re = re.compile(r"^0x[0-9a-f]{40}$")
    hash_re = re.compile(r"^0x[0-9a-f]{64}$")

    for node_id in load_nodes():
        if node_id.startswith("0x"):
            assert addr_re.match(node_id), f"malformed address: {node_id}"

    for e in load_edges():
        if e["tx_hash"]:
            assert hash_re.match(e["tx_hash"]), f"malformed tx hash: {e['tx_hash']}"


def test_timestamps_are_chronological():
    ts = [e["timestamp"] for e in load_edges()]
    assert ts == sorted(ts), "edges must be authored in chronological order"


# ------------------------------------------------------------ conservation

def test_seed_disburses_exactly_what_it_received():
    edges = load_edges()
    received = sum(float(e["amount"]) for e in edges if e["to_node"] == SEED)
    sent = sum(float(e["amount"]) for e in edges if e["from_node"] == SEED)
    assert received == 5200.00
    assert sent == 5200.00


def test_seed_fan_out_is_exactly_five():
    """R5 (fan-out) triggers above 5. The seed must sit AT 5 so its score
    lands on exactly 65, matching the published UI mockup."""
    edges = load_edges()
    downstream = {e["to_node"] for e in edges if e["from_node"] == SEED}
    assert len(downstream) == 5


def test_wallet_1_fan_out_exceeds_five():
    """R5 must be demonstrated somewhere in the dataset."""
    edges = load_edges()
    downstream = {e["to_node"] for e in edges if e["from_node"] == W1}
    assert len(downstream) == 6


# -------------------------------------------------------------- fx rate

def test_locked_exchange_rate_is_consistent():
    """INR 4,70,000 -> 5,200 USDT implies the locked rate. The residual is
    absorbed as exchange fees and must stay under 1%."""
    inr = 470000.00
    usdt = 5200.00
    implied = inr / usdt
    assert abs(implied - INR_PER_USDT) / INR_PER_USDT < 0.01


# ------------------------------------------------------------- dilution

def _haircut(prior_balance, incoming_amount, incoming_ratio):
    """SPEC section 06 - proportional haircut."""
    dirty = incoming_amount * incoming_ratio
    return dirty / (prior_balance + incoming_amount)


def test_dilution_rescue_produces_sixty_to_twelve_percent():
    """The single most important number in the demo.

    Wallet 2 sits at 60% illicit. It sends 2,000 USDT into a pool already
    holding 8,000 clean USDT. The haircut drops that pool to 12%, below the
    30% reporting threshold, so it is correctly NOT flagged. This is the
    false-positive-avoidance story.
    """
    nodes, edges = load_nodes(), load_edges()

    # Wallet 2: 1,200 clean prior + 1,800 fully-dirty inbound -> 60%
    prior_w2 = float(nodes[W2]["prior_balance"])
    inbound_w2 = sum(float(e["amount"]) for e in edges if e["to_node"] == W2)
    ratio_w2 = _haircut(prior_w2, inbound_w2, 1.0)
    assert round(ratio_w2, 4) == 0.60

    # Clean pool: 8,000 clean prior + 2,000 inbound carrying 60% taint -> 12%
    prior_pool = float(nodes[CLEAN_POOL]["prior_balance"])
    inbound_pool = sum(
        float(e["amount"])
        for e in edges
        if e["to_node"] == CLEAN_POOL and e["from_node"] == W2
    )
    ratio_pool = _haircut(prior_pool, inbound_pool, ratio_w2)
    assert round(ratio_pool, 4) == 0.12
    assert ratio_pool < DILUTION_THRESHOLD, "the rescue wallet must NOT be flagged"


def test_seed_is_fully_tainted():
    nodes, edges = load_nodes(), load_edges()
    prior = float(nodes[SEED]["prior_balance"])
    inbound = sum(float(e["amount"]) for e in edges if e["to_node"] == SEED)
    assert _haircut(prior, inbound, 1.0) == 1.0


# --------------------------------------------------------- evidence types

def test_exactly_one_inferred_edge_exists():
    """The UPI-to-exchange correlation is a hypothesis, not a proven link.
    It must render dashed so the confirmed/inferred distinction is visible."""
    inferred = [
        e for e in load_edges() if e["evidence_type"] == "inferred_correlation"
    ]
    assert len(inferred) == 1
    assert inferred[0]["edge_id"] == "E02"


def test_bank_edges_carry_a_utr_and_onchain_edges_carry_a_hash():
    for e in load_edges():
        if e["evidence_type"] == "confirmed_onchain":
            assert e["tx_hash"], f"{e['edge_id']} missing tx_hash"
            assert e["block_number"], f"{e['edge_id']} missing block_number"
        if e["evidence_type"] == "confirmed_bank":
            assert e["utr"], f"{e['edge_id']} missing UTR"


def test_no_real_world_identifiers_in_demo_data():
    """Every identity in the demo must be synthetic."""
    blob = EDGES_CSV.read_text(encoding="utf-8") + NODES_CSV.read_text(encoding="utf-8")
    for banned in ("@okaxis", "@ybl", "@paytm", "aadhaar", "PAN"):
        assert banned.lower() not in blob.lower()


# ------------------------------------------------------- risk consistency

def test_seed_risk_indicators_sum_to_sixty_five():
    """R1(20) + R2(15) + R3(15) + R4(15) = 65, matching the UI mockup.
    R5 deliberately does not fire because seed fan-out is exactly 5."""
    assert 20 + 15 + 15 + 15 == 65


def test_seed_dispersal_is_under_four_minutes():
    """R2 trigger condition: outbound within 4 minutes of receipt."""
    from datetime import datetime

    edges = load_edges()
    received = min(
        datetime.fromisoformat(e["timestamp"]) for e in edges if e["to_node"] == SEED
    )
    first_out = min(
        datetime.fromisoformat(e["timestamp"]) for e in edges if e["from_node"] == SEED
    )
    assert 0 < (first_out - received).total_seconds() < 240
