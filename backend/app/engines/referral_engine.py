"""
Internal referral note for addresses that cannot be served.  Owner: BE3

WHY THIS EXISTS
---------------
The Section 94 production order answers "who received this money" when the
money reached a service that holds records. It answers nothing when the trail
ends at an unhosted key or passes through a contract, and an officer who
serves one anyway loses weeks finding that out.

Those addresses still need to go somewhere. This produces the internal note
that sends them there: a referral for FIU-IND lead purposes and for
blockchain-analytics attribution, plus the monitoring position, listing each
terminal address with the reason it cannot be compelled.

WHAT THIS IS NOT
----------------
It is NOT a statutory instrument. Unlike the Section 94 order and the Section
63 certificate, no provision prescribes its form, and inventing a legal basis
for an internal memo would undo the discipline that makes the other documents
credible. So it recites no authority, compels nobody, and says on every page
that it is an internal working note.

It is also not a filing. Nothing here is transmitted to FIU-IND or to anyone
else; a referral is made by an officer through their own chain, and the same
rule that forbids an STR-filing endpoint applies to this.
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
from .conversion import build as build_trail
from .pipeline import CaseAnalysis
from .report_engine import (
    CRIT, MUTED, RULE, S_BODY, S_H, S_MONO, S_SMALL, S_TITLE, _cell, _table,
)

TO_COMPLETE = "[TO BE COMPLETED BY THE REFERRING OFFICER]"

DISPOSITION_LABEL = {
    "unhosted": "Terminal unhosted address",
    "pass_through_contract": "Pass-through contract",
    "bounds_reached": "Traversal bound - not established as terminal",
}

WHY_NOT_SERVEABLE = {
    "unhosted": ("No custodian holds this key, so there is no person on whom a "
                 "production order can be served."),
    "pass_through_contract": ("An address with no operator. A production order "
                              "would ask nobody for nothing."),
    "bounds_reached": ("The trace stopped here at its depth bound. This address "
                       "is not established as an endpoint and should be "
                       "re-traced before any conclusion is drawn."),
}

ROUTES = [
    ("FIU-IND lead referral",
     "Refer the addresses in the Schedule through the established channel so "
     "they can be matched against reporting-entity data. This note is not a "
     "Suspicious Transaction Report and does not discharge any reporting "
     "obligation; that obligation rests on a registered reporting entity."),
    ("Blockchain-analytics attribution",
     "Where a commercial attribution service is available to the unit, submit "
     "the addresses for ownership attribution. This system carries a small "
     "curated label set and does not attempt attribution at scale."),
    ("Monitoring",
     "Place the addresses under periodic re-trace. An unhosted address becomes "
     "compellable the moment its funds reach a hosted service, and that "
     "movement is the trigger for a Section 94 BNSS 2023 production order."),
]


def _reference(case_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"REFERRAL-{case_id}-{stamp}"


def build_fields(analysis: CaseAnalysis, case: dict) -> dict[str, Any]:
    trail = build_trail(case["case_id"], analysis.nodes, analysis.edges,
                        analysis.hop_depth)

    addresses = [{
        "address": t.node_id,
        "label": t.label,
        "type": t.node_type.value,
        "chain": t.chain.value,
        "amount_received": t.amount_received,
        "assets": [a.value for a in t.assets],
        "disposition": t.disposition,
        "disposition_label": DISPOSITION_LABEL[t.disposition],
        "why_not_serveable": WHY_NOT_SERVEABLE[t.disposition],
    } for t in trail.terminal_addresses]

    return {
        "case_reference": case["case_id"],
        "fir_reference": case.get("fir_ref") or TO_COMPLETE,
        "ncrp_reference": case.get("ncrp_ref") or "not recorded",
        "referring_officer": TO_COMPLETE,
        "designation": TO_COMPLETE,
        "police_station": TO_COMPLETE,
        "instrument_type": "Internal working note - not a statutory instrument",
        "addresses": addresses,
        "routes": [{"route": r, "detail": d} for r, d in ROUTES],
        "limitations": [
            "This note recites no statutory authority and compels nobody. No "
            "provision prescribes its form.",
            "Nothing here has been transmitted. A referral is made by an "
            "officer through their own chain, and this software does not send "
            "it.",
            "The addresses listed are those the trace could not attribute to a "
            "service holding customer records. An address appearing here is "
            "not thereby innocent, and is not thereby criminal.",
            "No company or operator is named anywhere in this note. An "
            "on-chain label is not a legal identity.",
        ],
    }


def build_referral_document(
    analysis: CaseAnalysis, case: dict, out_dir: Path | None = None
) -> tuple[Path, str, dict[str, Any], str]:
    """Render the internal referral note. Returns (path, sha256, fields, ref)."""
    out_dir = out_dir or REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    fields = build_fields(analysis, case)
    reference = _reference(case["case_id"])
    path = out_dir / f"{reference}.pdf"

    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title=f"Internal referral note - {case['case_id']}",
        author="Project Violet Milk",
    )

    def chrome(canvas, d):
        canvas.saveState()
        w, h = A4
        canvas.setFillColor(CRIT)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(20 * mm, h - 12 * mm,
                          "INTERNAL WORKING NOTE - NOT A STATUTORY INSTRUMENT")
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.drawRightString(w - 20 * mm, h - 12 * mm, reference)
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(20 * mm, h - 14 * mm, w - 20 * mm, h - 14 * mm)
        canvas.line(20 * mm, 15 * mm, w - 20 * mm, 15 * mm)
        canvas.setFont("Helvetica", 6.4)
        canvas.drawString(20 * mm, 11 * mm,
                          "Compels nobody. Transmitted to nobody. For referral "
                          "and monitoring within the investigating unit.")
        canvas.drawRightString(w - 20 * mm, 11 * mm, f"Page {d.page}")
        canvas.restoreState()

    story: list = []
    story.append(Paragraph("INTERNAL REFERRAL NOTE", S_TITLE))
    story.append(Paragraph(
        "Addresses that cannot be served with a production order", S_SMALL))
    story.append(Spacer(1, 5 * mm))

    story.append(_table([
        [_cell("Case reference"), Paragraph(fields["case_reference"], S_MONO)],
        [_cell("FIR"), Paragraph(fields["fir_reference"], S_MONO)],
        [_cell("NCRP acknowledgement"),
         Paragraph(fields["ncrp_reference"], S_MONO)],
        [_cell("Referring officer"),
         Paragraph(fields["referring_officer"], S_BODY)],
        [_cell("Designation"), Paragraph(fields["designation"], S_BODY)],
        [_cell("Police station"), Paragraph(fields["police_station"], S_BODY)],
        [_cell("Instrument"), Paragraph(fields["instrument_type"], S_BODY)],
    ], widths=[52 * mm, None]))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("Purpose", S_H))
    story.append(Paragraph(
        "A production order under Section 94 BNSS 2023 compels a person to "
        "produce records. The addresses in the Schedule below are those the "
        "trace reached but could not attribute to any service holding customer "
        "records - either because no custodian holds the key, or because the "
        "address is a contract with no operator. An order served on them would "
        "ask nobody for nothing.", S_BODY))
    story.append(Paragraph(
        "They are recorded here so that they are referred and monitored rather "
        "than abandoned, and so that no officer spends weeks discovering that "
        "an order against them cannot be answered.", S_BODY))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Schedule - addresses not amenable to a production "
                           "order", S_H))
    if fields["addresses"]:
        rows = [[_cell("Address"), _cell("Chain"), _cell("Received"),
                 _cell("Disposition")]]
        for a in fields["addresses"]:
            amount = (f"{a['amount_received']:,.2f} "
                      f"{' '.join(a['assets'])}") if a["assets"] else "-"
            rows.append([
                Paragraph(a["address"], S_MONO),
                Paragraph(a["chain"], S_MONO),
                Paragraph(amount, S_MONO),
                Paragraph(a["disposition_label"], S_SMALL),
            ])
        story.append(_table(rows, widths=[None, 20 * mm, 30 * mm, 40 * mm]))
        story.append(Spacer(1, 3 * mm))
        for a in fields["addresses"]:
            story.append(Paragraph(
                f"<b>{a['address'][:22]}…</b>&nbsp;&nbsp;{a['why_not_serveable']}",
                S_SMALL))
            story.append(Spacer(1, 1.2 * mm))
    else:
        story.append(Paragraph(
            "<b>No unattributable addresses were found in this trace.</b> Every "
            "endpoint reached a service that holds customer records, so this "
            "note is not required - use the Section 94 production order "
            "instead.", S_BODY))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("Routes recommended", S_H))
    for idx, r in enumerate(fields["routes"], start=1):
        story.append(Paragraph(
            f"<b>{idx}. {r['route']}.</b>&nbsp;&nbsp;{r['detail']}", S_BODY))
        story.append(Spacer(1, 1.6 * mm))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("What this note is not", S_H))
    for idx, lim in enumerate(fields["limitations"], start=1):
        story.append(Paragraph(f"<b>{idx}.</b>&nbsp;&nbsp;{lim}", S_BODY))
        story.append(Spacer(1, 1.4 * mm))
    story.append(Spacer(1, 8 * mm))

    story.append(_table([
        [_cell("Prepared by"), Paragraph(TO_COMPLETE, S_BODY)],
        [_cell("Reviewed by"), Paragraph(TO_COMPLETE, S_BODY)],
        [_cell("Date"), Paragraph(TO_COMPLETE, S_BODY)],
    ], widths=[52 * mm, None]))

    doc.build(story, onFirstPage=chrome, onLaterPages=chrome)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, digest, fields, reference
