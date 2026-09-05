"""Case Manager  ·  owner: BE3  ·  Phase 1 = fixture stubs."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from ..models import Case, CaseCreate, CaseUpdate
from ..stubs import load

router = APIRouter(prefix="/api/cases", tags=["cases"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("", response_model=list[Case], summary="List all cases")
def list_cases():
    return load("cases.json")


@router.post("", response_model=Case, status_code=201, summary="Create a case")
def create_case(payload: CaseCreate):
    # BE3 Phase 2: persist to SQLite, generate the real case_id, write an audit row.
    base = dict(load("case.json"))
    base.update(payload.model_dump())
    base["updated_at"] = _now()
    return base


@router.get("/{case_id}", response_model=Case, summary="Fetch case metadata")
def get_case(case_id: str):
    case = load("case.json")
    if case_id != case["case_id"]:
        raise HTTPException(404, f"Case {case_id} not found")
    return case


@router.put("/{case_id}", response_model=Case, summary="Update case notes/status")
def update_case(case_id: str, payload: CaseUpdate):
    case = dict(load("case.json"))
    if case_id != case["case_id"]:
        raise HTTPException(404, f"Case {case_id} not found")
    case.update({k: v for k, v in payload.model_dump().items() if v is not None})
    case["updated_at"] = _now()
    return case
