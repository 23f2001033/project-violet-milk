"""
AI feature 2 — dossier narrative.  Owner: BE2

Turns computed findings into the paragraph an investigating officer would
otherwise write by hand. The model receives ONLY figures the engines already
produced and is instructed to invent nothing: every number in the prose exists
in the analysis, and the risk score itself is never the model's opinion.

If the provider is unreachable the deterministic template below is used
instead, and the dossier records which was used. A reader can always tell
whether they are looking at generated prose or a template.
"""

from __future__ import annotations

from ..engines.pipeline import CaseAnalysis
from . import llm_client
from .formatting import inr, inr_group

SYSTEM = (
    "You draft factual summaries for Indian police cyber-crime case files. "
    "Write plain, sober prose for an investigating officer and a court. "
    "STRICT RULES: use only the figures supplied; never invent numbers, names, "
    "addresses or conclusions; never state or imply that any person is guilty; "
    "never claim an account holder has been identified. Describe what the fund "
    "movement shows, not who did it. Two paragraphs, at most 160 words total. "
    "No headings, no bullet points, no markdown."
)


def _facts(a: CaseAnalysis, case: dict) -> str:
    seed = case.get("seed_wallet", "")
    risk = a.risk.get(seed)
    flagged = [s for s in a.dilution.steps if s.flagged]
    rescued = [s for s in a.dilution.steps if not s.flagged]
    inferred = [e for e in a.edges
                if e.evidence_type.value == "inferred_correlation"]

    lines = [
        f"Case: {case.get('case_id')}",
        f"FIR/NCRP: {case.get('ncrp_ref')}",
        f"Reported loss: {inr(case.get('victim_amount_inr', 0))}",
        f"Incident time: {case.get('incident_datetime')}",
        f"Seed wallet: {seed}",
        f"Entities traced: {len(a.nodes)}; transfers: {len(a.edges)};"
        f" maximum depth: {max(a.hop_depth.values(), default=0)}",
        f"Confirmed transfers: {len(a.edges) - len(inferred)};"
        f" inferred correlations: {len(inferred)}",
    ]
    if risk:
        lines.append(
            f"Seed wallet risk score: {risk.score}/100 ({risk.level.value}); "
            "indicators: "
            + "; ".join(f"{i.name} +{i.points} ({i.evidence})"
                        for i in risk.indicators)
        )
    lines.append(
        f"Dilution: {len(flagged)} transfers at or above the "
        f"{a.dilution.threshold:.0%} reporting threshold, "
        f"{len(rescued)} below it."
    )
    top = sorted(a.risk.values(), key=lambda r: r.score, reverse=True)[:3]
    lines.append(
        "Highest-scoring entities: "
        + "; ".join(f"{r.node_id} {r.score}/100 {r.level.value}" for r in top)
    )
    return "\n".join(lines)


def _template(a: CaseAnalysis, case: dict) -> str:
    seed = case.get("seed_wallet", "")
    risk = a.risk.get(seed)
    inferred = sum(1 for e in a.edges
                   if e.evidence_type.value == "inferred_correlation")
    confirmed = len(a.edges) - inferred
    score = f"{risk.score}/100 ({risk.level.value})" if risk else "not computed"

    return (
        f"Analysis of case {case.get('case_id')} traced a reported loss of "
        f"{inr(case.get('victim_amount_inr', 0))} across {len(a.nodes)} entities "
        f"and {len(a.edges)} transfers, to a maximum depth of "
        f"{max(a.hop_depth.values(), default=0)} hops from the seed address "
        f"{seed}. Of these transfers, {confirmed} are confirmed against bank or "
        f"on-chain records and {inferred} are inferred correlations that "
        f"require independent verification.\n\n"
        f"The seed address carries a risk score of {score}, derived from the "
        f"deterministic indicators listed in the risk appendix. Proportional "
        f"dilution was applied at each hop; entities falling below the "
        f"{a.dilution.threshold:.0%} threshold are recorded but not flagged. "
        f"This analysis identifies fund movement only and does not establish "
        f"the identity or culpability of any account holder."
    )


_EXOTIC_SPACE = dict.fromkeys(
    map(ord, "     ⁠﻿"), " "
)
_DASHES = {ord("–"): "-", ord("—"): "-",
           ord("‘"): "'", ord("’"): "'",
           ord("“"): '"', ord("”"): '"'}


def sanitise(text: str) -> str:
    """Make model output safe to place into a ReportLab paragraph.

    Two distinct hazards, both real:

    1. ReportLab parses a mini-markup language, so a bare '&' or '<' in
       generated prose raises at build time and takes the whole dossier with
       it. Escaping is mandatory, not defensive.
    2. Models emit typographic Unicode - narrow no-break spaces, en dashes,
       smart quotes - which the standard PDF fonts render as black boxes or
       drop entirely.
    """
    text = text.translate(_EXOTIC_SPACE).translate(_DASHES)
    text = text.encode("latin-1", "ignore").decode("latin-1")
    text = (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))
    # Models often ignore "no markdown"; strip the leftovers rather than
    # printing literal asterisks in a court document.
    text = text.replace("**", "").replace("##", "").replace("* ", "")
    return text.strip()


def build(a: CaseAnalysis, case: dict) -> tuple[str, str]:
    """Return (narrative, provenance) where provenance is
    "ai-live", "ai-cache" or "template"."""
    content, prov = llm_client.complete(
        SYSTEM,
        "Draft the investigation summary from these findings:\n\n"
        + _facts(a, case),
        max_tokens=1200,
    )
    if content:
        return sanitise(content), ("ai-live" if prov == "live" else "ai-cache")
    return sanitise(_template(a, case)), "template"
