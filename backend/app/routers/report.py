"""Report Engine  ·  owner: BE3  ·  Phase 1 = contract stub.

Phase 5 builds the real ReportLab dossier: agency header, Section 63 BSA 2023
certificate, evidence hash table, graph snapshot, timeline, risk appendix
carrying engine_version, limitations page, and the document's own SHA-256.
"""

from fastapi import APIRouter, HTTPException

from ..models import ReportResponse

router = APIRouter(prefix="/api/cases", tags=["report"])


@router.post("/{case_id}/report", response_model=ReportResponse,
             summary="Generate the Sec 63 BSA court dossier")
def generate_report(case_id: str):
    raise HTTPException(
        501,
        "Report Engine lands in Phase 5. The contract is frozen; the frontend "
        "can wire the Export button against this shape now.",
    )
