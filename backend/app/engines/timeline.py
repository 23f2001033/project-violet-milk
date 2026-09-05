"""Timeline Engine — chronological reconstruction.  Owner: BE2

Police evaluate a case sequentially. The time deltas are the point: a 13-second
gap between a UPI debit and an exchange deposit is the finding, not decoration.
"""

from datetime import datetime

from ..models import Edge, Node, TimelineEvent

_SOURCE = {
    "confirmed_bank": "bank",
    "inferred_correlation": "bank",
    "confirmed_onchain": "onchain",
}


def build_timeline(
    case_id: str, nodes: list[Node], edges: list[Edge]
) -> list[TimelineEvent]:
    labels = {n.node_id: (n.label or n.node_id) for n in nodes}
    ordered = sorted(edges, key=lambda e: e.timestamp)

    events: list[TimelineEvent] = []
    prev: datetime | None = None

    for e in ordered:
        ts = datetime.fromisoformat(e.timestamp)
        delta = int((ts - prev).total_seconds()) if prev else 0

        if e.evidence_type.value == "inferred_correlation":
            desc = (f"Correlated deposit detected at {labels.get(e.to_node)} "
                    f"(INFERRED - not a proven transfer)")
        elif e.asset.value == "INR":
            desc = (f"UPI/bank transfer of INR {e.amount:,.0f} to "
                    f"{labels.get(e.to_node)}")
        else:
            desc = (f"{labels.get(e.to_node)} receives {e.amount:,.0f} "
                    f"{e.asset.value}")

        events.append(TimelineEvent(
            event_id=f"EV-{e.edge_id}",
            case_id=case_id,
            timestamp=e.timestamp,
            event_type=e.evidence_type.value,
            description=desc,
            node_id=e.to_node,
            edge_id=e.edge_id,
            delta_seconds_prev=delta,
            source=_SOURCE.get(e.evidence_type.value, "system"),
        ))
        prev = ts

    return events
