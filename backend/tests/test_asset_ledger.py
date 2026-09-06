"""
Asset ledger — currency composition by layer and by entity.

Additive to every existing engine. Two properties carry the weight:

  * amounts must reconcile with the graph the rest of the system traced, so
    the ledger can never tell a different story from the dossier;
  * an asset with no rate must report a NULL rupee value, never a number
    invented from a rate nobody sourced. This figure could end up quoted as a
    rupee loss in a chargesheet.
"""

import pytest

from backend.app.config import DEMO_INR_PER_USDT
from backend.app.engines import assets as assets_engine
from backend.app.engines.pipeline import analyse
from backend.app.models import Asset

from ._client import make_client

CASE = "CP-CYBER-2026-001"
SEED = "0xa7f39c1d8e4b2a5f7c3d9e0a1b8c6d4e5f2a67e9"
VICTIM_BANK = "SBI_XXXXXXXX8891"

client = make_client()


@pytest.fixture(scope="module")
def ledger():
    r = client.get(f"/api/cases/{CASE}/assets")
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------- reconciliation

def test_transfer_counts_reconcile_with_the_traced_graph(ledger):
    """If the ledger and the graph disagree, one of them is lying to a court."""
    a = analyse(CASE, SEED)
    assert sum(t["transfer_count"] for t in ledger["totals"]) == len(a.edges)


def test_every_asset_in_the_graph_appears_in_the_totals(ledger):
    a = analyse(CASE, SEED)
    assert {t["asset"] for t in ledger["totals"]} == {e.asset.value
                                                     for e in a.edges}


def test_the_demo_case_carries_the_locked_victim_amount(ledger):
    """The case is a rupee loss that became USDT; both must be visible."""
    by_asset = {t["asset"]: t for t in ledger["totals"]}
    assert by_asset["INR"]["total_amount"] == pytest.approx(470000.0 * 2)
    assert by_asset["USDT"]["transfer_count"] == 15


# ----------------------------------------------------------------- conversion

def test_usdt_converts_at_the_locked_rate(ledger):
    usdt = next(t for t in ledger["totals"] if t["asset"] == "USDT")
    expected = usdt["total_amount"] * DEMO_INR_PER_USDT
    assert usdt["inr_equivalent"] == pytest.approx(expected, rel=1e-6)
    assert usdt["convertible"] is True


def test_rupees_are_grouped_the_indian_way(ledger):
    inr = next(t for t in ledger["totals"] if t["asset"] == "INR")
    assert inr["inr_formatted"] == "9,40,000"


def test_an_unpriced_asset_reports_null_not_zero():
    """THE honesty guarantee. This build has no price feed, so ETH must not be
    handed a rupee figure - a zero would read as 'worth nothing'."""
    from backend.app.models import Edge, EvidenceType

    edge = Edge(edge_id="E-eth", case_id=CASE, from_node="a", to_node="b",
                amount=3.5, asset=Asset.ETH,
                timestamp="2026-09-08T10:00:00+05:30",
                evidence_type=EvidenceType.CONFIRMED_ONCHAIN)
    row = assets_engine._tally([edge])[0]
    assert row.asset == Asset.ETH
    assert row.total_amount == 3.5
    assert row.inr_equivalent is None
    assert row.inr_formatted is None
    assert row.convertible is False


def test_the_caveat_states_the_limit_in_words(ledger):
    c = ledger["caveat"].lower()
    assert "no market price feed" in c
    assert "never that the amount is zero" in c
    assert set(ledger["convertible_assets"]) == {"INR", "USDT"}


# --------------------------------------------------------------------- layers

def test_layers_are_ordered_and_start_at_the_seed(ledger):
    depths = [l["depth"] for l in ledger["layers"]]
    assert depths == sorted(depths)
    assert depths[0] == 0


def test_every_transfer_lands_in_exactly_one_layer(ledger):
    total = sum(t["transfer_count"] for t in ledger["totals"])
    assert sum(l["transfer_count"] for l in ledger["layers"]) == total


def test_the_seed_layer_receives_usdt_not_rupees(ledger):
    """Layer 0 is where rupees have already become crypto - that is the whole
    point of the case, and the ledger should show it without commentary."""
    layer0 = next(l for l in ledger["layers"] if l["depth"] == 0)
    assert {a["asset"] for a in layer0["assets"]} == {"USDT"}


def test_layers_endpoint_matches_the_full_breakdown(ledger):
    r = client.get(f"/api/cases/{CASE}/assets/layers")
    assert r.status_code == 200
    assert r.json() == ledger["layers"]


# ---------------------------------------------------------------------- nodes

def test_a_node_reports_what_it_received_and_sent(ledger):
    r = client.get(f"/api/cases/{CASE}/assets/nodes/{SEED}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["depth"] == 0
    assert {a["asset"] for a in body["received"]} == {"USDT"}
    assert sum(a["transfer_count"] for a in body["sent"]) == 5


def test_the_mule_account_shows_rupees_in_and_rupees_out():
    """The bank node is where an officer reads a rupee figure for a freeze
    request, so it must carry a formatted rupee amount."""
    r = client.get(f"/api/cases/{CASE}/assets/nodes/{VICTIM_BANK}")
    assert r.status_code == 200, r.text
    body = r.json()
    received = next(a for a in body["received"] if a["asset"] == "INR")
    assert received["inr_formatted"] == "4,70,000"


def test_node_lookup_is_case_insensitive_for_hex():
    r = client.get(f"/api/cases/{CASE}/assets/nodes/{SEED.upper()}")
    assert r.status_code == 200


def test_unknown_node_404s():
    r = client.get(f"/api/cases/{CASE}/assets/nodes/0xdeadbeef")
    assert r.status_code == 404


# ---------------------------------------------------------------- no side effects

def test_the_ledger_writes_no_audit_row():
    """A derived view the dashboard recomputes on render must not bury real
    custody events - the same rule dilution already follows."""
    before = len(client.get(f"/api/cases/{CASE}/audit").json())
    client.get(f"/api/cases/{CASE}/assets")
    client.get(f"/api/cases/{CASE}/assets/layers")
    assert len(client.get(f"/api/cases/{CASE}/audit").json()) == before
