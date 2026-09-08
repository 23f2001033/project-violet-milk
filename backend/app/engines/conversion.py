"""
Conversion trail - where the money changed form, and whose hands it passed
through.

THE QUESTION THIS ANSWERS
-------------------------
"You have shown me it left the SBI account. Which platform did it go to, and
what did it become?"

The graph does not answer that on its own. It shows movement; it does not
separate the two things an officer actually needs to write down:

  * where value changed FORM - rupees became USDT, USDT became ether;
  * where value changed HANDS at a SERVICE - an exchange, a P2P trader, a
    bank, a mixer, a bridge.

The distinction matters because only the second kind can be compelled. A
mixer holds no customer record; an exchange does. So this engine reports both
and marks which is which.

WHAT IT REFUSES TO DO
---------------------
It never names a company. We hold an on-chain label at best, and a label is
not a legal identity - reporting "Binance" because an address resembles one
would be the single most damaging thing this system could do. An unlabelled
venue is reported as unidentified, with the instrument that WOULD identify it
named instead.

The implied rate is arithmetic on the two legs, not a sourced market price.
It is reported as "implied" for that reason.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..models import (
    Asset, Chain, ConversionPoint, ConversionTrail, Edge, Node, NodeType,
    VenueUse,
)

# Services that hold customer records and can therefore be served with a
# production order. A mixer or a bridge is a contract: there is nobody to ask.
COMPELLABLE = {NodeType.EXCHANGE, NodeType.BANK_ACCOUNT, NodeType.UPI_HANDLE}

VENUE_KINDS = COMPELLABLE | {NodeType.MIXER, NodeType.BRIDGE}

CAVEAT = (
    "Conversion rates here are implied by the two legs of the trade, not "
    "taken from a market data source. Venues are described by the type of "
    "service the evidence supports; no company is named, because an on-chain "
    "label is not a legal identity. Naming the operator of a venue requires "
    "the production order this system drafts."
)

NOTE_COMPELLABLE = (
    "Holds customer records. A Section 94 BNSS 2023 production order can "
    "compel KYC, the linked Indian bank account and the transaction history."
)
NOTE_CONTRACT = (
    "A contract, not a company. There is no operator holding records to "
    "produce, so the trail is followed through it rather than served on it."
)
NOTE_UNIDENTIFIED = (
    "No curated label backs this address, so the service behind it is not "
    "identified. Unlabelled is unknown, never clean."
)


def _sum_by_asset(edges: list[Edge]) -> dict[Asset, float]:
    out: dict[Asset, float] = {}
    for e in edges:
        out[e.asset] = out.get(e.asset, 0.0) + e.amount
    return out


def _rate(amount_in: float, amount_out: float,
          a_in: Asset, a_out: Asset) -> str | None:
    """The rate the two legs imply. Never invented when either side is zero."""
    if amount_in <= 0 or amount_out <= 0:
        return None
    if a_in == Asset.INR:
        return f"INR {amount_in / amount_out:,.2f} per {a_out.value}"
    if a_out == Asset.INR:
        return f"INR {amount_out / amount_in:,.2f} per {a_in.value}"
    return f"{amount_out / amount_in:,.6f} {a_out.value} per {a_in.value}"


def build(case_id: str, nodes: list[Node], edges: list[Edge]) -> ConversionTrail:
    by_id = {n.node_id: n for n in nodes}

    # Rails in order of first appearance, so the sequence reads the way the
    # money actually travelled: bank rails, then a chain.
    rails: list[str] = []
    for e in sorted(edges, key=lambda x: x.timestamp):
        for side in (e.from_node, e.to_node):
            node = by_id.get(side)
            if node and node.chain.value not in rails and node.chain != Chain.NONE:
                rails.append(node.chain.value)

    conversions: list[ConversionPoint] = []
    venues: list[VenueUse] = []

    for node in nodes:
        inbound = [e for e in edges if e.to_node == node.node_id]
        outbound = [e for e in edges if e.from_node == node.node_id]
        if not inbound or not outbound:
            continue

        got = _sum_by_asset(inbound)
        gave = _sum_by_asset(outbound)

        # A conversion is an asset arriving that does not leave. Matching the
        # largest of each side is the honest reading of a swap when the
        # evidence does not pair individual legs.
        incoming_only = {a: v for a, v in got.items() if a not in gave}
        outgoing_only = {a: v for a, v in gave.items() if a not in got}
        if incoming_only and outgoing_only:
            a_in = max(incoming_only, key=incoming_only.get)
            a_out = max(outgoing_only, key=outgoing_only.get)
            legs = [e for e in outbound if e.asset == a_out]
            # A conversion is only as good as its weaker leg.
            all_legs = [e for e in inbound if e.asset == a_in] + legs
            basis = ("CONFIRMED"
                     if all(e.evidence_type.value.startswith("confirmed")
                            for e in all_legs)
                     else "INFERRED")
            conversions.append(ConversionPoint(
                node_id=node.node_id,
                label=node.label,
                node_type=node.node_type,
                chain=node.chain,
                from_asset=a_in,
                to_asset=a_out,
                amount_in=round(incoming_only[a_in], 8),
                amount_out=round(outgoing_only[a_out], 8),
                implied_rate=_rate(incoming_only[a_in], outgoing_only[a_out],
                                   a_in, a_out),
                at=min(e.timestamp for e in legs),
                basis=basis,
            ))

    for node in nodes:
        if node.node_type not in VENUE_KINDS:
            continue
        touching = [e for e in edges
                    if node.node_id in (e.from_node, e.to_node)]
        if not touching:
            continue
        identified = bool(node.label)
        compellable = node.node_type in COMPELLABLE
        if not identified:
            note = NOTE_UNIDENTIFIED
        elif compellable:
            note = NOTE_COMPELLABLE
        else:
            note = NOTE_CONTRACT
        venues.append(VenueUse(
            node_id=node.node_id,
            label=node.label,
            kind=node.node_type,
            chain=node.chain,
            assets_handled=sorted({e.asset for e in touching},
                                  key=lambda a: a.value),
            transfers=len(touching),
            identified=identified,
            can_be_compelled=compellable,
            note=note,
        ))

    conversions.sort(key=lambda c: c.at)
    # Services that can be served come first: that is the actionable end.
    venues.sort(key=lambda v: (not v.can_be_compelled, v.kind.value, v.node_id))

    return ConversionTrail(
        case_id=case_id,
        computed_at=datetime.now(timezone.utc).isoformat(),
        rails_used=rails,
        conversions=conversions,
        venues=venues,
        caveat=CAVEAT,
    )
