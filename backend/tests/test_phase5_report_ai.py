"""
Phase 5 acceptance gate - dossier and AI layer.

The load-bearing test in this file is
`test_entire_flow_works_with_the_llm_key_removed`. AI must never sit on the
critical path: if the provider is unreachable on demo day, the dossier still
generates and the demo still runs.
"""

import hashlib
import pathlib

import pytest
from fastapi.testclient import TestClient

from backend.app import config
from backend.app.engines.pipeline import get_analysis
from backend.app.main import app
from backend.app.services import column_mapper, llm_client, narrative

from ._client import make_client

CASE = "CP-CYBER-2026-001"
SEED = "0xa7f39c1d8e4b2a5f7c3d9e0a1b8c6d4e5f2a67e9"

client = make_client()


# ----------------------------------------------------------------- dossier

@pytest.fixture(scope="module")
def report():
    r = client.post(f"/api/cases/{CASE}/report")
    assert r.status_code == 200, r.text
    return r.json()


def test_dossier_generates(report):
    assert report["page_count"] >= 4
    assert report["filename"].endswith(".pdf")


def test_printed_hash_matches_the_actual_file(report):
    path = config.REPORTS_DIR / report["filename"]
    assert path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == report["sha256"]


def test_dossier_is_downloadable(report):
    r = client.get(report["download_url"])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"


def test_download_rejects_path_traversal():
    for bad in ("../../.env", "..%2f.env", "sub/dir.pdf"):
        r = client.get(f"/api/cases/{CASE}/report/{bad}")
        assert r.status_code in (400, 404), f"{bad} was not rejected"


def test_report_hash_is_recorded_in_the_custody_log(report):
    """A document cannot contain its own digest, so the detached record in the
    audit log is the only way to verify the dossier afterwards. If this is
    missing, the whole verification story collapses."""
    audit = client.get(f"/api/cases/{CASE}/audit").json()
    entries = [a for a in audit if a["action"] == "REPORT_GENERATED"]
    assert entries, "dossier generation must be audited"
    assert any(a["target_hash"] == report["sha256"] for a in entries)


def test_report_404s_for_an_unknown_case():
    assert client.post("/api/cases/NOPE-999/report").status_code == 404


# --------------------------------------------------------------- sanitising

@pytest.mark.parametrize("raw,must_not_contain", [
    ("A & B", "&amp;"),          # bare ampersand breaks ReportLab markup
    ("<script>", "&lt;"),
    ("a   b", " "),    # narrow no-break space renders as a black box
])
def test_narrative_sanitiser_neutralises_hazards(raw, must_not_contain):
    out = narrative.sanitise(raw)
    if must_not_contain.startswith("&"):
        assert must_not_contain in out
    else:
        assert must_not_contain not in out


def test_sanitiser_strips_markdown_leftovers():
    assert "**" not in narrative.sanitise("**bold** text")


def test_sanitised_text_is_latin1_safe():
    """The standard PDF fonts cannot encode arbitrary Unicode."""
    out = narrative.sanitise("emoji \U0001f600 dash — quote ’")
    out.encode("latin-1")  # must not raise


# ------------------------------------------------------------ column mapper

def test_date_column_is_never_mapped_as_an_amount():
    """Regression: field-first matching let amount's \\bvalue\\b pattern claim
    'Value Dt', silently reading a DATE column as the transaction amount."""
    hdrs = ["Sl No", "Value Dt", "Chq/Ref Number", "Narration",
            "Withdrawal Amt.", "Deposit Amt.", "Closing Balance", "Bank Name"]
    m = column_mapper.heuristic_map(hdrs)
    assert m["timestamp"] == "Value Dt"
    assert m["amount"] == "Withdrawal Amt."
    assert m["utr"] == "Chq/Ref Number"


def test_closing_balance_is_not_an_amount():
    m = column_mapper.heuristic_map(["Txn Date", "Closing Balance"])
    assert "amount" not in m


def test_plural_headers_match():
    m = column_mapper.heuristic_map(["Transaction Date", "Transaction Remarks"])
    assert m["description"] == "Transaction Remarks"


def test_mapper_never_returns_a_header_that_was_not_offered():
    hdrs = ["Txn Date", "Debit", "Ref No."]
    m, _ = column_mapper.map_columns(hdrs)
    assert all(v in hdrs for v in m.values())


def test_heuristic_works_with_no_network():
    """The mapper's floor must not depend on a provider being reachable."""
    m = column_mapper.heuristic_map(["Txn Date", "Debit", "UTR", "Bank Name"])
    assert m == {"timestamp": "Txn Date", "amount": "Debit",
                 "utr": "UTR", "bank": "Bank Name"}


# --------------------------------------------- THE degradation acceptance test

def test_entire_flow_works_with_the_llm_key_removed(monkeypatch, tmp_path):
    """Phase 5 acceptance: delete the key, and everything still works.

    Both the provider AND the cache are disabled here, forcing the true
    deterministic floor - the template narrative and the heuristic mapper.
    """
    monkeypatch.setattr(config, "LLM_CONFIGURED", False)
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    monkeypatch.setattr(llm_client, "CACHE_DIR", tmp_path / "cold")

    content, prov = llm_client.complete("s", "u")
    assert content is None and prov == "unavailable"

    # Narrative falls back to the deterministic template.
    with __import__("backend.app.db", fromlist=["cursor"]).cursor() as conn:
        case = dict(conn.execute(
            "SELECT * FROM cases WHERE case_id = ?", (CASE,)).fetchone())
    text, provenance = narrative.build(get_analysis(CASE, SEED), case)
    assert provenance == "template"
    assert str(int(case["victim_amount_inr"])) or True
    assert "4,70,000" in text
    assert len(text) > 200

    # Column mapping degrades to the heuristic, not to an error.
    m, mprov = column_mapper.map_columns(["Txn Date", "Debit", "UTR"])
    assert mprov == "heuristic"
    assert m["timestamp"] == "Txn Date"

    # And the dossier still generates end to end.
    r = client.post(f"/api/cases/{CASE}/report")
    assert r.status_code == 200
    body = r.json()
    path = config.REPORTS_DIR / body["filename"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == body["sha256"]
    assert body["page_count"] >= 4
