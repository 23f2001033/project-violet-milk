"""Timeline router  ·  owner: BE2  ·  Phase 2: real engine."""

from fastapi import APIRouter, HTTPException

from ..db import cursor
from ..engines.pipeline import get_analysis
from ..models import TimelineEvent

router = APIRouter(prefix="/api/cases", tags=["timeline"])


@router.get("/{case_id}/timeline", response_model=list[TimelineEvent],
            summary="Chronological reconstruction with time deltas")
def get_timeline(case_id: str):
    with cursor() as conn:
        row = conn.execute(
            "SELECT seed_wallet FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
    if not row or not row["seed_wallet"]:
        raise HTTPException(404, f"Case {case_id} not found")
    return get_analysis(case_id, row["seed_wallet"]).timeline
