"""
Conversion trail - where value changed form, and whose hands it passed through.

Three guarantees carry the weight:

  * no company is ever named. An on-chain label is not a legal identity, and
    reporting "Binance" because an address resembles one would be the single
    most damaging thing this system could do;
  * a conversion is only as good as its WEAKER leg. The rupee side of the
    demo case is an inference, so the conversion is INFERRED even though the
    on-chain side is proven;
  * the rate is described as implied, because it is arithmetic on two legs and
    not a sourced market price.
"""

import pytest

from backend.app.engines import conversion
from backend.app.engines.pipeline import analyse
from backend.app.models import NodeType

from ._client import make_client

CASE = "CP-CYBER-2026-001"
SEED = "0xa7f39c1d8e4b2a5f7c3d9e0a1b8c6d4e5f2a67e9"

client = make_client()


@pytest.fixture(scope="module")
def trail():
    r = client.get(f"/api/cases/{CASE}/conversions")
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- the answer

def test_it_finds_the_rupee_to_usdt_conversion(trail):
    """The question this engine exists for: the money left an SBI account in
    rupees and arrived on-chain as USDT. Where did that happen?"""
    c = next(x for x in trail["conversions"] if x["from_asset"] == "INR")
    assert c["to_asset"] == "USDT"
    assert c["amount_in"] == pytest.approx(470000.0)
    assert c["amount_out"] == pytest.approx(5200.0)
    assert c["node_type"] == "exchange"


def test_the_rate_is_derived_from_the_evidence(trail):
    """470000 / 5200 = 90.38, which is the locked demo rate - but it is
    computed from the two legs rather than read from a constant."""
    c = next(x for x in trail["conversions"] if x["from_asset"] == "INR")
    assert "90.38" in c["implied_rate"]
    assert "per USDT" in c["implied_rate"]


def test_the_rails_are_reported_in_the_order_travelled(trail):
    assert trail["rails_used"][0] == "bank_inr"
    assert "ethereum" in trail["rails_used"]


# ------------------------------------------------------------- the honesty

def test_a_conversion_is_only_as_good_as_its_weaker_leg(trail):
    """The rupee leg into the exchange is an INFERRED correlation. The USDT
    leg out is confirmed on-chain. Reporting the conversion as CONFIRMED would
    launder an inference into a proven fact."""
    c = next(x for x in trail["conversions"] if x["from_asset"] == "INR")
    assert c["basis"] == "INFERRED"


def test_no_company_is_ever_named(trail):
    """We hold a label, never a legal identity."""
    blob = str(trail).lower()
    for brand in ("binance", "wazirx", "coindcx", "kraken", "coinbase",
                  "zebpay", "bybit"):
        assert brand not in blob, brand


def test_the_caveat_says_the_rate_is_not_a_market_price(trail):
    c = trail["caveat"].lower()
    assert "not " in c and "market data source" in c
    assert "no company is named" in c


# -------------------------------------------------------------- the venues

def test_it_separates_who_can_be_served_from_who_cannot(trail):
    """A mixer is a contract - there is nobody holding records to produce. An
    exchange is a company that is. Confusing the two wastes an officer's
    time on an order that can never be answered."""
    kinds = {v["kind"]: v["can_be_compelled"] for v in trail["venues"]}
    assert kinds.get("exchange") is True
    assert kinds.get("bank_account") is True
    assert kinds.get("mixer") is False
    assert kinds.get("bridge") is False


def test_compellable_venues_are_listed_first(trail):
    """That end of the list is the actionable one, so it reads first."""
    flags = [v["can_be_compelled"] for v in trail["venues"]]
    assert flags == sorted(flags, reverse=True)


def test_a_compellable_venue_names_the_instrument(trail):
    v = next(x for x in trail["venues"] if x["kind"] == "exchange")
    assert "94 BNSS" in v["note"]


def test_a_contract_venue_says_there_is_nobody_to_serve(trail):
    v = next(x for x in trail["venues"] if x["kind"] == "mixer")
    assert "no operator" in v["note"].lower()


def test_an_unlabelled_venue_is_reported_as_unidentified():
    """Unlabelled is unknown, never clean - the same rule the label lookup
    follows."""
    a = analyse(CASE, SEED)
    for n in a.nodes:
        if n.node_type == NodeType.EXCHANGE:
            n.label = None
    t = conversion.build(CASE, a.nodes, a.edges)
    v = next(x for x in t.venues if x.kind == NodeType.EXCHANGE)
    assert v.identified is False
    assert "unknown, never clean" in v.note


# ---------------------------------------------------------- other case data

@pytest.mark.parametrize("case_id", ["CP-CYBER-2026-002", "CP-CYBER-2026-003",
                                     "CP-CYBER-2026-004"])
def test_every_case_reaches_a_venue_that_can_be_served(case_id):
    """If no case reached a compellable service, the production order would
    have nobody to address."""
    r = client.get(f"/api/cases/{case_id}/conversions")
    assert r.status_code == 200, r.text
    assert any(v["can_be_compelled"] for v in r.json()["venues"]), case_id


def test_the_chain_hopping_case_shows_more_than_one_rail():
    """Case 003 hops Ethereum to Tron on purpose."""
    r = client.get("/api/cases/CP-CYBER-2026-003/conversions")
    assert len(r.json()["rails_used"]) >= 2


def test_the_trail_writes_no_audit_row():
    before = len(client.get(f"/api/cases/{CASE}/audit").json())
    client.get(f"/api/cases/{CASE}/conversions")
    assert len(client.get(f"/api/cases/{CASE}/audit").json()) == before
