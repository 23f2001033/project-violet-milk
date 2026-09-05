"""
Risk Engine — seven deterministic rules.  Owner: BE2

No model, no training, no randomness. The same input always yields the same
score, which is the only property that survives a defence lawyer. Section 63
BSA 2023 requires explaining how electronic evidence was produced: arithmetic
can be explained to a court, a neural network cannot be cross-examined.

INVARIANT (locked by tests): the case seed wallet scores exactly 65 -
R1 + R2 + R3 + R4 = 20 + 15 + 15 + 15. R5 must NOT fire on the seed, which is
why the demo dataset gives it exactly five downstream addresses.
"""

from datetime import datetime, timezone

from ..models import (
    Confidence, Edge, Node, NodeType, RiskAssessment, RiskIndicator, RiskLevel,
)

RAPID_DISPERSAL_SECONDS = 240        # R2: under 4 minutes
FAN_OUT_THRESHOLD = 5                # R5: fires above this, not at it
TIME_CORRELATION_SECONDS = 900       # R7: within 15 minutes
STRUCTURING_MIN_COUNT = 3            # R6
STRUCTURING_BANDS = (10_000, 50_000, 100_000, 1_000_000)


def _ts(v: str) -> datetime:
    return datetime.fromisoformat(v)


def level_for(score: int) -> RiskLevel:
    if score >= 75:
        return RiskLevel.CRITICAL
    if score >= 50:
        return RiskLevel.HIGH
    if score >= 25:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _downstream_within(
    start: str, edges: list[Edge], hops: int, types: dict[str, NodeType],
    target: NodeType,
) -> str | None:
    """Breadth-first search downstream for a node of `target` type."""
    frontier, seen = {start}, {start}
    for _ in range(hops):
        nxt = set()
        for e in edges:
            if e.from_node in frontier and e.to_node not in seen:
                if types.get(e.to_node) == target:
                    return e.to_node
                seen.add(e.to_node)
                nxt.add(e.to_node)
        frontier = nxt
        if not frontier:
            break
    return None


def assess(
    case_id: str,
    node: Node,
    nodes: list[Node],
    edges: list[Edge],
    hop_depth: dict[str, int],
    illicit_ratio: dict[str, float],
    victim_debit_at: str | None = None,
) -> RiskAssessment:
    nid = node.node_id
    types = {n.node_id: n.node_type for n in nodes}
    inbound = [e for e in edges if e.to_node == nid]
    outbound = [e for e in edges if e.from_node == nid]
    ind: list[RiskIndicator] = []

    # -- R1  proximity to the seed cluster ---------------------------------
    depth = hop_depth.get(nid)
    r1_fired = depth is not None and depth <= 1
    if r1_fired:
        ind.append(RiskIndicator(
            rule_id="R1", name="Proximity to known scam cluster", points=20,
            evidence=f"hop_depth={depth}"
                     + (" (case seed address)" if depth == 0 else ""),
            confidence=Confidence.CONFIRMED,
        ))

    # -- R2  rapid dispersal after receipt ---------------------------------
    if inbound and outbound:
        first_in = min(_ts(e.timestamp) for e in inbound)
        after = [e for e in outbound if _ts(e.timestamp) > first_in]
        if after:
            first_out = min(after, key=lambda e: _ts(e.timestamp))
            delta = int((_ts(first_out.timestamp) - first_in).total_seconds())
            if delta < RAPID_DISPERSAL_SECONDS:
                ind.append(RiskIndicator(
                    rule_id="R2", name="Rapid automated dispersal", points=15,
                    evidence=(
                        f"received {first_in:%H:%M:%S}, first outbound "
                        f"{_ts(first_out.timestamp):%H:%M:%S} (+{delta // 60}m"
                        f"{delta % 60:02d}s) via {first_out.edge_id}"
                    ),
                    confidence=Confidence.CONFIRMED,
                ))

    # -- R3  mixer exposure -------------------------------------------------
    if node.node_type == NodeType.MIXER:
        ind.append(RiskIndicator(
            rule_id="R3", name="Mixer contract interaction", points=15,
            evidence=f"{nid} is a known mixer contract",
            confidence=Confidence.CONFIRMED,
        ))
    else:
        hit = next(
            (e for e in outbound if types.get(e.to_node) == NodeType.MIXER), None
        )
        if hit:
            ind.append(RiskIndicator(
                rule_id="R3", name="Mixer contract interaction", points=15,
                evidence=f"{hit.edge_id} -> {hit.to_node} "
                         f"({hit.amount:,.0f} {hit.asset.value})",
                confidence=Confidence.CONFIRMED,
            ))

    # -- R4  cross-chain bridge exposure ------------------------------------
    if node.node_type == NodeType.BRIDGE:
        ind.append(RiskIndicator(
            rule_id="R4", name="Cross-chain bridge exposure", points=15,
            evidence=f"{nid} is a cross-chain bridge contract",
            confidence=Confidence.CONFIRMED,
        ))
    else:
        bridge = _downstream_within(nid, edges, 2, types, NodeType.BRIDGE)
        if bridge:
            ind.append(RiskIndicator(
                rule_id="R4", name="Cross-chain bridge exposure", points=15,
                evidence=f"bridge {bridge} reached within 2 hops downstream",
                confidence=Confidence.INFERRED,
            ))

    # -- R5  fan-out --------------------------------------------------------
    downstream = {e.to_node for e in outbound}
    if len(downstream) > FAN_OUT_THRESHOLD:
        ind.append(RiskIndicator(
            rule_id="R5", name="Fan-out dispersal", points=10,
            evidence=f"{len(downstream)} distinct downstream addresses",
            confidence=Confidence.CONFIRMED,
        ))

    # -- R6  structuring ----------------------------------------------------
    for band in STRUCTURING_BANDS:
        near = [e for e in outbound if band * 0.90 <= e.amount < band]
        if len(near) >= STRUCTURING_MIN_COUNT:
            ind.append(RiskIndicator(
                rule_id="R6", name="Structuring below reporting threshold",
                points=10,
                evidence=f"{len(near)} transfers in [{band * 0.90:,.0f}, "
                         f"{band:,.0f}): "
                         + ", ".join(e.edge_id for e in near[:5]),
                confidence=Confidence.INFERRED,
            ))
            break

    # -- R7  time correlation with the victim's bank debit -------------------
    #
    # Deliberately suppressed when R1 already fired. For a node structurally
    # adjacent to the seed, "close in time" and "close in the graph" measure the
    # same underlying signal, and counting both double-charges the node for one
    # piece of evidence. R7 exists to catch wallets with NO structural link that
    # nonetheless correlate suspiciously in time - that is its whole
    # investigative purpose. This suppression is also what holds the seed at 65.
    if victim_debit_at and not r1_fired:
        debit = _ts(victim_debit_at)
        onchain_in = [e for e in inbound
                      if e.evidence_type.value == "confirmed_onchain"]
        for e in onchain_in:
            delta = abs((_ts(e.timestamp) - debit).total_seconds())
            if delta <= TIME_CORRELATION_SECONDS:
                ind.append(RiskIndicator(
                    rule_id="R7", name="Time correlation with victim debit",
                    points=15,
                    evidence=f"{e.edge_id} at {_ts(e.timestamp):%H:%M:%S}, "
                             f"{int(delta) // 60}m{int(delta) % 60:02d}s after "
                             f"UPI debit {debit:%H:%M:%S}",
                    confidence=Confidence.INFERRED,
                ))
                break

    score = max(0, min(100, sum(i.points for i in ind)))

    return RiskAssessment(
        node_id=nid,
        case_id=case_id,
        score=score,
        level=level_for(score),
        illicit_ratio=illicit_ratio.get(nid, 0.0),
        indicators=ind,
        computed_at=datetime.now(timezone.utc).isoformat(),
    )
