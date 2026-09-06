"""
API contract tests - Phase 1 acceptance gate.

Proves every endpoint in SPEC section 08 exists and returns the frozen shape.
These run against the fixture stubs today and must keep passing unchanged after
Phase 2 swaps in the real engines. If one of these breaks during Phase 2, the
engine is wrong - not the test.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

from ._client import make_client

CASE = "CP-CYBER-2026-001"
SEED = "0xa7f39c1d8e4b2a5f7c3d9e0a1b8c6d4e5f2a67e9"
RESCUE = "0xd90f42a17c58e03b96d1f47a20c85e39b7f481ab"

client = make_client()


# ------------------------------------------------------------------ system

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"ok", "degraded"}
    assert set(body["components"]) == {
        "database", "graph_engine", "report_engine",
        "llm_configured", "etherscan_configured", "anchoring_configured",
        "auth_enabled", "using_default_password",
    }


def test_openapi_exposes_every_specified_endpoint():
    paths = client.get("/openapi.json").json()["paths"]
    expected = [
        "/api/health",
        "/api/cases",
        "/api/cases/{case_id}",
        "/api/cases/{case_id}/evidence",
        "/api/cases/{case_id}/trace",
        "/api/cases/{case_id}/graph",
        "/api/cases/{case_id}/timeline",
        "/api/cases/{case_id}/nodes/{node_id}/risk",
        "/api/cases/{case_id}/dilution",
        "/api/cases/{case_id}/audit",
        "/api/cases/{case_id}/report",
        "/api/labels/{address}",
    ]
    for p in expected:
        assert p in paths, f"missing endpoint: {p}"


# ------------------------------------------------------------------- cases

def test_list_and_get_case():
    assert client.get("/api/cases").status_code == 200
    body = client.get(f"/api/cases/{CASE}").json()
    assert body["case_id"] == CASE
    assert body["victim_amount_inr"] == 470000.0
    assert body["seed_wallet"] == SEED


def test_unknown_case_is_404():
    assert client.get("/api/cases/NOPE-123").status_code == 404


# ------------------------------------------------------------------- graph

def test_graph_is_cytoscape_ready():
    body = client.get(f"/api/cases/{CASE}/graph").json()
    assert body["stats"]["nodes"] == 14
    assert body["stats"]["edges"] == 17
    nodes = body["elements"]["nodes"]
    edges = body["elements"]["edges"]
    assert all("data" in n and "id" in n["data"] for n in nodes)
    assert all({"source", "target"} <= set(e["data"]) for e in edges)


def test_seed_node_scores_sixty_five():
    """Locked against the published UI mockup."""
    body = client.get(f"/api/cases/{CASE}/graph").json()
    seed = next(n["data"] for n in body["elements"]["nodes"] if n["data"]["is_seed"])
    assert seed["risk_score"] == 65
    assert seed["risk_level"] == "HIGH"


def test_graph_contains_one_inferred_edge():
    body = client.get(f"/api/cases/{CASE}/graph").json()
    inferred = [
        e for e in body["elements"]["edges"]
        if e["data"]["evidence_type"] == "inferred_correlation"
    ]
    assert len(inferred) == 1, "the confirmed/inferred distinction must be visible"


def test_trace_rejects_depth_beyond_the_ceiling():
    r = client.post(f"/api/cases/{CASE}/trace",
                    json={"seed": SEED, "max_depth": 99})
    assert r.status_code == 400


def test_trace_returns_ids():
    r = client.post(f"/api/cases/{CASE}/trace",
                    json={"seed": SEED, "max_depth": 3})
    assert r.status_code == 200
    body = r.json()
    assert len(body["node_ids"]) == 14
    assert len(body["edge_ids"]) == 17


# -------------------------------------------------------------------- risk

def test_seed_risk_indicators_are_all_evidenced():
    body = client.get(f"/api/cases/{CASE}/nodes/{SEED}/risk").json()
    assert body["score"] == 65
    assert sum(i["points"] for i in body["indicators"]) == 65
    for ind in body["indicators"]:
        assert ind["evidence"].strip(), "an indicator with no evidence is invalid"


def test_risk_resolves_for_a_non_seed_node():
    r = client.get(f"/api/cases/{CASE}/nodes/{RESCUE}/risk")
    assert r.status_code == 200
    assert r.json()["illicit_ratio"] == 0.12


def test_unknown_node_is_404():
    r = client.get(f"/api/cases/{CASE}/nodes/0xdeadbeef/risk")
    assert r.status_code == 404


# ---------------------------------------------------------------- dilution

def test_dilution_shows_the_rescue():
    body = client.post(f"/api/cases/{CASE}/dilution").json()
    pool = next(s for s in body["steps"] if s["node_id"] == RESCUE)
    assert pool["illicit_ratio"] == 0.12
    assert pool["flagged"] is False
    assert body["threshold"] == 0.30


# --------------------------------------------------- timeline / evidence / audit

def test_timeline_is_sorted_with_deltas():
    body = client.get(f"/api/cases/{CASE}/timeline").json()
    assert len(body) == 17
    assert [e["timestamp"] for e in body] == sorted(e["timestamp"] for e in body)
    assert body[0]["delta_seconds_prev"] == 0
    assert body[1]["delta_seconds_prev"] == 13   # the +13s UPI->exchange gap


def test_evidence_hashes_match():
    body = client.get(f"/api/cases/{CASE}/evidence").json()
    for ev in body:
        assert ev["sha256_client"] == ev["sha256_server"]
        assert ev["hash_match"] is True


def test_audit_log_records_the_trace():
    actions = [a["action"] for a in client.get(f"/api/cases/{CASE}/audit").json()]
    assert "CASE_CREATED" in actions
    assert "TRACE_RUN" in actions


# ------------------------------------------------------------------ report

def test_report_generates_a_dossier():
    """Was a 501 placeholder through Phase 4; implemented in Phase 5.
    Depth is covered by test_phase5_report_ai.py - this only guards the
    frozen response shape."""
    r = client.post(f"/api/cases/{CASE}/report")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"case_id", "filename", "sha256", "generated_at",
                         "page_count", "download_url", "anchor"}
    assert len(body["sha256"]) == 64
    assert body["page_count"] >= 4


def test_reading_the_dashboard_does_not_pollute_the_custody_log():
    """Regression: /dilution used to write an audit row, so every page load
    appended a DILUTION_COMPUTED entry and buried the real custody events.
    The chain of custody records investigator actions on evidence, not
    incidental recomputation."""
    before = len(client.get(f"/api/cases/{CASE}/audit").json())
    for _ in range(3):
        client.get(f"/api/cases/{CASE}/graph")
        client.post(f"/api/cases/{CASE}/dilution")
        client.get(f"/api/cases/{CASE}/timeline")
    after = client.get(f"/api/cases/{CASE}/audit").json()
    assert len(after) == before
    assert not any(a["action"] == "DILUTION_COMPUTED" for a in after)


# ------------------------------------------------- real evidence ingestion

def test_evidence_upload_stores_and_maps_columns():
    """The uploader is a real ingestion path, not a preview widget: the file
    is hashed in the browser, re-hashed here, stored, audited, and its columns
    mapped onto the case schema."""
    import hashlib

    csv_bytes = (
        b"Txn Date,Ref No./Cheque No.,Narration,Debit,Bank Name\n"
        b"2026-09-08,420192830192,UPI/TRANSFER,470000,SBI\n"
    )
    digest = hashlib.sha256(csv_bytes).hexdigest()

    r = client.post(
        f"/api/cases/{CASE}/evidence",
        files={"file": ("Bank_Stmt_Test.csv", csv_bytes, "text/csv")},
        data={"sha256_client": digest, "is_synthetic": "true",
              "uploaded_by": "IO_TEST"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["sha256_server"] == digest
    assert body["hash_match"] is True
    assert body["row_count"] == 1
    assert body["column_mapping"]["timestamp"] == "Txn Date"
    assert body["column_mapping"]["amount"] == "Debit"

    listed = client.get(f"/api/cases/{CASE}/evidence").json()
    assert any(e["evidence_id"] == body["evidence_id"] for e in listed)

    audit = client.get(f"/api/cases/{CASE}/audit").json()
    assert any(a["target_hash"] == digest for a in audit)


def test_evidence_upload_rejects_a_hash_mismatch():
    """A file that changed in transit must be REJECTED, never stored. An
    evidence table holding unverified files is worse than no table."""
    before = len(client.get(f"/api/cases/{CASE}/evidence").json())
    r = client.post(
        f"/api/cases/{CASE}/evidence",
        files={"file": ("tampered.csv", b"a,b\n1,2\n", "text/csv")},
        data={"sha256_client": "0" * 64, "is_synthetic": "true"},
    )
    assert r.status_code == 422
    assert "rejected" in r.json()["detail"].lower()
    after = len(client.get(f"/api/cases/{CASE}/evidence").json())
    assert after == before, "a rejected file must not be persisted"
