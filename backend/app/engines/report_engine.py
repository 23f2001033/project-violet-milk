"""
Report Engine — Section 63 BSA 2023 court dossier.  Owner: BE3

Converts the analysis into an official paper artifact attachable to an FIR or
charge sheet.

ON THE DOCUMENT'S OWN HASH — a deliberate design decision worth being able to
defend out loud: a file cannot contain its own SHA-256, because printing the
hash changes the bytes being hashed. Any product claiming otherwise is either
hashing something narrower than the file or is wrong. So this dossier prints
the hashes of the INGESTED EVIDENCE (which is what Section 63 concerns - the
integrity of the electronic records relied upon), and the hash OF THE DOSSIER
is computed after generation, returned by the API and written to the audit log
as a detached verification record. The document tells the reader exactly how to
verify it.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)

from ..config import REPORTS_DIR
from ..services.formatting import inr_group
from .pipeline import CaseAnalysis

INK = colors.HexColor("#17151F")
MUTED = colors.HexColor("#5A5668")
RULE = colors.HexColor("#C9C3D6")
VIOLET = colors.HexColor("#4A3480")
BAND = colors.HexColor("#F2F0F7")
CRIT = colors.HexColor("#A8342E")
WARN = colors.HexColor("#B4762A")
GOOD = colors.HexColor("#2F6B4F")

_ss = getSampleStyleSheet()

S_TITLE = ParagraphStyle("t", parent=_ss["Title"], fontName="Helvetica-Bold",
                         fontSize=15, leading=19, textColor=INK, spaceAfter=2)
S_SUB = ParagraphStyle("s", parent=_ss["Normal"], fontName="Helvetica-Bold",
                       fontSize=9.5, leading=13, textColor=VIOLET,
                       alignment=1, spaceAfter=10)
S_H = ParagraphStyle("h", parent=_ss["Heading2"], fontName="Helvetica-Bold",
                     fontSize=10.5, leading=14, textColor=INK,
                     spaceBefore=12, spaceAfter=5)
S_BODY = ParagraphStyle("b", parent=_ss["Normal"], fontName="Helvetica",
                        fontSize=8.8, leading=12.6, textColor=INK,
                        alignment=TA_JUSTIFY, spaceAfter=6)
S_SMALL = ParagraphStyle("sm", parent=_ss["Normal"], fontName="Helvetica",
                         fontSize=7.4, leading=10, textColor=MUTED)
S_MONO = ParagraphStyle("m", parent=_ss["Normal"], fontName="Courier",
                        fontSize=7, leading=9.4, textColor=INK)


def _cell(text, style=S_SMALL):
    return Paragraph(str(text), style)


def _table(rows, widths, header=True, align=None):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), BAND),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 7.2),
            ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ]
    if align:
        style += align
    t.setStyle(TableStyle(style))
    return t


def _chrome(case_id: str):
    """Header and footer drawn on every page."""
    def draw(canvas, doc):
        canvas.saveState()
        w, h = A4

        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, h - 12 * mm,
                          "CHANDIGARH POLICE HACKATHON")
        canvas.drawRightString(w - 18 * mm, h - 12 * mm, case_id)
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, h - 14 * mm, w - 18 * mm, h - 14 * mm)

        canvas.line(18 * mm, 15 * mm, w - 18 * mm, 15 * mm)
        canvas.setFont("Helvetica", 6.4)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 11 * mm,
                          "DEMONSTRATION / SYNTHETIC DATA — investigative lead "
                          "material, not a finding of guilt")
        canvas.drawRightString(w - 18 * mm, 11 * mm, f"Page {doc.page}")
        canvas.restoreState()
    return draw


def _risk_colour(level: str):
    return {"CRITICAL": CRIT, "HIGH": CRIT, "MEDIUM": WARN}.get(level, GOOD)


def build_dossier(
    analysis: CaseAnalysis,
    case: dict,
    evidence: list[dict],
    audit: list[dict],
    narrative: str,
    narrative_provenance: str,
    out_dir: Path | None = None,
    audit_verification: dict | None = None,
    evidence_anchors: dict[str, dict] | None = None,
) -> tuple[Path, str, int]:
    """Render the dossier. Returns (path, sha256_of_file, page_count)."""
    out_dir = out_dir or REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"{case['case_id']}_dossier_{stamp}.pdf"

    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title=f"Electronic Evidence Dossier — {case['case_id']}",
        author="Project Violet Milk",
    )

    seed = case.get("seed_wallet", "")
    seed_risk = analysis.risk.get(seed)
    story: list = []

    # ------------------------------------------------------------ page 1
    story.append(Paragraph("ELECTRONIC EVIDENCE DOSSIER", S_TITLE))
    story.append(Paragraph(
        "Prepared under Section 63, Bharatiya Sakshya Adhiniyam 2023", S_SUB))

    meta = [
        ["Case reference", case["case_id"], "FIR reference", case.get("fir_ref", "—")],
        ["NCRP / 1930 reference", case.get("ncrp_ref", "—"),
         "Investigating officer", case.get("io_name", "—")],
        ["Reported loss (INR)", inr_group(case.get('victim_amount_inr', 0)),
         "Incident date/time", case.get("incident_datetime", "—")],
        ["Seed address", seed or "—", "Bank UTR", case.get("seed_utr", "—")],
        ["Analysis source", analysis.source_name,
         "Data mode", "LIVE" if analysis.is_live else "SYNTHETIC / DEMO"],
        ["Generated (UTC)", datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "Risk engine", seed_risk.engine_version if seed_risk else "—"],
    ]
    story.append(_table(
        [[_cell(f"<b>{r[0]}</b>"), _cell(r[1]), _cell(f"<b>{r[2]}</b>"), _cell(r[3])]
         for r in meta],
        [32 * mm, 52 * mm, 32 * mm, 58 * mm], header=False))

    story.append(Paragraph("1. Investigation summary", S_H))
    for para in narrative.split("\n"):
        if para.strip():
            story.append(Paragraph(para.strip(), S_BODY))
    story.append(Paragraph(
        f"Summary generated by: <b>{narrative_provenance}</b>. Figures in this "
        "summary are produced by the deterministic analysis engines; narrative "
        "text does not compute or alter any score.", S_SMALL))

    story.append(Paragraph("2. Analysis at a glance", S_H))
    inferred = [e for e in analysis.edges
                if e.evidence_type.value == "inferred_correlation"]
    glance = [
        ["Entities traced", str(len(analysis.nodes)),
         "Transfers examined", str(len(analysis.edges))],
        ["Confirmed transfers", str(len(analysis.edges) - len(inferred)),
         "Inferred correlations", str(len(inferred))],
        ["Maximum hop depth", str(max(analysis.hop_depth.values(), default=0)),
         "Traversal truncated", "YES" if analysis.truncated else "NO"],
        ["Seed risk score",
         f"{seed_risk.score}/100 ({seed_risk.level.value})" if seed_risk else "—",
         "Dilution threshold", f"{analysis.dilution.threshold:.0%}"],
    ]
    story.append(_table(
        [[_cell(f"<b>{r[0]}</b>"), _cell(r[1]), _cell(f"<b>{r[2]}</b>"), _cell(r[3])]
         for r in glance],
        [42 * mm, 32 * mm, 44 * mm, 56 * mm], header=False))

    # ------------------------------------------------------------ page 2
    story.append(PageBreak())
    story.append(Paragraph("3. Section 63 BSA 2023 — statutory certificate", S_H))
    story.append(Paragraph(
        "This material accompanies the electronic record produced above. The "
        "analysis was generated by an automated system operated during the "
        "period of the investigation. The source records were ingested in the "
        "ordinary course of the investigation and their integrity is evidenced "
        "by the cryptographic digests tabulated below. The computer output was "
        "produced by deterministic, reproducible processing of those records; "
        "the scoring rules and their weights are stated in full in the risk "
        "appendix so that any reader may recompute the result independently.",
        S_BODY))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "<b>What Section 63(4) requires, and what this document is not.</b> A "
        "certificate under Section 63(4) of the Bharatiya Sakshya Adhiniyam "
        "2023 must be in the form of the Schedule to that Act, and must be "
        "signed both by the person in charge of the computer or communication "
        "device and by an expert. That is a change from the position under the "
        "repealed Indian Evidence Act 1872, where a single signatory "
        "sufficed. This document supplies the particulars such a certificate "
        "recites - the device, the process, and the digests - but it is NOT "
        "itself the certificate and it carries neither signature.",
        S_BODY))
    story.append(Paragraph(
        "<b>Certification under Section 63 remains the responsibility of the "
        "signatories named below. This software prepares the material; it does "
        "not certify it, and it cannot.</b>", S_BODY))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "The statutory wording in this document was prepared by the authors of "
        "the software, who are not legal practitioners, and has not been "
        "settled by counsel.", S_SMALL))

    story.append(Paragraph("4. Evidence integrity register", S_H))
    ev_rows = [["File", "Type", "Rows", "SHA-256 (server)", "Client match", "Ingested"]]
    for e in evidence:
        ev_rows.append([
            _cell(e["filename"]), _cell(e["file_type"]),
            _cell(e.get("row_count") or "—"),
            Paragraph(e["sha256_server"], S_MONO),
            _cell("MATCH" if e["hash_match"] else "MISMATCH"),
            _cell(e["uploaded_at"][:19]),
        ])
    if len(ev_rows) == 1:
        ev_rows.append([_cell("No files ingested"), "", "", "", "", ""])
    story.append(_table(ev_rows,
                        [30 * mm, 12 * mm, 12 * mm, 62 * mm, 18 * mm, 30 * mm]))
    story.append(Paragraph(
        "Each file is hashed in the browser before transmission and re-hashed "
        "on receipt. A mismatch causes the upload to be rejected rather than "
        "stored, so every row above represents a file whose bytes were "
        "identical at both points.", S_SMALL))

    story.append(Paragraph("5. Chain of custody", S_H))
    au_rows = [["Timestamp (UTC)", "User", "Action", "Target", "Digest"]]
    for a in audit:
        au_rows.append([
            _cell(a["timestamp"][:19]), _cell(a["user_id"]), _cell(a["action"]),
            Paragraph(str(a["target"]), S_MONO),
            Paragraph((a.get("target_hash") or "—")[:32], S_MONO),
        ])
    story.append(_table(au_rows,
                        [30 * mm, 20 * mm, 32 * mm, 52 * mm, 40 * mm]))

    if audit_verification:
        intact = audit_verification.get("intact")
        story.append(Paragraph(
            ("<b>Chain verification: INTACT.</b> " if intact
             else "<b>Chain verification: FAILED at "
                  f"{audit_verification.get('broken_at')}.</b> ")
            + "Each entry above carries a SHA-256 committing to the entry "
            "before it, so altering, reordering or removing any row breaks "
            f"every subsequent link. {audit_verification.get('entries', 0)} "
            "entries were re-walked at the time of export"
            + (f"; the chain head is {audit_verification.get('head_hash','')[:32]}…."
               if intact else ".")
            + " This makes tampering detectable; it does not prevent it.",
            S_SMALL))

    # ------------------------------------------------------------ page 3
    story.append(PageBreak())
    story.append(Paragraph("6. Entities traced", S_H))
    n_rows = [["Address / account", "Type", "Traced %", "Score", "Level"]]
    for n in sorted(analysis.nodes,
                    key=lambda x: analysis.risk[x.node_id].score, reverse=True):
        r = analysis.risk[n.node_id]
        n_rows.append([
            Paragraph(n.node_id, S_MONO), _cell(n.node_type.value),
            _cell(f"{analysis.illicit_ratio.get(n.node_id, 0) * 100:.0f}%"),
            _cell(str(r.score)),
            Paragraph(f'<font color="#{_risk_colour(r.level.value).hexval()[2:]}">'
                      f"<b>{r.level.value}</b></font>", S_SMALL),
        ])
    story.append(_table(n_rows, [74 * mm, 24 * mm, 20 * mm, 16 * mm, 20 * mm]))

    story.append(Paragraph("7. Transfers", S_H))
    t_rows = [["#", "Time (IST)", "From", "To", "Amount", "Basis"]]
    for e in analysis.edges:
        t_rows.append([
            _cell(e.edge_id), _cell(e.timestamp[11:19]),
            Paragraph(e.from_node[:20], S_MONO),
            Paragraph(e.to_node[:20], S_MONO),
            _cell(f"{inr_group(e.amount)} {e.asset.value}"),
            _cell("CONFIRMED" if e.evidence_type.value.startswith("confirmed")
                  else "INFERRED"),
        ])
    story.append(_table(t_rows,
                        [10 * mm, 18 * mm, 40 * mm, 40 * mm, 26 * mm, 20 * mm]))
    story.append(Paragraph(
        "<b>CONFIRMED</b> entries are supported by a bank record or an on-chain "
        "transaction. <b>INFERRED</b> entries are correlations - for example a "
        "debit and a deposit close in time - and are hypotheses requiring "
        "independent verification. They are not proven transfers.", S_SMALL))

    # ------------------------------------------------------------ page 4
    story.append(PageBreak())
    story.append(Paragraph("8. Risk appendix — indicators and evidence", S_H))
    scored = [r for r in analysis.risk.values() if r.indicators]
    for r in sorted(scored, key=lambda x: x.score, reverse=True)[:8]:
        block = [Paragraph(
            f'<font face="Courier" size="7">{r.node_id}</font> &nbsp; '
            f"<b>{r.score}/100 — {r.level.value}</b>", S_SMALL)]
        rows = [["Rule", "Pts", "Indicator", "Evidence", "Basis"]]
        for i in r.indicators:
            rows.append([
                _cell(i.rule_id), _cell(f"+{i.points}"), _cell(i.name),
                Paragraph(i.evidence, S_MONO), _cell(i.confidence.value.upper()),
            ])
        block.append(_table(rows,
                            [12 * mm, 10 * mm, 40 * mm, 74 * mm, 18 * mm]))
        block.append(Spacer(1, 5))
        story.append(KeepTogether(block))

    story.append(Paragraph("9. Dilution appendix — proportional haircut", S_H))
    story.append(Paragraph(
        "Illicit ratio = (incoming amount × source ratio) ÷ (prior balance + "
        "incoming amount). Applied in strict chronological order. Entities "
        f"below {analysis.dilution.threshold:.0%} are recorded but not flagged, "
        "which prevents legitimate liquidity from being implicated.", S_BODY))
    story.append(Paragraph(
        f"<b>Model applied: {analysis.dilution.model.upper()}.</b> "
        + analysis.dilution.caveat, S_BODY))
    d_rows = [["Entity", "Prior", "Incoming", "Source %", "Traced", "Result %", "Flag"]]
    for s in analysis.dilution.steps:
        d_rows.append([
            Paragraph(s.node_id[:22], S_MONO), _cell(f"{s.prior_balance:,.0f}"),
            _cell(f"{s.incoming_amount:,.0f}"), _cell(f"{s.incoming_ratio:.0%}"),
            _cell(f"{s.dirty_received:,.0f}"), _cell(f"{s.illicit_ratio:.0%}"),
            _cell("FLAGGED" if s.flagged else "—"),
        ])
    story.append(_table(d_rows,
                        [44 * mm, 20 * mm, 22 * mm, 18 * mm, 20 * mm, 20 * mm,
                         20 * mm]))
    story.append(Paragraph(
        "Amounts in this table are normalised to a single unit so that the "
        f"rupee and token legs of the same movement can be compared; INR is "
        f"converted at the rate recorded for this case. Section 7 lists every "
        "transfer in its original denomination.", S_SMALL))

    story.append(Paragraph("10. Limitations and scope", S_H))
    for idx, text in enumerate([
        "This analysis identifies the movement of funds. It does <b>not</b> "
        "identify any account holder. Attributing an address to a person "
        "requires KYC records obtained from the exchange under a Section 94 "
        "BNSS 2023 production order.",
        "Nothing in this document constitutes a finding of guilt, and no "
        "conclusion here is a substitute for independent investigation.",
        "Address attribution labels, where shown, come from a limited curated "
        "list and are not comprehensive. An unlabelled address is not thereby "
        "innocent, and a labelled one is not thereby proven.",
        "The proportional haircut model can be influenced by deliberately "
        "mixing clean funds. Alternative models (FIFO, LIFO, poison/taint) "
        "distribute taint differently; the haircut was selected to reduce "
        "false positives on legitimate liquidity.",
        "Where traversal bounds were reached the graph is incomplete, and this "
        "is reported as 'Traversal truncated' in section 2.",
        "Inferred correlations are explicitly separated from confirmed records "
        "throughout this document and must not be treated as equivalent.",
    ], start=1):
        story.append(Paragraph(f"<b>10.{idx}</b>&nbsp;&nbsp;{text}", S_BODY))

    story.append(Paragraph("11. Blockchain anchoring of evidence digests", S_H))
    anchors = evidence_anchors or {}
    anchored = [(f, a) for f, a in anchors.items() if a.get("anchored")]

    if anchored:
        story.append(Paragraph(
            "The digest of each ingested file below has been published to a "
            "public blockchain. Because that record is outside this system, "
            "the fact that the file existed in this form at that time remains "
            "checkable even if this server is later compromised, rebuilt, or "
            "its database rewritten.", S_BODY))
        an_rows = [["File", "SHA-256", "Block", "Transaction"]]
        for fname, a in anchored:
            an_rows.append([
                _cell(fname),
                Paragraph(a.get("digest", "")[:32] + "…", S_MONO),
                _cell(a.get("block_number") or "—"),
                Paragraph(str(a.get("tx_hash") or "—")[:34] + "…", S_MONO),
            ])
        story.append(_table(an_rows,
                            [34 * mm, 56 * mm, 20 * mm, 64 * mm]))
        first = anchored[0][1]
        if first.get("explorer_url"):
            story.append(Paragraph(
                f"Verify independently at: {first['explorer_url']}", S_MONO))
    else:
        story.append(Paragraph(
            "Blockchain anchoring is not enabled on this instance, so no "
            "external existence proof accompanies this dossier. The evidence "
            "digests in section 4 and the chain-of-custody log in section 5 "
            "remain the record of integrity.", S_BODY))

    story.append(Paragraph(
        "<b>What an anchor establishes, and what it does not.</b> An anchor "
        "shows that a digest existed at or before the stated block and that "
        "the record cannot afterwards be revised. It does <b>not</b> "
        "establish who created the document — any party may anchor any "
        "digest — and it does not render a document tamper-proof. It makes a "
        "later substitution <b>detectable</b>, because an altered file "
        "produces a different digest. Block timestamps are set by the block "
        "proposer and may drift by seconds, so an anchor should be read as "
        "‘at or before this block’ rather than as a precise time.",
        S_BODY))

    story.append(Paragraph("12. Verification of this document", S_H))
    story.append(Paragraph(
        "A document cannot contain its own cryptographic digest, because "
        "printing the digest alters the bytes being digested. The SHA-256 of "
        "this file is therefore issued as a detached record: it is returned by "
        "the system at the moment of export and written to the chain-of-custody "
        "log. To verify this dossier, compute the SHA-256 of this PDF and "
        "compare it against that recorded value.", S_BODY))

    story.append(Spacer(1, 10))
    story.append(_table([
        [_cell("<b>Certifying officer</b>"), _cell(case.get("io_name", "")),
         _cell("<b>Signature (DSC)</b>"), _cell(" ")],
        [_cell("<b>Designation</b>"), _cell(" "), _cell("<b>Date</b>"), _cell(" ")],
    ], [30 * mm, 50 * mm, 32 * mm, 62 * mm], header=False))

    doc.build(story, onFirstPage=_chrome(case["case_id"]),
              onLaterPages=_chrome(case["case_id"]))

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, digest, doc.page
