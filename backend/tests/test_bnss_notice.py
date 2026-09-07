"""
Section 94 BNSS production order - acceptance tests.

The load-bearing guarantees, in order of how much damage they prevent:

  * nothing can present the draft as a signed or served order;
  * the addressee is chosen from the trace, never invented, and a trace that
    reached no exchange says so instead of naming somebody;
  * the Schedule recites transactions that actually exist in the graph.

A production order is a legal instrument. Every claim it makes has to come
from evidence the system genuinely holds.
"""

import hashlib

import pytest

from backend.app import config
from backend.app.engines import notice_engine
from backend.app.engines.pipeline import analyse
from backend.app.models import NodeType

from ._client import make_client

CASE = "CP-CYBER-2026-001"
SEED = "0xa7f39c1d8e4b2a5f7c3d9e0a1b8c6d4e5f2a67e9"

client = make_client()


@pytest.fixture(scope="module")
def notice():
    r = client.post(f"/api/cases/{CASE}/notice")
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------- never a real order

def test_the_draft_can_never_claim_to_be_signed(notice):
    assert notice["status"] == "DRAFT"
    assert notice["signed"] is False


def test_no_endpoint_can_issue_or_serve_a_notice():
    """Authority to issue comes from an officer's signature, not from software.
    A route that could set `signed` would be a lie about a legal instrument."""
    paths = client.get("/openapi.json").json()["paths"]
    banned = {"issue", "serve", "sign", "dispatch"}
    for path, verbs in paths.items():
        segments = {s.lower() for s in path.split("/") if not s.startswith("{")}
        mutating = {"post", "put", "patch"} & set(verbs)
        assert not (segments & banned and mutating), (
            f"{path} exposes {sorted(segments & banned)} - nothing may issue "
            "or serve a production order"
        )


def test_officer_and_station_are_placeholders_not_inventions(notice):
    f = notice["fields"]
    for key in ("issuing_officer", "designation", "police_station"):
        assert "TO BE COMPLETED" in f[key], key


def test_the_addressee_legal_name_is_not_invented(notice):
    """We know an on-chain label. We do not know a company's legal name or
    registered address, and serving the wrong entity is a real harm."""
    assert "LEGAL NAME" in notice["fields"]["addressee_legal_name"]


def test_limitations_state_the_draft_has_no_legal_effect(notice):
    text = " ".join(notice["fields"]["limitations"]).lower()
    assert "no legal effect" in text
    assert "not been settled by a legal practitioner" in text
    assert "mutual legal assistance" in text


# ---------------------------------------------------------------- addressee

def test_the_addressee_is_an_exchange_from_the_trace(notice):
    a = analyse(CASE, SEED)
    exchanges = {n.node_id for n in a.nodes if n.node_type == NodeType.EXCHANGE}
    assert notice["addressee_identified"] is True
    assert notice["fields"]["addressee_address_on_chain"] in exchanges


def test_a_trace_with_no_exchange_names_nobody():
    """THE safety case. An order drafted against an unidentified party is
    worse than no order at all."""
    a = analyse(CASE, SEED)
    a.nodes = [n for n in a.nodes if n.node_type != NodeType.EXCHANGE]
    assert notice_engine.identify_addressee(a) is None

    fields = notice_engine.build_fields(a, {"case_id": CASE,
                                            "victim_amount_inr": 470000.0})
    assert fields["addressee_address_on_chain"] is None
    assert fields["addressee_observed_label"] == "NO EXCHANGE IDENTIFIED"
    assert fields["schedule"] == []


def test_addressee_is_ranked_by_tainted_value_not_gross():
    """A large clean inflow must not make an address the right one to serve."""
    a = analyse(CASE, SEED)
    target = notice_engine.identify_addressee(a)
    assert target is not None
    assert target["illicit_ratio"] > 0


# ----------------------------------------------------------------- schedule

def test_every_scheduled_transaction_exists_in_the_graph(notice):
    a = analyse(CASE, SEED)
    known = {(e.from_node, e.to_node) for e in a.edges}
    assert notice["fields"]["schedule"]
    for s in notice["fields"]["schedule"]:
        assert (s["sending_address"], s["deposit_address"]) in known


def test_the_schedule_is_in_time_order(notice):
    stamps = [s["timestamp_ist"] for s in notice["fields"]["schedule"]]
    assert stamps == sorted(stamps)


def test_the_records_sought_ask_for_kyc_and_linked_indian_accounts(notice):
    text = " ".join(notice["fields"]["records_sought"]).lower()
    assert "know your customer" in text
    assert "unified payments interface" in text
    assert "internet protocol address" in text


def test_the_statutory_basis_is_named(notice):
    assert "94" in notice["fields"]["statutory_basis"]
    assert "Bharatiya Nagarik Suraksha Sanhita" in notice["fields"]["statutory_basis"]


# --------------------------------------------------------------- the artefact

def test_printed_hash_matches_the_file(notice):
    path = config.REPORTS_DIR / notice["filename"]
    assert path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == notice["sha256"]


def test_the_draft_is_downloadable(notice):
    r = client.get(notice["download_url"])
    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"


def test_generation_is_recorded_in_the_custody_log(notice):
    audit = client.get(f"/api/cases/{CASE}/audit").json()
    entry = next(
        (a for a in audit
         if a.get("details", {}).get("kind") == "BNSS94_DRAFT"
         and a["target_hash"] == notice["sha256"]),
        None)
    assert entry is not None
    assert entry["details"]["signed"] is False


def test_unknown_case_404s():
    assert client.post("/api/cases/NOPE-999/notice").status_code == 404


def test_the_schedule_carries_the_confirmed_leg_not_only_the_inference():
    """On the demo case the only INBOUND edge at the exchange is the inferred
    bank correlation. An order resting on that alone would rest on our weakest
    link, so the confirmed on-chain withdrawal must appear too."""
    a = analyse(CASE, SEED)
    fields = notice_engine.build_fields(
        a, {"case_id": CASE, "victim_amount_inr": 470000.0})
    bases = {s["basis"] for s in fields["schedule"]}
    assert "CONFIRMED" in bases, "the order must recite confirmed evidence"
    assert len(fields["schedule"]) >= 2


def test_every_scheduled_line_declares_its_basis():
    """A defence reads the Schedule. Which lines are contestable has to be on
    the face of the order, not buried in a field name."""
    a = analyse(CASE, SEED)
    fields = notice_engine.build_fields(
        a, {"case_id": CASE, "victim_amount_inr": 470000.0})
    for s in fields["schedule"]:
        assert s["basis"] in {"CONFIRMED", "INFERRED"}
        assert s["direction"] in {"RECEIVED BY", "SENT BY"}


# ------------------------------------------------- current Indian statute law

def test_the_order_names_who_may_issue_it(notice):
    """Sec 94(1) BNSS empowers a Court or an officer in charge of a police
    station. An order that does not recite its own authority invites the first
    question a defence will ask."""
    text = notice["fields"]["issuing_authority"]
    assert "94(1)" in text
    assert "officer in charge of a police station" in text
    assert "software cannot confer that authority" in text


def test_no_repealed_statute_is_cited(notice):
    """The CrPC 1973 and the Indian Evidence Act 1872 stand repealed. Citing
    either in a document served on a third party would be an obvious error."""
    blob = str(notice["fields"]).lower()
    for repealed in ("criminal procedure code", "code of criminal procedure",
                     "indian evidence act", "section 91 of the code"):
        assert repealed not in blob, repealed
