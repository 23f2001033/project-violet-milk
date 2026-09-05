"""
Dilution Engine — proportional haircut.  Owner: BE2

    illicit_ratio = (incoming_amount x incoming_ratio) / (prior_balance + incoming_amount)

Two implementation details carry all the weight:

1. Propagation runs in STRICT TIMESTAMP ORDER, never graph order. A wallet's
   taint depends on what it held at the moment funds arrived, so replaying the
   ledger out of order silently produces wrong ratios.

2. A node's reported ratio is captured at its LAST INBOUND EVENT, not at the
   end of the run. A pass-through wallet ends with a zero balance, and 0/0 is
   not "clean" - it is undefined. The forensically meaningful number is what
   fraction of what this wallet RECEIVED was tainted.

Known limitation, to be volunteered before a judge raises it: the haircut model
can be gamed by padding a wallet with clean funds. FIFO, LIFO and poison/taint
trade off differently; poison over-flags catastrophically. We chose haircut
deliberately, to avoid false positives on legitimate liquidity.
"""

from datetime import datetime, timezone

from ..config import DEMO_INR_PER_USDT, DILUTION_THRESHOLD
from ..models import Asset, DilutionResult, DilutionStep, Edge, Node


def _norm(amount: float, asset: Asset) -> float:
    """Normalise to a single unit so the on-ramp does not corrupt the maths.

    The victim's INR leg and the wallet's USDT leg are the same money. Adding
    470000 to 5200 without conversion produces nonsense, so INR is converted at
    the locked demo rate before any ratio is computed. Display values keep their
    original units.
    """
    return amount / DEMO_INR_PER_USDT if asset == Asset.INR else amount


def compute_dilution(
    case_id: str,
    nodes: list[Node],
    edges: list[Edge],
    origin_node: str | None = None,
) -> tuple[DilutionResult, dict[str, float]]:
    """Replay the ledger chronologically.

    `origin_node` is where the taint enters - the victim. Funds leaving it are
    100% traced by definition. Returns the full result plus a
    {node_id: illicit_ratio} map for the risk engine and the graph payload.
    """
    balance = {n.node_id: _norm(n.prior_balance, Asset.INR
                                if n.chain.value == "bank_inr" else Asset.USDT)
               for n in nodes}
    dirty = {n.node_id: 0.0 for n in nodes}
    ratio: dict[str, float] = {n.node_id: 0.0 for n in nodes}

    if origin_node is None:
        origin = next((n.node_id for n in nodes if n.node_type.value == "victim"), None)
    else:
        origin = origin_node

    steps: list[DilutionStep] = []

    for e in sorted(edges, key=lambda x: x.timestamp):
        amt = _norm(e.amount, e.asset)
        src, dst = e.from_node, e.to_node

        if src == origin:
            incoming_ratio = 1.0            # stolen funds, traced by definition
        else:
            bal = balance.get(src, 0.0)
            incoming_ratio = (dirty.get(src, 0.0) / bal) if bal > 0 else 0.0

        moved_dirty = amt * incoming_ratio

        # debit the source (the origin is not itself tainted)
        if src != origin:
            balance[src] = max(0.0, balance.get(src, 0.0) - amt)
            dirty[src] = max(0.0, dirty.get(src, 0.0) - moved_dirty)
        else:
            balance[src] = max(0.0, balance.get(src, 0.0) - amt)

        prior = balance.get(dst, 0.0)
        balance[dst] = prior + amt
        dirty[dst] = dirty.get(dst, 0.0) + moved_dirty

        new_ratio = dirty[dst] / balance[dst] if balance[dst] > 0 else 0.0
        ratio[dst] = round(new_ratio, 4)

        steps.append(DilutionStep(
            node_id=dst,
            prior_balance=round(prior, 2),
            incoming_amount=round(amt, 2),
            incoming_ratio=round(incoming_ratio, 4),
            dirty_received=round(moved_dirty, 2),
            total_after=round(balance[dst], 2),
            illicit_ratio=round(new_ratio, 4),
            flagged=new_ratio >= DILUTION_THRESHOLD,
        ))

    result = DilutionResult(
        case_id=case_id,
        threshold=DILUTION_THRESHOLD,
        steps=steps,
        computed_at=datetime.now(timezone.utc).isoformat(),
    )
    return result, ratio
