"""Audit router  ·  owner: BE3  ·  Phase 2: real append-only log."""

from fastapi import APIRouter

from ..models import AuditLog
from ..services import audit as audit_service

router = APIRouter(prefix="/api/cases", tags=["audit"])


@router.get("/{case_id}/audit", response_model=list[AuditLog],
            summary="Chain-of-custody action log")
def get_audit(case_id: str):
    return audit_service.for_case(case_id)
