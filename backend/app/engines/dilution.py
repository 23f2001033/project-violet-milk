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


HAIRCUT_CAVEAT = (
    "Prior balances are drawn from curated case evidence, so each ratio is a "
    "true proportional haircut."
)
PROPAGATION_CAVEAT = (
    "PROPAGATION ONLY - NOT A DILUTION FIGURE. Historical balances at the "
    "moment funds arrived cannot be reconstructed from a public explorer, so "
    "the haircut denominator is unavailable. These values show how far traced "
    "funds REACHED, not what proportion of each wallet they represent. A "
    "wallet shown at 100% may hold far more untraced value."
)


def compute_dilution(
    case_id: str,
    nodes: list[Node],
    edges: list[Edge],
    origin_node: str | None = None,
    prior_balances_available: bool = True,
) -> tuple[DilutionResult, dict[str, float]]:
    """Replay the ledger chronologically.

    Two modes, and the distinction is not cosmetic:

    HAIRCUT (curated evidence) - every node carries a known prior balance, so
    the denominator is real and the output is a genuine proportion.

    PROPAGATION (live chain data) - a public explorer cannot tell us what a
    wallet held at the moment funds arrived. Historical balance reconstruction
    means replaying every prior transfer for every address, which the rate
    limits make impossible inside a trace. Rather than invent a denominator,
    the prior-balance term is dropped and the result is relabelled: it shows
    REACH, not proportion.

    Before this split existed, live mode silently produced 0.0 for every node
    - there was no victim to seed the taint from - so the headline feature
    quietly did nothing on real data.
    """
    balance = {
        n.node_id: (
            _norm(n.prior_balance,
                  Asset.INR if n.chain.value == "bank_inr" else Asset.USDT)
            if prior_balances_available else 0.0
        )
        for n in nodes
    }
    dirty = {n.node_id: 0.0 for n in nodes}
    ratio: dict[str, float] = {n.node_id: 0.0 for n in nodes}

    if origin_node is not None:
        origin = origin_node
    else:
        # Curated cases start at the complainant. A live trace has no victim
        # node at all, so the seed address becomes the origin of taint.
        origin = next(
            (n.node_id for n in nodes if n.node_type.value == "victim"), None
        )
        if origin is None:
            origin = next((n.node_id for n in nodes if n.is_seed), None)

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

    # The origin itself is fully traced by definition - it is the money the
    # complainant lost, or the address the investigator named.
    if origin:
        ratio.setdefault(origin, 0.0)
        if not prior_balances_available:
            ratio[origin] = 1.0

    result = DilutionResult(
        case_id=case_id,
        threshold=DILUTION_THRESHOLD,
        model="haircut" if prior_balances_available else "propagation",
        caveat=HAIRCUT_CAVEAT if prior_balances_available else PROPAGATION_CAVEAT,
        steps=steps,
        computed_at=datetime.now(timezone.utc).isoformat(),
    )
    return result, ratio
