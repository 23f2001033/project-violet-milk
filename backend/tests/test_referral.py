"""
Internal referral note - acceptance tests.

This document is the odd one out. The Sec 63 certificate and the Sec 94 order
have prescribed forms; this has none, and that is exactly where the danger
sits. A memo that quietly borrowed statutory language would undo the
discipline that makes the other two credible.

So most of what follows guards against the note claiming to be more than an
internal working paper.
"""

import hashlib

import pytest

from backend.app import config
from backend.app.engines import referral_engine
from backend.app.engines.pipeline import analyse
from backend.app.models import NodeType

from ._client import make_client

CASE = "CP-CYBER-2026-001"
SEED = "0xa7f39c1d8e4b2a5f7c3d9e0a1b8c6d4e5f2a67e9"

client = make_client()


@pytest.fixture(scope="module")
def referral():
    r = client.post(f"/api/cases/{CASE}/referral")
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------- never more than it is

def test_it_is_never_statutory(referral):
    """No provision prescribes this form. Claiming one would be an invention
    of exactly the kind the Sec 94 order refuses to make."""
    assert referral["statutory"] is False
    assert "not a statutory instrument" in referral["fields"]["instrument_type"].lower()


def test_it_is_never_transmitted(referral):
    """A referral is made by an officer through their own chain. The same rule
    that forbids an STR-filing endpoint applies here."""
    assert referral["transmitted"] is False
    assert "sent to nobody" in referral["instruction"]


def test_no_endpoint_can_transmit_a_referral():
    paths = client.get("/openapi.json").json()["paths"]
    banned = {"send", "transmit", "refer", "dispatch", "file"}
    for path, verbs in paths.items():
        segments = {s.lower() for s in path.split("/") if not s.startswith("{")}
        mutating = {"post", "put", "patch"} & set(verbs)
        offending = segments & banned
        assert not (offending and mutating), (
            f"{path} exposes {sorted(offending)} - nothing may transmit a "
            "referral on an officer's behalf"
        )


def test_the_officer_fields_are_placeholders(referral):
    f = referral["fields"]
    for key in ("referring_officer", "designation", "police_station"):
        assert "TO BE COMPLETED" in f[key], key


def test_it_states_what_it_is_not(referral):
    text = " ".join(referral["fields"]["limitations"]).lower()
    assert "recites no statutory authority" in text
    assert "compels nobody" in text
    assert "not thereby innocent" in text
    assert "not a legal identity" in text


def test_it_does_not_claim_to_discharge_a_reporting_obligation(referral):
    """An officer's referral is not an STR. Conflating them would let a
    reporting entity believe its own duty had been met."""
    fiu = next(r for r in referral["fields"]["routes"]
               if "FIU-IND" in r["route"])
    assert "not a Suspicious Transaction Report" in fiu["detail"]
    assert "does not discharge" in fiu["detail"]


def test_no_company_is_named(referral):
    blob = str(referral).lower()
    for brand in ("binance", "wazirx", "coindcx", "chainalysis", "trm labs"):
        assert brand not in blob, brand


# ------------------------------------------------------------- the content

def test_it_lists_only_addresses_that_cannot_be_served(referral):
    """Every entry must be one a production order genuinely cannot reach. An
    exchange appearing here would send the officer down the wrong route."""
    assert referral["addresses_referred"] > 0
    kinds = {a["type"] for a in referral["fields"]["addresses"]}
    assert "exchange" not in kinds
    assert "bank_account" not in kinds


def test_each_address_says_why_it_cannot_be_served(referral):
    for a in referral["fields"]["addresses"]:
        assert a["why_not_serveable"].strip()
        assert a["disposition"] in {"unhosted", "pass_through_contract",
                                    "bounds_reached"}


def test_it_names_all_three_routes(referral):
    routes = {r["route"] for r in referral["fields"]["routes"]}
    assert any("FIU-IND" in r for r in routes)
    assert any("attribution" in r.lower() for r in routes)
    assert any("Monitoring" in r for r in routes)


def test_monitoring_names_the_trigger_for_an_order(referral):
    """The point of monitoring: an unhosted address becomes compellable the
    moment its funds reach a hosted service."""
    mon = next(r for r in referral["fields"]["routes"]
               if "Monitoring" in r["route"])
    assert "94 BNSS" in mon["detail"]
    assert "hosted service" in mon["detail"]


def test_a_terminal_exchange_is_never_called_unhosted():
    """THE inversion to guard against. An exchange that sends nothing onward is
    not a dead end - it is the destination, and it CAN be served. Listing it
    here would tell an officer "no custodian holds this key" about the one
    party in the trace who does."""
    a = analyse(CASE, SEED)
    exchanges = {n.node_id for n in a.nodes if n.node_type == NodeType.EXCHANGE}
    # Strip the exchange's outbound legs so it becomes terminal in the data.
    a.edges = [e for e in a.edges if e.from_node not in exchanges]

    fields = referral_engine.build_fields(
        a, {"case_id": CASE, "fir_ref": "X", "ncrp_ref": "Y"})
    listed = {x["address"] for x in fields["addresses"]}
    assert not (listed & exchanges), "an exchange must never be referred as unhosted"


def test_a_trace_with_nothing_unattributable_produces_an_empty_schedule():
    """A note listing no addresses must not read as an empty form - the
    document sends the officer to the production order instead."""
    a = analyse(CASE, SEED)
    # Keep only the legs that end at the exchange: every endpoint is then a
    # party that can be served, so nothing is referable.
    exchanges = {n.node_id for n in a.nodes if n.node_type == NodeType.EXCHANGE}
    a.edges = [e for e in a.edges if e.to_node in exchanges]
    a.nodes = [n for n in a.nodes
               if n.node_id in exchanges
               or n.node_id in {e.from_node for e in a.edges}]

    fields = referral_engine.build_fields(
        a, {"case_id": CASE, "fir_ref": "X", "ncrp_ref": "Y"})
    assert fields["addresses"] == []


# ------------------------------------------------------------- the artefact

def test_printed_hash_matches_the_file(referral):
    path = config.REPORTS_DIR / referral["filename"]
    assert path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == referral["sha256"]


def test_it_is_downloadable(referral):
    r = client.get(referral["download_url"])
    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"


def test_generation_is_recorded_in_the_custody_log(referral):
    audit = client.get(f"/api/cases/{CASE}/audit").json()
    entry = next(
        (a for a in audit
         if a.get("details", {}).get("kind") == "INTERNAL_REFERRAL"
         and a["target_hash"] == referral["sha256"]),
        None)
    assert entry is not None
    assert entry["details"]["statutory"] is False
    assert entry["details"]["transmitted"] is False


def test_unknown_case_404s():
    assert client.post("/api/cases/NOPE-999/referral").status_code == 404
