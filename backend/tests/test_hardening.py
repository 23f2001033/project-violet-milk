"""
Hardening fixes from the adversarial review.

Three defects, each of which survived every earlier test suite because the
tests only ever exercised the curated dataset:

  1. dilution reported 0.0 for every node on live chain data
  2. the custody log was append-only by convention, not by construction
  3. (frontend) a render error blanked the screen - covered by the
     ErrorBoundary component, not reachable from pytest
"""

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.db import cursor
from backend.app.engines.dilution import compute_dilution
from backend.app.engines.pipeline import analyse
from backend.app.main import app
from backend.app.models import Chain, Edge, EvidenceType, Node, NodeType, Asset
from backend.app.services import audit as audit_service

CASE = "CP-CYBER-2026-001"
SEED = "0xa7f39c1d8e4b2a5f7c3d9e0a1b8c6d4e5f2a67e9"
POOL = "0xd90f42a17c58e03b96d1f47a20c85e39b7f481ab"

client = TestClient(app)


# ------------------------------------------------- 1. dilution on live data

def _live_shaped_graph():
    """A live trace as EtherscanSource produces one: no victim node and no
    prior balances, because a public explorer cannot supply either."""
    ids = [f"0x{i:040x}" for i in range(4)]
    nodes = [
        Node(node_id=ids[0], case_id="LT", node_type=NodeType.UNKNOWN,
             chain=Chain.ETHEREUM, prior_balance=0.0, is_seed=True),
        *[Node(node_id=i, case_id="LT", node_type=NodeType.UNKNOWN,
               chain=Chain.ETHEREUM, prior_balance=0.0) for i in ids[1:]],
    ]
    edges = [
        Edge(edge_id=f"e{n}", case_id="LT", from_node=ids[0], to_node=ids[n],
             amount=100.0 * n, asset=Asset.USDT,
             timestamp=f"2026-09-01T10:0{n}:00+00:00",
             evidence_type=EvidenceType.CONFIRMED_ONCHAIN)
        for n in (1, 2, 3)
    ]
    return nodes, edges


def test_live_dilution_is_no_longer_all_zero():
    """Regression: with no victim node the taint had no origin, so every
    live-mode ratio came back 0.0 - the headline feature silently did nothing
    on real data."""
    nodes, edges = _live_shaped_graph()
    result, ratios = compute_dilution(
        "LT", nodes, edges, prior_balances_available=False)

    assert set(ratios.values()) != {0.0}, "live dilution is dead again"
    assert ratios[nodes[0].node_id] == 1.0, "the seed is the origin of taint"
    assert any(v == 1.0 for k, v in ratios.items() if k != nodes[0].node_id)


def test_live_mode_is_labelled_propagation_not_dilution():
    """Calling reach a 'dilution percentage' would overstate it: without a
    prior balance there is no denominator, so the number is not a proportion."""
    nodes, edges = _live_shaped_graph()
    result, _ = compute_dilution(
        "LT", nodes, edges, prior_balances_available=False)
    assert result.model == "propagation"
    assert "NOT A DILUTION FIGURE" in result.caveat


def test_curated_mode_is_still_a_true_haircut():
    a = analyse(CASE, SEED)
    assert a.dilution.model == "haircut"
    assert a.illicit_ratio[SEED] == 1.0
    assert a.illicit_ratio[POOL] == 0.12      # the rescue survives
    assert "haircut" in a.dilution.caveat.lower()


def test_the_two_models_are_never_confused_in_the_api():
    body = client.post(f"/api/cases/{CASE}/dilution").json()
    assert body["model"] == "haircut"
    assert body["caveat"]


# --------------------------------------------- 2. hash-chained custody log

def test_seeded_history_forms_a_valid_chain():
    """The demo case must not report itself as tampered."""
    v = client.get(f"/api/cases/{CASE}/audit/verify").json()
    assert v["intact"] is True
    assert v["entries"] >= 3
    assert len(v["head_hash"]) == 64


def test_new_entries_extend_the_chain():
    before = client.get(f"/api/cases/{CASE}/audit/verify").json()
    client.post(f"/api/cases/{CASE}/trace",
                json={"seed": SEED, "max_depth": 3})
    after = client.get(f"/api/cases/{CASE}/audit/verify").json()
    assert after["intact"] is True
    assert after["entries"] > before["entries"]
    assert after["head_hash"] != before["head_hash"]


def test_every_entry_commits_to_its_predecessor():
    entries = audit_service._ordered_rows(CASE)
    prev = audit_service.GENESIS
    for e in entries:
        assert e["prev_hash"] == prev
        assert len(e["entry_hash"]) == 64
        prev = e["entry_hash"]


def test_editing_a_row_is_detected():
    """THE point of the chain. Before this, any SQLite client could rewrite
    the custody log silently."""
    with cursor() as conn:
        conn.execute(
            "UPDATE audit_log SET user_id = 'IO_IMPOSTER' "
            "WHERE case_id = ? AND action = 'CASE_CREATED'", (CASE,))

    v = client.get(f"/api/cases/{CASE}/audit/verify").json()
    assert v["intact"] is False
    assert v["broken_at"], "a broken chain must name where it broke"

    # restore so later tests see a clean chain
    with cursor() as conn:
        conn.execute(
            "UPDATE audit_log SET user_id = 'IO_SHARMA' "
            "WHERE case_id = ? AND action = 'CASE_CREATED'", (CASE,))
    assert client.get(f"/api/cases/{CASE}/audit/verify").json()["intact"] is True


def test_deleting_a_row_is_detected():
    with cursor() as conn:
        row = conn.execute(
            "SELECT * FROM audit_log WHERE case_id = ? ORDER BY rowid ASC "
            "LIMIT 1 OFFSET 1", (CASE,)).fetchone()
        saved = dict(row)
        conn.execute("DELETE FROM audit_log WHERE audit_id = ?",
                     (saved["audit_id"],))

    assert client.get(f"/api/cases/{CASE}/audit/verify").json()["intact"] is False

    with cursor() as conn:
        conn.execute(
            "INSERT INTO audit_log (audit_id, case_id, timestamp, user_id, "
            "action, target, target_hash, details, seq, prev_hash, "
            "entry_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            tuple(saved[k] for k in (
                "audit_id", "case_id", "timestamp", "user_id", "action",
                "target", "target_hash", "details", "seq", "prev_hash",
                "entry_hash")))
    assert client.get(f"/api/cases/{CASE}/audit/verify").json()["intact"] is True


def test_details_are_canonical_json_so_the_digest_reproduces():
    """Unsorted keys would make a valid chain verify as broken."""
    entry = audit_service.record(
        CASE, __import__("backend.app.models", fromlist=["AuditAction"])
        .AuditAction.CASE_UPDATED, "canonical-test",
        details={"z": 1, "a": 2},
    )
    stored = next(e for e in audit_service._ordered_rows(CASE)
                  if e["audit_id"] == entry.audit_id)
    assert json.dumps(stored["details"], sort_keys=True) == \
        json.dumps({"z": 1, "a": 2}, sort_keys=True)
    assert client.get(f"/api/cases/{CASE}/audit/verify").json()["intact"] is True
