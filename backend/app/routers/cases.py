"""Case Manager  ·  owner: BE3  ·  Phase 2: SQLite persistence."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from ..db import cursor, row_to_case
from ..models import AuditAction, Case, CaseCreate, CaseUpdate
from ..services import audit

router = APIRouter(prefix="/api/cases", tags=["cases"])

_MUTABLE = {"notes", "status", "seed_wallet", "data_mode"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_case_id() -> str:
    with cursor() as conn:
        n = conn.execute("SELECT COUNT(*) AS c FROM cases").fetchone()["c"]
    return f"CP-CYBER-{datetime.now().year}-{n + 1:03d}"


@router.get("", response_model=list[Case], summary="List all cases")
def list_cases():
    with cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM cases WHERE status != 'archived' "
            "ORDER BY created_at DESC"
        ).fetchall()
    return [row_to_case(r) for r in rows]


@router.post("", response_model=Case, status_code=201, summary="Create a case")
def create_case(payload: CaseCreate):
    case_id = _next_case_id()
    now = _now()
    record = {**payload.model_dump(), "case_id": case_id, "status": "active",
              "data_mode": "synthetic", "created_at": now, "updated_at": now}

    with cursor() as conn:
        conn.execute(
            "INSERT INTO cases (case_id, fir_ref, ncrp_ref, victim_name, "
            "victim_amount_inr, incident_datetime, seed_wallet, seed_utr, "
            "io_name, notes, status, data_mode, created_at, updated_at) "
            "VALUES (:case_id, :fir_ref, :ncrp_ref, :victim_name, "
            ":victim_amount_inr, :incident_datetime, :seed_wallet, :seed_utr, "
            ":io_name, :notes, :status, :data_mode, :created_at, :updated_at)",
            record,
        )

    audit.record(case_id, AuditAction.CASE_CREATED, case_id,
                 user_id=payload.io_name, details={"fir_ref": payload.fir_ref})
    return record


@router.get("/{case_id}", response_model=Case, summary="Fetch case metadata")
def get_case(case_id: str):
    with cursor() as conn:
        row = conn.execute(
            "SELECT * FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, f"Case {case_id} not found")
    return row_to_case(row)


@router.put("/{case_id}", response_model=Case,
            summary="Update case notes, status, seed or data mode")
def update_case(case_id: str, payload: CaseUpdate):
    changes = {
        k: (v.value if hasattr(v, "value") else v)
        for k, v in payload.model_dump().items()
        if v is not None and k in _MUTABLE
    }
    if not changes:
        raise HTTPException(400, "No updatable fields supplied")

    changes["updated_at"] = _now()
    assignments = ", ".join(f"{k} = :{k}" for k in changes)

    with cursor() as conn:
        result = conn.execute(
            f"UPDATE cases SET {assignments} WHERE case_id = :case_id",
            {**changes, "case_id": case_id},
        )
        if result.rowcount == 0:
            raise HTTPException(404, f"Case {case_id} not found")
        row = conn.execute(
            "SELECT * FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()

    action = (AuditAction.MODE_SWITCHED if "data_mode" in changes
              else AuditAction.CASE_UPDATED)
    audit.record(case_id, action, case_id,
                 details={k: v for k, v in changes.items() if k != "updated_at"})
    return row_to_case(row)
