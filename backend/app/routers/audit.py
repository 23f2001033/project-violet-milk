"""Audit router  ·  owner: BE3  ·  Phase 2: real append-only log."""

from fastapi import APIRouter

from ..models import AuditLog, AuditVerification
from ..services import audit as audit_service

router = APIRouter(prefix="/api/cases", tags=["audit"])


@router.get("/{case_id}/audit", response_model=list[AuditLog],
            summary="Chain-of-custody action log")
def get_audit(case_id: str):
    return audit_service.for_case(case_id)


@router.get("/{case_id}/audit/verify", response_model=AuditVerification,
            summary="Re-walk the custody chain and report any broken link")
def verify_audit(case_id: str):
    """Proves the log has not been edited since it was written.

    Each entry commits to its predecessor, so altering, reordering or deleting
    any row breaks every link after it. This does not PREVENT tampering - only
    an append-only store or external notarisation does that - but it makes
    tampering detectable, which is what the dossier's custody claim requires.
    """
    return audit_service.verify(case_id)
