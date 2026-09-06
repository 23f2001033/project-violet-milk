"""
Asset ledger — which currency moved, at which layer, and what it is in rupees.

Additive to the existing engines: nothing here feeds a risk score, a dilution
ratio or a dossier figure. It answers the question an investigating officer
actually asks first — "how much of what, and where did it change hands?"

THE HONESTY RULE IN THIS FILE
-----------------------------
Only INR and USDT are convertible, at the locked demo rate. This build carries
no price feed, so ETH, TRX and unverified tokens report native amounts with a
null rupee value rather than a number invented from a rate nobody sourced.
`dilution._norm()` treats non-INR assets as 1:1 with USDT for ratio purposes,
which is fine for a proportion of a single pool and would be wrong here, where
the figure could end up quoted as a rupee loss in a chargesheet.
"""

from datetime import datetime, timezone

from ..config import DEMO_INR_PER_USDT
from ..models import (
    Asset, AssetAmount, AssetBreakdown, Edge, LayerAssets, Node, NodeAssets,
)
from ..services.formatting import inr_group

# Assets this build can express in rupees. Everything else reports native
# units and a null rupee figure - see the module docstring.
CONVERTIBLE = (Asset.INR, Asset.USDT)

CAVEAT = (
    "Rupee equivalents are shown only for INR and USDT, converted at the "
    f"locked demo rate of INR {DEMO_INR_PER_USDT:.2f} per USDT. This build "
    "carries no market price feed, so ETH, TRX and unverified tokens report "
    "native amounts with no rupee value. An absent rupee figure means the "
    "rate is unknown, never that the amount is zero."
)


def _to_inr(amount: float, asset: Asset) -> float | None:
    if asset == Asset.INR:
        return amount
    if asset == Asset.USDT:
        return amount * DEMO_INR_PER_USDT
    return None


def _tally(edges: list[Edge]) -> list[AssetAmount]:
    """Collapse edges into one row per asset, largest rupee value first."""
    totals: dict[Asset, list[float]] = {}
    for e in edges:
        bucket = totals.setdefault(e.asset, [0.0, 0.0])
        bucket[0] += e.amount
        bucket[1] += 1

    rows = []
    for asset, (amount, count) in totals.items():
        inr = _to_inr(amount, asset)
        rows.append(AssetAmount(
            asset=asset,
            transfer_count=int(count),
            total_amount=round(amount, 8),
            inr_equivalent=round(inr, 2) if inr is not None else None,
            inr_formatted=inr_group(inr) if inr is not None else None,
            convertible=asset in CONVERTIBLE,
        ))

    # Convertible rows first and by value, so the rupee figures an officer
    # needs sit at the top; unpriced assets follow in a stable alphabetical
    # order rather than an arbitrary dict order.
    rows.sort(key=lambda r: (r.inr_equivalent is None,
                             -(r.inr_equivalent or 0.0), r.asset.value))
    return rows


def build(
    case_id: str,
    nodes: list[Node],
    edges: list[Edge],
    hop_depth: dict[str, int],
) -> AssetBreakdown:
    """Asset composition overall, per layer, and per entity.

    A transfer is counted at the hop depth of the node that RECEIVED it, so a
    layer reads as "what arrived here". An edge whose destination was never
    reached by the trace is skipped rather than guessed at.
    """
    by_id = {n.node_id: n for n in nodes}

    layers: dict[int, list[Edge]] = {}
    for e in edges:
        depth = hop_depth.get(e.to_node)
        if depth is None:
            continue
        layers.setdefault(depth, []).append(e)

    layer_rows = []
    for depth in sorted(layers):
        bucket = layers[depth]
        layer_rows.append(LayerAssets(
            depth=depth,
            node_count=len({e.to_node for e in bucket}),
            transfer_count=len(bucket),
            assets=_tally(bucket),
        ))

    node_rows = []
    for n in sorted(nodes, key=lambda x: (hop_depth.get(x.node_id, 99),
                                          x.node_id)):
        received = [e for e in edges if e.to_node == n.node_id]
        sent = [e for e in edges if e.from_node == n.node_id]
        if not received and not sent:
            continue
        node_rows.append(NodeAssets(
            node_id=n.node_id,
            depth=hop_depth.get(n.node_id, -1),
            node_type=n.node_type,
            label=n.label,
            received=_tally(received),
            sent=_tally(sent),
        ))

    return AssetBreakdown(
        case_id=case_id,
        computed_at=datetime.now(timezone.utc).isoformat(),
        inr_per_usdt=DEMO_INR_PER_USDT,
        convertible_assets=list(CONVERTIBLE),
        caveat=CAVEAT,
        totals=_tally(edges),
        layers=layer_rows,
        nodes=node_rows,
    )
