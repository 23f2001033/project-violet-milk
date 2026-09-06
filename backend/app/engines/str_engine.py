"""
FIU-IND Suspicious Transaction Report - DRAFT generator.  Owner: BE3

Produces the STR field set an authorised Reporting Entity needs, as a
reviewable draft document.

WHAT THIS IS NOT
----------------
It does not file anything. FIU-IND's FINnet portal has no public submission
API, and filing requires the submitting organisation to be a registered
Reporting Entity whose Principal Officer signs the report. That is a legal
status, not an integration, so no amount of code can produce a working "file
with FIU-IND" button. Every page of the output says DRAFT and names who must
actually review and submit it.

Fields the Reporting Entity must supply are emitted as explicit
"[TO BE COMPLETED BY REPORTING ENTITY]" placeholders rather than being
invented, so nobody can mistake a generated draft for a complete report.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from ..config import REPORTS_DIR
from ..services.formatting import inr_group
from .pipeline import CaseAnalysis
from .report_engine import (
    BAND, CRIT, INK, MUTED, RULE, S_BODY, S_H, S_MONO, S_SMALL, S_SUB, S_TITLE,
    _cell, _table,
)

TO_COMPLETE = "[TO BE COMPLETED BY REPORTING ENTITY]"


def _reference(case_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"STR-DRAFT-{case_id}-{stamp}"


def build_fields(analysis: CaseAnalysis, case: dict) -> dict[str, Any]:
    """The STR field set, as structured data.

    Returned by the API alongside the PDF so the values can be inspected,
    diffed and copied into FINnet by the Principal Officer.
    """
    seed = case.get("seed_wallet", "")
    risk = analysis.risk.get(seed)
    flagged = [s for s in analysis.dilution.steps if s.flagged]
    inferred = [e for e in analysis.edges
                if e.evidence_type.value == "inferred_correlation"]
    mixers = [n.node_id for n in analysis.nodes if n.node_type.value == "mixer"]
    bridges = [n.node_id for n in analysis.nodes if n.node_type.value == "bridge"]

    return {
        # --- Part A: reporting entity (we are not one) --------------------
        "reporting_entity_name": TO_COMPLETE,
        "reporting_entity_fiu_reg_no": TO_COMPLETE,
        "principal_officer_name": TO_COMPLETE,
        "principal_officer_contact": TO_COMPLETE,

        # --- Part B: report metadata --------------------------------------
        "report_type": "STR - Suspicious Transaction Report (DRAFT)",
        "report_status": "DRAFT - NOT FILED",
        "prepared_by_system": "Project Violet Milk",
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "law_enforcement_reference": {
            "case_id": case.get("case_id"),
            "fir_reference": case.get("fir_ref"),
            "ncrp_reference": case.get("ncrp_ref"),
            "investigating_officer": case.get("io_name"),
        },

        # --- Part C: subject ----------------------------------------------
        "subject": {
            "identification_status":
                "NOT IDENTIFIED - address only. Attribution to a person "
                "requires KYC records obtained from the exchange under a "
                "Section 94 BNSS 2023 production order.",
            "primary_virtual_asset_address": seed,
            "chain": "Ethereum",
            "linked_bank_utr": case.get("seed_utr") or "not supplied",
        },

        # --- Part D: transactions ------------------------------------------
        "transaction_summary": {
            "reported_loss_inr": case.get("victim_amount_inr"),
            "incident_datetime": case.get("incident_datetime"),
            "entities_traced": len(analysis.nodes),
            "transfers_examined": len(analysis.edges),
            "confirmed_transfers": len(analysis.edges) - len(inferred),
            "inferred_correlations": len(inferred),
            "maximum_hop_depth": max(analysis.hop_depth.values(), default=0),
            "traversal_truncated": analysis.truncated,
            "data_source": analysis.source_name,
        },

        # --- Part E: grounds of suspicion -----------------------------------
        "grounds_of_suspicion": {
            "risk_score": f"{risk.score}/100" if risk else "not computed",
            "risk_level": risk.level.value if risk else "not computed",
            "engine_version": risk.engine_version if risk else None,
            "indicators": [
                {"rule": i.rule_id, "indicator": i.name, "weight": i.points,
                 "evidence": i.evidence, "basis": i.confidence.value}
                for i in (risk.indicators if risk else [])
            ],
            "mixer_contracts_involved": mixers,
            "cross_chain_bridges_involved": bridges,
            "entities_above_dilution_threshold": len(flagged),
            "dilution_threshold": analysis.dilution.threshold,
        },

        # --- Part F: limitations --------------------------------------------
        "limitations": [
            "This draft identifies movement of funds only. It does not "
            "identify any account holder and is not a finding of guilt.",
            "Inferred correlations are hypotheses requiring independent "
            "verification and are listed separately from confirmed records.",
            "Address attribution labels are drawn from a limited curated list "
            "and are not comprehensive.",
            "This system is not a registered Reporting Entity and has not "
            "filed, and cannot file, this report with FIU-IND.",
        ],
    }


def build_str_document(
    analysis: CaseAnalysis, case: dict, out_dir: Path | None = None
) -> tuple[Path, str, dict[str, Any], str]:
    """Render the draft STR. Returns (path, sha256, fields, reference)."""
    out_dir = out_dir or REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    fields = build_fields(analysis, case)
    reference = _reference(case["case_id"])
    path = out_dir / f"{reference}.pdf"

    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title=f"DRAFT STR - {case['case_id']}",
        author="Project Violet Milk",
    )

    def chrome(canvas, d):
        canvas.saveState()
        w, h = A4
        canvas.setFillColor(CRIT)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(18 * mm, h - 12 * mm, "DRAFT - NOT FILED")
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.drawRightString(w - 18 * mm, h - 12 * mm, reference)
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, h - 14 * mm, w - 18 * mm, h - 14 * mm)
        canvas.line(18 * mm, 15 * mm, w - 18 * mm, 15 * mm)
        canvas.setFont("Helvetica", 6.4)
        canvas.drawString(
            18 * mm, 11 * mm,
            "Draft prepared by an analysis system. Must be reviewed and "
            "submitted by an authorised Reporting Entity via FINnet.")
        canvas.drawRightString(w - 18 * mm, 11 * mm, f"Page {d.page}")
        canvas.restoreState()

    story: list = []
    story.append(Paragraph("SUSPICIOUS TRANSACTION REPORT", S_TITLE))
    story.append(Paragraph("DRAFT for review by an authorised Reporting "
                           "Entity &mdash; FIU-IND", S_SUB))

    warn = Table([[Paragraph(
        "<b>THIS DOCUMENT HAS NOT BEEN FILED.</b> Project Violet Milk is not a "
        "registered Reporting Entity and has no ability to submit reports to "
        "FIU-IND. Submission requires review by the Principal Officer of a "
        "registered entity and lodgement through the FINnet portal. Fields "
        "marked <b>[TO BE COMPLETED BY REPORTING ENTITY]</b> must be filled in "
        "before this draft can be used.", S_BODY)]],
        colWidths=[174 * mm])
    warn.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.0, CRIT),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8E5E3")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(warn)
    story.append(Spacer(1, 10))

    ler = fields["law_enforcement_reference"]
    story.append(Paragraph("Part A &mdash; Reporting entity", S_H))
    story.append(_table([
        [_cell("<b>Entity name</b>"), _cell(fields["reporting_entity_name"])],
        [_cell("<b>FIU registration no.</b>"),
         _cell(fields["reporting_entity_fiu_reg_no"])],
        [_cell("<b>Principal Officer</b>"),
         _cell(fields["principal_officer_name"])],
        [_cell("<b>Contact</b>"), _cell(fields["principal_officer_contact"])],
    ], [50 * mm, 124 * mm], header=False))

    story.append(Paragraph("Part B &mdash; Report metadata", S_H))
    story.append(_table([
        [_cell("<b>Reference</b>"), _cell(reference)],
        [_cell("<b>Status</b>"), _cell(f"<b>{fields['report_status']}</b>")],
        [_cell("<b>Prepared by</b>"), _cell(fields["prepared_by_system"])],
        [_cell("<b>Prepared at (UTC)</b>"), _cell(fields["prepared_at_utc"])],
        [_cell("<b>Case / FIR / NCRP</b>"),
         _cell(f"{ler['case_id']} · {ler['fir_reference']} · "
               f"{ler['ncrp_reference']}")],
        [_cell("<b>Investigating officer</b>"),
         _cell(ler["investigating_officer"])],
    ], [50 * mm, 124 * mm], header=False))

    subj = fields["subject"]
    story.append(Paragraph("Part C &mdash; Subject of the report", S_H))
    story.append(_table([
        [_cell("<b>Identification</b>"), _cell(subj["identification_status"])],
        [_cell("<b>Virtual asset address</b>"),
         Paragraph(subj["primary_virtual_asset_address"], S_MONO)],
        [_cell("<b>Chain</b>"), _cell(subj["chain"])],
        [_cell("<b>Linked bank UTR</b>"), _cell(subj["linked_bank_utr"])],
    ], [50 * mm, 124 * mm], header=False))

    ts = fields["transaction_summary"]
    story.append(Paragraph("Part D &mdash; Transaction summary", S_H))
    story.append(_table([
        [_cell("<b>Reported loss</b>"),
         _cell(f"INR {inr_group(ts['reported_loss_inr'] or 0)}"),
         _cell("<b>Incident</b>"), _cell(ts["incident_datetime"])],
        [_cell("<b>Entities traced</b>"), _cell(ts["entities_traced"]),
         _cell("<b>Transfers</b>"), _cell(ts["transfers_examined"])],
        [_cell("<b>Confirmed</b>"), _cell(ts["confirmed_transfers"]),
         _cell("<b>Inferred</b>"), _cell(ts["inferred_correlations"])],
        [_cell("<b>Max hop depth</b>"), _cell(ts["maximum_hop_depth"]),
         _cell("<b>Truncated</b>"),
         _cell("YES" if ts["traversal_truncated"] else "NO")],
    ], [38 * mm, 48 * mm, 38 * mm, 50 * mm], header=False))

    story.append(PageBreak())
    g = fields["grounds_of_suspicion"]
    story.append(Paragraph("Part E &mdash; Grounds of suspicion", S_H))
    story.append(Paragraph(
        f"Deterministic risk assessment: <b>{g['risk_score']} "
        f"({g['risk_level']})</b>, engine <b>{g['engine_version']}</b>. Every "
        "indicator below carries the specific evidence that triggered it, so "
        "the assessment can be recomputed independently.", S_BODY))

    rows = [["Rule", "Indicator", "Weight", "Evidence", "Basis"]]
    for i in g["indicators"]:
        rows.append([
            _cell(i["rule"]), _cell(i["indicator"]), _cell(f"+{i['weight']}"),
            Paragraph(i["evidence"], S_MONO), _cell(i["basis"].upper()),
        ])
    if len(rows) == 1:
        rows.append([_cell("—"), _cell("No indicators fired"), "", "", ""])
    story.append(_table(rows, [14 * mm, 42 * mm, 16 * mm, 82 * mm, 20 * mm]))

    story.append(_table([
        [_cell("<b>Mixer contracts</b>"),
         Paragraph(", ".join(g["mixer_contracts_involved"]) or "none", S_MONO)],
        [_cell("<b>Cross-chain bridges</b>"),
         Paragraph(", ".join(g["cross_chain_bridges_involved"]) or "none",
                   S_MONO)],
        [_cell("<b>Above dilution threshold</b>"),
         _cell(f"{g['entities_above_dilution_threshold']} entities at or above "
               f"{g['dilution_threshold']:.0%}")],
    ], [50 * mm, 124 * mm], header=False))

    story.append(Paragraph("Part F &mdash; Limitations", S_H))
    for idx, lim in enumerate(fields["limitations"], start=1):
        story.append(Paragraph(f"<b>F.{idx}</b>&nbsp;&nbsp;{lim}", S_BODY))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Part G &mdash; Certification by Reporting Entity",
                           S_H))
    story.append(Paragraph(
        "The undersigned confirms that the contents of this report have been "
        "reviewed and verified, and that the report is submitted in "
        "accordance with the entity's obligations under the PMLA 2002 and "
        "the FIU-IND guidelines applicable to Virtual Digital Asset service "
        "providers.", S_BODY))
    story.append(_table([
        [_cell("<b>Principal Officer</b>"), _cell(" "),
         _cell("<b>Signature</b>"), _cell(" ")],
        [_cell("<b>Designation</b>"), _cell(" "), _cell("<b>Date</b>"),
         _cell(" ")],
    ], [38 * mm, 48 * mm, 38 * mm, 50 * mm], header=False))

    doc.build(story, onFirstPage=chrome, onLaterPages=chrome)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, digest, fields, reference
