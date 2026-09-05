"""Risk + Dilution routers  ·  owner: BE2  ·  Phase 2: real engines."""

from fastapi import APIRouter, HTTPException

from ..db import cursor
from ..engines.pipeline import get_analysis
from ..models import AuditAction, DilutionResult, RiskAssessment
from ..services import audit

router = APIRouter(prefix="/api/cases", tags=["risk"])


def _seed_for(case_id: str) -> str:
    with cursor() as conn:
        row = conn.execute(
            "SELECT seed_wallet FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
    if not row or not row["seed_wallet"]:
        raise HTTPException(404, f"Case {case_id} not found")
    return row["seed_wallet"]


@router.get("/{case_id}/nodes/{node_id}/risk", response_model=RiskAssessment,
            summary="Explainable risk score for one node")
def get_risk(case_id: str, node_id: str):
    a = get_analysis(case_id, _seed_for(case_id))
    for nid, assessment in a.risk.items():
        if nid.lower() == node_id.lower():
            return assessment
    raise HTTPException(404, f"Node {node_id} not found in case {case_id}")


@router.post("/{case_id}/dilution", response_model=DilutionResult,
             summary="Proportional haircut across the traced graph")
def compute_dilution(case_id: str):
    a = get_analysis(case_id, _seed_for(case_id))
    flagged = sum(1 for s in a.dilution.steps if s.flagged)
    audit.record(
        case_id, AuditAction.DILUTION_COMPUTED, case_id,
        details={"steps": len(a.dilution.steps), "flagged": flagged,
                 "threshold": a.dilution.threshold},
    )
    return a.dilution
