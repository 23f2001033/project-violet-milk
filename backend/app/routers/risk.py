"""Risk + Dilution Engines  ·  owner: BE2  ·  Phase 1 = fixture stubs.

Phase 2 must reproduce the fixture numbers EXACTLY:
  · seed 0xa7f3...67e9 scores 65 (R1+R2+R3+R4, R5 deliberately not firing)
  · the clean pool dilutes to 0.12 and is NOT flagged
Those two numbers are locked by tests/test_dataset_integrity.py.
"""

from fastapi import APIRouter, HTTPException

from ..models import DilutionResult, RiskAssessment
from ..stubs import load

router = APIRouter(prefix="/api/cases", tags=["risk"])


@router.get("/{case_id}/nodes/{node_id}/risk", response_model=RiskAssessment,
            summary="Explainable risk score for one node")
def get_risk(case_id: str, node_id: str):
    risk = load("risk.json")
    if node_id.lower() == risk["node_id"].lower():
        return risk

    # Fall back to the graph fixture so every node answers during Phase 1.
    for n in load("graph.json")["elements"]["nodes"]:
        if n["data"]["id"].lower() == node_id.lower():
            d = n["data"]
            return RiskAssessment(
                node_id=d["id"], case_id=case_id,
                score=d["risk_score"], level=d["risk_level"],
                illicit_ratio=d["illicit_ratio"],
                indicators=[],  # BE2 Phase 2: emit real evidenced indicators
                computed_at=load("graph.json")["stats"]["traced_at"],
            )
    raise HTTPException(404, f"Node {node_id} not found in case {case_id}")


@router.post("/{case_id}/dilution", response_model=DilutionResult,
             summary="Proportional haircut across the traced graph")
def compute_dilution(case_id: str):
    return load("dilution.json")
