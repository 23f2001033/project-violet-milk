"""
Flag Agent + FIU-IND STR draft - acceptance tests.

The two load-bearing guarantees here:

  * ML output can never become a risk score.
  * The STR can never claim to have been filed.

Both are claims the deck makes, and both are only defensible if enforced in
code rather than promised in a slide.
"""

import hashlib

import pytest
from fastapi.testclient import TestClient

from backend.app import config
from backend.app.engines.anomaly import (
    MIN_SAMPLES_FOR_MODEL, detect, extract_features,
)
from backend.app.engines.pipeline import analyse, get_analysis
from backend.app.main import app

CASE = "CP-CYBER-2026-001"
SEED = "0xa7f39c1d8e4b2a5f7c3d9e0a1b8c6d4e5f2a67e9"
VICTIM = "VICTIM_4471"

client = TestClient(app)


@pytest.fixture(scope="module")
def analysis():
    return analyse(CASE, SEED)


# ------------------------------------------------------------- Flag Agent

def test_anomaly_model_trains_on_the_demo_case(analysis):
    r = analysis.anomaly
    assert r is not None and r.trained is True
    assert r.outliers, "the model should surface at least one outlier"


def test_every_outlier_is_explained(analysis):
    """An unexplained ML flag is an oracle. Each one must name the feature
    that separated the wallet from its peers."""
    for nid in analysis.anomaly.outliers:
        assert analysis.anomaly.explanations.get(nid, "").strip()


def test_anomaly_is_deterministic():
    """random_state is pinned: the same case must produce the same findings
    every run, including on stage."""
    a1 = analyse(CASE, SEED)
    a2 = analyse(CASE, SEED)
    assert a1.anomaly.outliers == a2.anomaly.outliers
    assert a1.anomaly.scores == a2.anomaly.scores


def test_ml_does_not_change_any_risk_score(analysis):
    """THE guarantee. Scores must be reproducible from the seven documented
    rules alone; if ML leaked in, these sums would not reconcile."""
    for nid, r in analysis.risk.items():
        assert r.score == max(0, min(100, sum(i.points for i in r.indicators)))
        assert all(i.rule_id.startswith("R") for i in r.indicators)


def test_an_ml_outlier_is_not_automatically_high_risk(analysis):
    """The complainant is an outlier - they moved the largest single amount -
    and is obviously not a suspect. If ML drove scoring, the victim would be
    flagged. This test is the reason ML is kept off the score."""
    assert VICTIM in analysis.anomaly.outliers
    assert analysis.risk[VICTIM].score == 0


def test_model_is_skipped_rather_than_run_on_noise():
    nodes, edges = [], []
    r = detect(nodes, edges)
    assert r.trained is False
    assert str(MIN_SAMPLES_FOR_MODEL) in r.reason


def test_features_are_extracted_per_entity(analysis):
    feats = extract_features(analysis.nodes, analysis.edges)
    assert len(feats) == len(analysis.nodes)
    seed = next(f for f in feats if f.node_id == SEED)
    assert seed.in_count == 1
    assert seed.out_count == 5
    assert seed.pass_through_ratio == pytest.approx(1.0, abs=0.01)


def test_anomaly_endpoint_is_separate_from_risk():
    """Served on its own path with its own shape, so a model finding can never
    be consumed as a statutory risk assessment."""
    r = client.get(f"/api/cases/{CASE}/anomaly")
    assert r.status_code == 200
    body = r.json()
    assert "risk_score" not in body
    assert "level" not in body
    assert "lead generation only" in body["advisory"].lower()
    for f in body["findings"]:
        assert set(f) == {"node_id", "score", "cluster", "explanation"}


# --------------------------------------------------------------- STR draft

@pytest.fixture(scope="module")
def str_doc():
    r = client.post(f"/api/cases/{CASE}/str")
    assert r.status_code == 200, r.text
    return r.json()


def test_str_is_always_a_draft(str_doc):
    assert str_doc["status"] == "DRAFT"
    assert str_doc["filed"] is False


def test_no_endpoint_can_file_an_str():
    """FIU-IND's FINnet portal has no public submission API and filing
    requires registered-entity status. A filing endpoint must not exist."""
    paths = client.get("/openapi.json").json()["paths"]
    # Match whole path segments, not substrings - "{filename}" on the download
    # route legitimately contains "file" and is not a submission endpoint.
    banned = {"file", "filing", "submit", "lodge", "finnet", "fiu"}
    for path, verbs in paths.items():
        segments = {s.lower() for s in path.split("/") if not s.startswith("{")}
        offending = segments & banned
        mutating = {"post", "put", "patch"} & set(verbs)
        assert not (offending and mutating), (
            f"{path} exposes {sorted(offending)} over {sorted(mutating)} - "
            "nothing in this system may transmit a report to FIU-IND"
        )


def test_str_does_not_invent_reporting_entity_details(str_doc):
    """We are not a Reporting Entity. Those fields must be placeholders, not
    fabrications."""
    f = str_doc["fields"]
    for key in ("reporting_entity_name", "reporting_entity_fiu_reg_no",
                "principal_officer_name"):
        assert "TO BE COMPLETED" in f[key]


def test_str_does_not_claim_to_identify_a_person(str_doc):
    subject = str_doc["fields"]["subject"]
    assert "NOT IDENTIFIED" in subject["identification_status"]
    assert "94 BNSS" in subject["identification_status"]


def test_str_carries_the_evidenced_indicators(str_doc):
    g = str_doc["fields"]["grounds_of_suspicion"]
    assert g["risk_score"] == "65/100"
    assert g["risk_level"] == "HIGH"
    assert len(g["indicators"]) == 4
    for i in g["indicators"]:
        assert i["evidence"].strip()


def test_str_separates_confirmed_from_inferred(str_doc):
    ts = str_doc["fields"]["transaction_summary"]
    assert ts["confirmed_transfers"] == 16
    assert ts["inferred_correlations"] == 1


def test_str_states_its_limitations(str_doc):
    lims = " ".join(str_doc["fields"]["limitations"]).lower()
    assert "not a finding of guilt" in lims
    assert "cannot file" in lims


def test_str_pdf_hash_matches_the_file(str_doc):
    path = config.REPORTS_DIR / str_doc["filename"]
    assert path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == str_doc["sha256"]


def test_str_is_downloadable(str_doc):
    r = client.get(str_doc["download_url"])
    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"


def test_str_generation_is_audited(str_doc):
    audit = client.get(f"/api/cases/{CASE}/audit").json()
    entry = next(
        (a for a in audit if a.get("details", {}).get("kind") == "STR_DRAFT"),
        None)
    assert entry is not None
    assert entry["details"]["filed"] is False
    assert entry["target_hash"] == str_doc["sha256"]
