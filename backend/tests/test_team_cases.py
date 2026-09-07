"""
Per-officer demonstration cases.

Four officers, four different graphs. The properties that matter:

  * case 001 is UNCHANGED - it is the locked dataset the integrity tests
    assert, and adding cases must not disturb it;
  * each case reads its OWN data, which is the bug this feature exists to fix
    (SyntheticSource cached one global pair of CSVs, so every case saw the
    same graph);
  * the four cases genuinely differ - if they all scored the same, showing
    four of them proves nothing about the scoring.
"""

import pytest

from backend.app.engines.pipeline import analyse
from backend.app.sources.synthetic import SyntheticSource

from ._client import make_client

client = make_client()

LOCKED = "CP-CYBER-2026-001"
TEAM = ["CP-CYBER-2026-002", "CP-CYBER-2026-003", "CP-CYBER-2026-004"]


def _case(case_id: str) -> dict:
    r = client.get(f"/api/cases/{case_id}")
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------- isolation

def test_the_locked_case_is_untouched():
    """The integrity suite asserts 14 nodes and 17 edges. Adding cases must
    not move them."""
    a = analyse(LOCKED, _case(LOCKED)["seed_wallet"])
    assert len(a.nodes) == 14
    assert len(a.edges) == 17


def test_each_case_reads_its_own_dataset():
    """THE regression. SyntheticSource cached one global pair of CSVs with
    maxsize=1, so the case_id it was handed made no difference and every
    officer saw the identical graph."""
    seen = {}
    for cid in [LOCKED] + TEAM:
        nodes = {n.node_id for n in SyntheticSource(cid).all_nodes()}
        assert nodes, cid
        seen[cid] = nodes

    ids = list(seen)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            assert seen[a] != seen[b], f"{a} and {b} share a dataset"


def test_every_officer_owns_exactly_one_case():
    cases = client.get("/api/cases").json()
    owners = [c["io_name"] for c in cases]
    for uid in ("IO_SHARMA", "DEMO_2", "DEMO_3", "DEMO_4"):
        assert owners.count(uid) == 1, uid


# --------------------------------------------------------------- variety

@pytest.mark.parametrize("case_id", TEAM)
def test_a_team_case_traces_and_scores(case_id):
    case = _case(case_id)
    a = analyse(case_id, case["seed_wallet"], max_depth=3)
    assert a.nodes and a.edges
    assert case["seed_wallet"] in a.risk


def test_the_four_cases_do_not_all_score_alike():
    """Four identical scores would prove nothing. The spread is the point:
    CRITICAL, HIGH, HIGH and LOW across the set."""
    scores = {}
    for cid in [LOCKED] + TEAM:
        case = _case(cid)
        a = analyse(cid, case["seed_wallet"], max_depth=3)
        scores[cid] = a.risk[case["seed_wallet"]].score
    assert len(set(scores.values())) >= 3, scores
    assert max(scores.values()) >= 75, "one case should reach CRITICAL"
    assert min(scores.values()) <= 25, "one case should stay LOW"


def test_the_complex_cases_carry_more_than_one_chain_or_asset():
    """Case 002 moves on Tron and 003 hops chains. A single-asset graph would
    not exercise the cross-asset ranking or the rupee conversion rules."""
    from backend.app.engines import assets as assets_engine

    for cid in ("CP-CYBER-2026-002", "CP-CYBER-2026-003"):
        case = _case(cid)
        a = analyse(cid, case["seed_wallet"], max_depth=3)
        led = assets_engine.build(cid, a.nodes, a.edges, a.hop_depth)
        assert len(led.totals) >= 2, cid
        assert len(led.layers) >= 3, cid


def test_the_short_case_really_is_short():
    """004 exists to show a trail that resolves. If it grows into a maze it
    has stopped making its point."""
    case = _case("CP-CYBER-2026-004")
    a = analyse("CP-CYBER-2026-004", case["seed_wallet"], max_depth=3)
    assert len(a.nodes) <= 12


# ------------------------------------------------------------- provenance

@pytest.mark.parametrize("case_id", TEAM)
def test_every_case_separates_confirmed_from_inferred(case_id):
    """The distinction the whole project rests on has to hold in every
    dataset, not only in the one that gets demonstrated."""
    case = _case(case_id)
    a = analyse(case_id, case["seed_wallet"], max_depth=3)
    kinds = {e.evidence_type.value for e in a.edges}
    assert "inferred_correlation" in kinds, case_id
    assert any(k.startswith("confirmed") for k in kinds), case_id


@pytest.mark.parametrize("case_id", TEAM)
def test_a_production_order_can_be_drafted(case_id):
    """Each case must reach an exchange, or the whole 'what do I do on
    Monday' answer does not apply to it."""
    from backend.app.engines import notice_engine

    case = _case(case_id)
    a = analyse(case_id, case["seed_wallet"], max_depth=3)
    assert notice_engine.identify_addressee(a) is not None, case_id


@pytest.mark.parametrize("case_id", TEAM)
def test_transaction_hashes_are_well_formed(case_id):
    import re

    case = _case(case_id)
    a = analyse(case_id, case["seed_wallet"], max_depth=3)
    for e in a.edges:
        if e.tx_hash:
            assert re.fullmatch(r"0x[0-9a-f]{64}", e.tx_hash), e.edge_id


# --------------------------------------------------- dilution origin fallback

def test_a_seed_whose_complainants_are_out_of_bounds_is_still_traced():
    """THE regression this fix exists for.

    Case 002 puts a mule network four hops between the complainants and the
    wallet under investigation, so the depth-3 bound truncates every victim
    out. Dilution then had no origin, tainted nothing, and reported a seed
    scoring 75/CRITICAL as 0% traced funds - a contradiction on the same
    screen. The seed IS the money under investigation when no complainant is
    in the traced set.
    """
    case = _case("CP-CYBER-2026-002")
    a = analyse(case["case_id"], case["seed_wallet"], max_depth=3)

    assert not [n for n in a.nodes if n.node_type.value == "victim"], (
        "this test is meaningless if the victims are inside the bound")

    seed = next(n.data for n in a.graph().elements.nodes
                if n.data.id == case["seed_wallet"])
    assert seed.illicit_ratio == 1.0


def test_a_complainant_is_never_marked_tainted():
    """The rule cuts the other way too. Where the complainant IS in the traced
    set they are the origin, and their own account is not itself illicit -
    the taint begins with what leaves it. Marking a victim 100% illicit would
    be both wrong and offensive."""
    for cid in (LOCKED, "CP-CYBER-2026-003"):
        case = _case(cid)
        a = analyse(cid, case["seed_wallet"], max_depth=3)
        victims = [n.data for n in a.graph().elements.nodes
                   if n.data.type.value == "victim"]
        assert victims, cid
        for v in victims:
            assert v.illicit_ratio == 0.0, f"{cid}: {v.id}"


def test_the_locked_dilution_figures_did_not_move():
    """60% to 12% is asserted in the deck, the README and the explainer PDF."""
    case = _case(LOCKED)
    a = analyse(LOCKED, case["seed_wallet"])
    ratios = sorted({round(s.illicit_ratio, 2) for s in a.dilution.steps})
    assert 0.6 in ratios and 0.12 in ratios, ratios
