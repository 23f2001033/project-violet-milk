"""
Section 94 BNSS 2023 production order - DRAFT generator.  Owner: BE3

THE QUESTION THIS ANSWERS
-------------------------
"You have shown me a graph. What do I do with it on Monday morning?"

A wallet address is not a person. The only lawful route from a hex string to a
human being is the exchange that holds the KYC record, and the instrument that
compels it is a written order under Section 94 of the Bharatiya Nagarik
Suraksha Sanhita 2023 (the successor to Section 91 CrPC). Everything the trace
computed - which exchange received the funds, at which deposit address, in what
amount, at what time, under which transaction hash - is exactly the content
that order has to recite.

So this engine converts a finished trace into the draft of that order.

WHAT THIS IS NOT
----------------
It is not a signed order and it is not legal advice. A production order is
issued by a court or by an officer in charge of a police station under their
own authority and signature. Software can assemble the recitals; it cannot
confer the authority. Every field that depends on the issuing officer, the
station, or the legal identity of the addressee is emitted as an explicit
placeholder rather than invented, and every page is marked DRAFT.

The statutory wording here was drafted by the authors and has NOT been settled
by a legal practitioner. It is a starting point for an officer and their legal
advisor, not a form to be signed as-is.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from ..config import REPORTS_DIR
from ..models import Asset, NodeType
from ..services.formatting import inr_group
from .pipeline import CaseAnalysis
from .report_engine import (
    CRIT, MUTED, RULE, S_BODY, S_H, S_MONO, S_SMALL, S_TITLE, _cell, _table,
)

TO_COMPLETE = "[TO BE COMPLETED BY THE ISSUING OFFICER]"
ADDRESSEE_TO_COMPLETE = "[LEGAL NAME AND REGISTERED ADDRESS OF THE ENTITY]"

# What is actually worth asking a virtual asset service provider for. Ordered
# the way an investigating officer needs them: identity first, then the money,
# then the technical trail that corroborates both.
RECORDS_SOUGHT = [
    "Complete Know Your Customer records for the account which controls or "
    "received funds at the deposit address specified in the Schedule, "
    "including name, permanent account number, Aadhaar or other identity "
    "document relied upon, address, electronic mail address and mobile "
    "number as recorded at the time of onboarding and as presently held.",

    "Account opening date, current status of the account, and the record of "
    "any customer due diligence, enhanced due diligence or internal alert "
    "raised against it.",

    "Complete transaction statement for the account for the period specified "
    "in the Schedule, including deposits, withdrawals, trades and internal "
    "transfers, with the corresponding blockchain transaction identifiers.",

    "Particulars of every Indian bank account, Unified Payments Interface "
    "handle or other payment instrument linked to the account, together with "
    "the record of funds moved to or from those instruments.",

    "Internet Protocol address logs, device identifiers and session logs for "
    "account creation and for each transaction specified in the Schedule, "
    "with timestamps recorded in Indian Standard Time or with the applicable "
    "offset stated.",

    "Details of any freeze, hold, or restriction presently operating on the "
    "account, and confirmation of whether the balance traceable to the "
    "transactions in the Schedule remains available.",
]


def _reference(case_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"BNSS94-DRAFT-{case_id}-{stamp}"


def identify_addressee(analysis: CaseAnalysis) -> dict[str, Any] | None:
    """Pick the entity a production order should actually be served on.

    An exchange is the only node in a trace that is compelled to hold a KYC
    record, so it is the sole useful addressee. Where the trace found more
    than one, the one that received the most tainted value is chosen - that
    is where the largest recoverable amount sits.

    Returns None when the trace reached no exchange at all. That is a real
    outcome and must be reported as such: an order cannot be drafted against
    an entity that was never identified.
    """
    exchanges = [n for n in analysis.nodes if n.node_type == NodeType.EXCHANGE]
    if not exchanges:
        return None

    ratio = {s.node_id: s.illicit_ratio for s in analysis.dilution.steps}

    scored = []
    for node in exchanges:
        inbound = [e for e in analysis.edges if e.to_node == node.node_id]
        # Rank on tainted value, not gross value: a large clean inflow does
        # not make an address the right one to serve an order about.
        weight = sum(e.amount for e in inbound) * ratio.get(node.node_id, 0.0)
        scored.append((weight, len(inbound), node, inbound))

    scored.sort(key=lambda t: (-t[0], -t[1], t[2].node_id))
    _, _, node, inbound = scored[0]
    outbound = [e for e in analysis.edges if e.from_node == node.node_id]

    return {
        "node": node,
        "inbound": inbound,
        # The onward leg matters as much as the deposit. On the demo case the
        # only inbound edge is the INFERRED bank-to-exchange correlation; the
        # confirmed on-chain evidence is the withdrawal that followed. An
        # order reciting the inference alone would rest on our weakest link.
        "outbound": outbound,
        "illicit_ratio": ratio.get(node.node_id, 0.0),
    }


def build_fields(analysis: CaseAnalysis, case: dict) -> dict[str, Any]:
    """The order's field set as structured data, so it can be inspected."""
    target = identify_addressee(analysis)
    case_id = case["case_id"]

    schedule = []
    if target:
        legs = ([("RECEIVED BY", e) for e in target["inbound"]]
                + [("SENT BY", e) for e in target["outbound"]])
        for direction, e in sorted(legs, key=lambda t: t[1].timestamp):
            confirmed = e.evidence_type.value.startswith("confirmed")
            schedule.append({
                "direction": direction,
                "timestamp_ist": e.timestamp,
                "deposit_address": e.to_node,
                "sending_address": e.from_node,
                "counterparty": e.from_node if direction == "RECEIVED BY"
                                else e.to_node,
                "amount": f"{e.amount:,.2f} {e.asset.value}",
                "transaction_hash": e.tx_hash or "not recorded",
                "block_number": e.block_number,
                "evidence": e.evidence_type.value,
                # Spelled out because an officer reading the Schedule must be
                # able to see, without decoding a field name, which lines a
                # defence will contest.
                "basis": "CONFIRMED" if confirmed else "INFERRED",
            })

    return {
        "case_reference": case_id,
        "fir_reference": case.get("fir_ref") or TO_COMPLETE,
        "ncrp_reference": case.get("ncrp_ref") or "not recorded",
        "issuing_officer": TO_COMPLETE,
        "designation": TO_COMPLETE,
        "police_station": TO_COMPLETE,
        "addressee_legal_name": ADDRESSEE_TO_COMPLETE,
        "addressee_observed_label": (
            target["node"].label if target else "NO EXCHANGE IDENTIFIED"
        ),
        "addressee_address_on_chain": target["node"].node_id if target else None,
        "attribution_basis": (
            target["node"].label_source.value if target else "none"
        ),
        "amount_reported_by_complainant": inr_group(
            case.get("victim_amount_inr") or 0),
        "illicit_share_at_addressee": (
            f"{round(target['illicit_ratio'] * 100)}%" if target else "n/a"
        ),
        "records_sought": RECORDS_SOUGHT,
        "schedule": schedule,
        "statutory_basis": (
            "Section 94 of the Bharatiya Nagarik Suraksha Sanhita 2023"
        ),
        "issuing_authority": (
            "Section 94(1) BNSS 2023 empowers a Court, or an officer in "
            "charge of a police station, to require production of a document "
            "or thing considered necessary for an investigation. This draft "
            "must therefore be issued under the hand of an officer competent "
            "to do so; software cannot confer that authority."
        ),
        "limitations": [
            "This is an unsigned draft. It has no legal effect until issued "
            "and signed by an officer competent to do so.",
            "The statutory wording has not been settled by a legal "
            "practitioner and must be reviewed before issue.",
            "The addressee has been identified from an on-chain address "
            "label, not from a legal filing. Its legal name and registered "
            "address must be established independently before service.",
            "Where the addressee is incorporated outside India, service may "
            "require a mutual legal assistance request rather than a "
            "production order.",
            "Nothing in this document is a finding that any person has "
            "committed an offence.",
        ],
    }


def build_notice_document(
    analysis: CaseAnalysis, case: dict, out_dir: Path | None = None
) -> tuple[Path, str, dict[str, Any], str]:
    """Render the draft production order. Returns (path, sha256, fields, ref)."""
    out_dir = out_dir or REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    fields = build_fields(analysis, case)
    reference = _reference(case["case_id"])
    path = out_dir / f"{reference}.pdf"

    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title=f"DRAFT Sec 94 BNSS production order - {case['case_id']}",
        author="Project Violet Milk",
    )

    def chrome(canvas, d):
        canvas.saveState()
        w, h = A4
        canvas.setFillColor(CRIT)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(20 * mm, h - 12 * mm, "DRAFT - UNSIGNED - NO LEGAL EFFECT")
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.drawRightString(w - 20 * mm, h - 12 * mm, reference)
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(20 * mm, h - 14 * mm, w - 20 * mm, h - 14 * mm)
        canvas.line(20 * mm, 15 * mm, w - 20 * mm, 15 * mm)
        canvas.setFont("Helvetica", 6.4)
        canvas.drawString(
            20 * mm, 11 * mm,
            "Draft assembled from a traced case. Must be reviewed, completed "
            "and signed by an officer competent to issue it.")
        canvas.drawRightString(w - 20 * mm, 11 * mm, f"Page {d.page}")
        canvas.restoreState()

    story: list = []
    story.append(Paragraph("ORDER FOR PRODUCTION OF DOCUMENTS", S_TITLE))
    story.append(Paragraph(
        "Under Section 94 of the Bharatiya Nagarik Suraksha Sanhita, 2023 "
        "&mdash; <b>DRAFT for review and signature</b>", S_SMALL))
    story.append(Spacer(1, 5 * mm))

    story.append(_table([
        [_cell("Case reference"), Paragraph(fields["case_reference"], S_MONO)],
        [_cell("FIR"), Paragraph(fields["fir_reference"], S_MONO)],
        [_cell("NCRP acknowledgement"),
         Paragraph(fields["ncrp_reference"], S_MONO)],
        [_cell("Issuing officer"), Paragraph(fields["issuing_officer"], S_BODY)],
        [_cell("Designation"), Paragraph(fields["designation"], S_BODY)],
        [_cell("Police station"), Paragraph(fields["police_station"], S_BODY)],
    ], widths=[52 * mm, None]))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("To", S_H))
    story.append(_table([
        [_cell("Addressee"),
         Paragraph(fields["addressee_legal_name"], S_BODY)],
        [_cell("Identified in trace as"),
         Paragraph(fields["addressee_observed_label"] or "unlabelled", S_BODY)],
        [_cell("On-chain address"),
         Paragraph(fields["addressee_address_on_chain"] or
                   "no exchange identified in this trace", S_MONO)],
        [_cell("Attribution basis"),
         Paragraph(fields["attribution_basis"], S_MONO)],
    ], widths=[52 * mm, None]))
    story.append(Spacer(1, 4 * mm))

    if not fields["addressee_address_on_chain"]:
        story.append(Paragraph(
            "<b>This trace reached no exchange, so this order should not be "
            "issued.</b> A production order under Section 94 compels a person "
            "to produce records. Where funds rest in an unhosted address or "
            "pass through a contract such as a mixer or a bridge, there is no "
            "custodian holding records and no operator to serve: an order "
            "would ask nobody for nothing, and the weeks spent discovering "
            "that are weeks the trail goes cold.", S_BODY))
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(
            "The appropriate steps instead are to refer the terminal addresses "
            "as an FIU-IND lead and for blockchain-analytics attribution, to "
            "place them under monitoring so that a production order becomes "
            "possible the moment the funds reach a hosted service, and to "
            "re-seed a fresh trace from any address the traversal stopped at "
            "rather than treating a bound as an ending. The Asset Ledger "
            "screen lists each terminal address with which of these applies.",
            S_BODY))

    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Authority to issue", S_H))
    story.append(Paragraph(fields["issuing_authority"], S_BODY))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Grounds", S_H))
    story.append(Paragraph(
        f"An offence is under investigation in the above case. The "
        f"complainant reports a loss of INR "
        f"{fields['amount_reported_by_complainant']}. Analysis of bank records "
        f"and public blockchain records indicates that funds traceable to the "
        f"complainant were transferred to a deposit address controlled by the "
        f"addressee, as particularised in the Schedule below. The proportion "
        f"of value at that address traceable to the complainant is assessed at "
        f"{fields['illicit_share_at_addressee']}. The documents sought are "
        f"necessary for the purposes of this investigation.", S_BODY))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Documents and records required", S_H))
    for idx, item in enumerate(fields["records_sought"], start=1):
        story.append(Paragraph(f"<b>{idx}.</b>&nbsp;&nbsp;{item}", S_BODY))
        story.append(Spacer(1, 1.6 * mm))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("Schedule &mdash; transactions relied upon", S_H))
    if fields["schedule"]:
        story.append(Paragraph(
            "Lines marked INFERRED rest on a timing correlation between "
            "records, not on a single proven transfer, and are identified as "
            "such so that the distinction is on the face of this order.",
            S_SMALL))
        story.append(Spacer(1, 2 * mm))
        rows = [[_cell("Time (IST)"), _cell("Direction"), _cell("Amount"),
                 _cell("Counterparty"), _cell("Transaction hash"),
                 _cell("Basis")]]
        for s in fields["schedule"]:
            rows.append([
                Paragraph(s["timestamp_ist"], S_MONO),
                Paragraph(s["direction"], S_MONO),
                Paragraph(s["amount"], S_MONO),
                Paragraph(s["counterparty"], S_MONO),
                Paragraph(s["transaction_hash"], S_MONO),
                Paragraph(s["basis"], S_MONO),
            ])
        story.append(_table(rows, widths=[26 * mm, 20 * mm, 24 * mm, 34 * mm,
                                          None, 18 * mm]))
    else:
        story.append(Paragraph("No qualifying transactions were identified.",
                               S_BODY))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("Limitations of this draft", S_H))
    for idx, lim in enumerate(fields["limitations"], start=1):
        story.append(Paragraph(f"<b>{idx}.</b>&nbsp;&nbsp;{lim}", S_BODY))
        story.append(Spacer(1, 1.4 * mm))
    story.append(Spacer(1, 8 * mm))

    story.append(_table([
        [_cell("Signature"), Paragraph("&nbsp;", S_BODY)],
        [_cell("Name and designation"), Paragraph(TO_COMPLETE, S_BODY)],
        [_cell("Date and place"), Paragraph(TO_COMPLETE, S_BODY)],
        [_cell("Office seal"), Paragraph("&nbsp;", S_BODY)],
    ], widths=[52 * mm, None]))

    doc.build(story, onFirstPage=chrome, onLaterPages=chrome)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, digest, fields, reference
