"""Audit Logger  ·  owner: BE3  ·  Phase 1 = fixture stubs.

Append-only. There is no update or delete path, by design: the chain of custody
must be reconstructible after the fact.
"""

from fastapi import APIRouter

from ..models import AuditLog
from ..stubs import load

router = APIRouter(prefix="/api/cases", tags=["audit"])


@router.get("/{case_id}/audit", response_model=list[AuditLog],
            summary="Chain-of-custody action log")
def get_audit(case_id: str):
    return load("audit.json")
