"""Timeline Engine  ·  owner: BE2  ·  Phase 1 = fixture stubs."""

from fastapi import APIRouter

from ..models import TimelineEvent
from ..stubs import load

router = APIRouter(prefix="/api/cases", tags=["timeline"])


@router.get("/{case_id}/timeline", response_model=list[TimelineEvent],
            summary="Chronological reconstruction with time deltas")
def get_timeline(case_id: str):
    # Phase 2: merge bank + on-chain + system events, sort, compute deltas.
    return load("timeline.json")
