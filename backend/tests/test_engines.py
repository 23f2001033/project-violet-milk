"""
Engine unit tests - Phase 2 acceptance gate.

test_api_contract.py proves the endpoints answer correctly. These prove the
engines are right for the right reasons, independently of HTTP.
"""

import pytest

from backend.app.engines.dilution import compute_dilution
from backend.app.engines.graph_engine import bounded_trace
from backend.app.engines.pipeline import analyse
from backend.app.engines.risk_engine import level_for
from backend.app.models import RiskLevel
from backend.app.sources.synthetic import SyntheticSource

CASE = "CP-CYBER-2026-001"
SEED = "0xa7f39c1d8e4b2a5f7c3d9e0a1b8c6d4e5f2a67e9"
W1 = "0x9c04a7e3b21d5f86c0a94e7d2b83f150c6ead21e"
W2 = "0x2d81b6f09c3a7e54d21b8f60a93c7e15d40b7f43"
POOL = "0xd90f42a17c58e03b96d1f47a20c85e39b7f481ab"
MIXER = "0x8589f2c47b1d0a63e95482f7ca1b3d6e0f4a0b6f"
VICTIM = "VICTIM_4471"


@pytest.fixture(scope="module")
def src():
    return SyntheticSource(CASE)


@pytest.fixture(scope="module")
def analysis():
    return analyse(CASE, SEED)


# --------------------------------------------------------------- datasource

def test_synthetic_source_is_not_live(src):
    assert src.is_live() is False
    assert src.source_name() == "SyntheticSource"


def test_get_transactions_returns_both_directions(src):
    """The seed both receives and sends; a one-directional query would miss
    half the evidence."""
    txs = src.get_transactions(SEED)
    assert any(t.to_node == SEED for t in txs)
    assert any(t.from_node == SEED for t in txs)


def test_unknown_address_has_no_label(src):
    assert src.get_label("0xdeadbeef") is None


# -------------------------------------------------------------- graph bounds

def test_full_trace_reaches_every_node(src):
    nodes, edges, hop, truncated = bounded_trace(
        src.all_nodes(), src.all_edges(), SEED, max_depth=3
    )
    assert len(nodes) == 14
    assert len(edges) == 17
    assert truncated is False
    assert hop[SEED] == 0


def test_depth_one_stops_at_immediate_neighbours(src):
    nodes, _, hop, _ = bounded_trace(
        src.all_nodes(), src.all_edges(), SEED, max_depth=1
    )
    assert max(hop.values()) == 1
    assert len(nodes) < 14


def test_min_amount_filter_sets_truncated(src):
    nodes, edges, _, truncated = bounded_trace(
        src.all_nodes(), src.all_edges(), SEED, max_depth=3, min_amount=1000
    )
    assert truncated is True, "clipping the graph must be reported, not hidden"
    assert all(e.amount >= 1000 for e in edges)


def test_max_edges_per_node_keeps_the_largest_flows(src):
    _, edges, _, truncated = bounded_trace(
        src.all_nodes(), src.all_edges(), SEED,
        max_depth=3, max_edges_per_node=2,
    )
    assert truncated is True
    assert len(edges) < 17


def test_unknown_seed_returns_empty(src):
    nodes, edges, hop, _ = bounded_trace(
        src.all_nodes(), src.all_edges(), "0xnotreal", max_depth=3
    )
    assert nodes == [] and edges == [] and hop == {}


def test_edges_come_back_in_chronological_order(src):
    _, edges, _, _ = bounded_trace(
        src.all_nodes(), src.all_edges(), SEED, max_depth=3
    )
    ts = [e.timestamp for e in edges]
    assert ts == sorted(ts)


# ------------------------------------------------------------------ dilution

def test_haircut_produces_the_locked_ratios(src):
    nodes, edges, _, _ = bounded_trace(
        src.all_nodes(), src.all_edges(), SEED, max_depth=3
    )
    _, ratios = compute_dilution(CASE, nodes, edges)

    assert ratios[SEED] == 1.0
    assert ratios[W2] == 0.60
    assert ratios[POOL] == 0.12          # the rescue
    assert ratios[VICTIM] == 0.0         # the victim is not tainted


def test_rescue_wallet_is_below_the_reporting_threshold(analysis):
    step = next(s for s in analysis.dilution.steps if s.node_id == POOL)
    assert step.illicit_ratio == 0.12
    assert step.flagged is False
    assert step.prior_balance == 8000.0
    assert step.incoming_ratio == 0.60


def test_pass_through_wallet_reports_receipt_ratio_not_zero(analysis):
    """The seed ends with a zero balance. 0/0 is undefined, not clean - the
    reported figure must be the ratio at its last inbound event."""
    assert analysis.illicit_ratio[SEED] == 1.0


def test_inr_leg_is_converted_before_ratios_are_computed(analysis):
    """Adding 470000 INR to 5200 USDT without conversion yields nonsense.
    If the on-ramp were mishandled the seed would not land on exactly 1.0."""
    assert analysis.illicit_ratio[SEED] == 1.0


# ---------------------------------------------------------------- risk rules

def test_seed_scores_exactly_sixty_five(analysis):
    r = analysis.risk[SEED]
    assert r.score == 65
    assert r.level == RiskLevel.HIGH
    assert {i.rule_id for i in r.indicators} == {"R1", "R2", "R3", "R4"}


def test_r5_does_not_fire_on_the_seed(analysis):
    """The seed has exactly 5 downstream addresses. R5 fires ABOVE 5, so it
    must stay silent here - this is what holds the score at 65."""
    assert "R5" not in {i.rule_id for i in analysis.risk[SEED].indicators}


def test_r5_fires_on_the_six_way_fan_out(analysis):
    rules = {i.rule_id for i in analysis.risk[W1].indicators}
    assert "R5" in rules
    assert analysis.risk[W1].score == 75
    assert analysis.risk[W1].level == RiskLevel.CRITICAL


def test_r7_is_suppressed_when_r1_fires(analysis):
    """Proximity and time-correlation measure the same signal for a node
    adjacent to the on-ramp. Counting both would double-charge one piece of
    evidence - and would push the seed to 80."""
    for nid, r in analysis.risk.items():
        rules = {i.rule_id for i in r.indicators}
        if "R1" in rules:
            assert "R7" not in rules, f"{nid} double-counts proximity"


def test_every_indicator_carries_evidence(analysis):
    for nid, r in analysis.risk.items():
        for ind in r.indicators:
            assert ind.evidence.strip(), f"{nid}/{ind.rule_id} has no evidence"


def test_scores_are_clamped_to_the_valid_band(analysis):
    for r in analysis.risk.values():
        assert 0 <= r.score <= 100


def test_mixer_node_self_identifies(analysis):
    rules = {i.rule_id for i in analysis.risk[MIXER].indicators}
    assert "R3" in rules


def test_victim_is_not_scored(analysis):
    assert analysis.risk[VICTIM].score == 0


@pytest.mark.parametrize("score,expected", [
    (0, RiskLevel.LOW), (24, RiskLevel.LOW),
    (25, RiskLevel.MEDIUM), (49, RiskLevel.MEDIUM),
    (50, RiskLevel.HIGH), (74, RiskLevel.HIGH),
    (75, RiskLevel.CRITICAL), (100, RiskLevel.CRITICAL),
])
def test_band_boundaries(score, expected):
    assert level_for(score) == expected


# ------------------------------------------------------------------ timeline

def test_timeline_deltas(analysis):
    tl = analysis.timeline
    assert len(tl) == 17
    assert tl[0].delta_seconds_prev == 0
    assert tl[1].delta_seconds_prev == 13     # the UPI -> exchange gap
    assert [e.timestamp for e in tl] == sorted(e.timestamp for e in tl)


def test_inferred_event_is_labelled_as_such(analysis):
    inferred = [e for e in analysis.timeline
                if e.event_type == "inferred_correlation"]
    assert len(inferred) == 1
    assert "INFERRED" in inferred[0].description


# ------------------------------------------------------------------ pipeline

def test_pipeline_reports_its_source(analysis):
    assert analysis.source_name == "SyntheticSource"
    assert analysis.is_live is False
    assert analysis.stats().nodes == 14
    assert analysis.stats().truncated is False


def test_graph_projection_is_cytoscape_shaped(analysis):
    g = analysis.graph()
    assert len(g.elements.nodes) == 14
    assert len(g.elements.edges) == 17
    seed = next(n.data for n in g.elements.nodes if n.data.is_seed)
    assert seed.risk_score == 65
    assert seed.illicit_ratio == 1.0


# --------------------------------------------------------------------- audit

def test_audit_ordering_is_offset_aware():
    """Regression: SQLite ORDER BY compares ISO timestamps as raw strings, so
    mixed UTC/IST offsets sort wrongly. Ordering must use parsed datetimes."""
    from datetime import datetime

    from backend.app.services.audit import for_case

    entries = for_case(CASE)
    parsed = [datetime.fromisoformat(e["timestamp"]) for e in entries]
    assert parsed == sorted(parsed)
