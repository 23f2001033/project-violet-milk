"""Risk + Dilution routers  ·  owner: BE2  ·  Phase 2: real engines."""

from fastapi import APIRouter, HTTPException

from ..db import cursor
from ..engines.pipeline import get_analysis
from ..models import DilutionResult, RiskAssessment

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
    # Deliberately writes NO audit row. Dilution is a pure derived computation
    # that the dashboard recomputes on every render, so auditing it buried the
    # real custody events under one DILUTION_COMPUTED entry per page load.
    # The chain of custody records investigator ACTIONS on evidence - case
    # creation, ingestion, tracing, export - not incidental recalculation.
    return get_analysis(case_id, _seed_for(case_id)).dilution
