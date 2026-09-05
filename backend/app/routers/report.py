"""Report Engine router  ·  owner: BE3  ·  Phase 5: Sec 63 BSA dossier."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import REPORTS_DIR
from ..db import cursor, row_to_evidence
from ..engines.pipeline import get_analysis
from ..engines.report_engine import build_dossier
from ..models import AuditAction, ReportResponse
from ..services import audit as audit_service
from ..services import narrative as narrative_service

router = APIRouter(prefix="/api/cases", tags=["report"])


@router.post("/{case_id}/report", response_model=ReportResponse,
             summary="Generate the Sec 63 BSA court dossier")
def generate_report(case_id: str):
    with cursor() as conn:
        case_row = conn.execute(
            "SELECT * FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        if not case_row:
            raise HTTPException(404, f"Case {case_id} not found")
        ev_rows = conn.execute(
            "SELECT * FROM evidence WHERE case_id = ? ORDER BY uploaded_at",
            (case_id,),
        ).fetchall()

    case = dict(case_row)
    if not case.get("seed_wallet"):
        raise HTTPException(
            422, "Case has no seed wallet, so there is nothing to trace or report."
        )

    analysis = get_analysis(case_id, case["seed_wallet"])
    evidence = [row_to_evidence(r) for r in ev_rows]
    audit_before = audit_service.for_case(case_id)

    # AI drafts the prose only; if the provider is unreachable a deterministic
    # template is used and the dossier records which was applied.
    text, provenance = narrative_service.build(analysis, case)

    path, digest, pages = build_dossier(
        analysis, case, evidence, audit_before, text, provenance
    )

    # The dossier's own hash is a DETACHED record - a file cannot contain its
    # own digest. Writing it to the custody log is what makes the document
    # verifiable after the fact.
    audit_service.record(
        case_id, AuditAction.REPORT_GENERATED, path.name,
        user_id=case.get("io_name", "IO_SHARMA"), target_hash=digest,
        details={"pages": pages, "narrative": provenance,
                 "entities": len(analysis.nodes), "transfers": len(analysis.edges)},
    )

    return ReportResponse(
        case_id=case_id,
        filename=path.name,
        sha256=digest,
        generated_at=analysis.traced_at,
        page_count=pages,
        download_url=f"/api/cases/{case_id}/report/{path.name}",
    )


@router.get("/{case_id}/report/{filename}", summary="Download a generated dossier")
def download_report(case_id: str, filename: str):
    # Reject any path separator or traversal segment before touching the disk.
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    path = (REPORTS_DIR / filename).resolve()
    if not path.is_file() or REPORTS_DIR.resolve() not in path.parents:
        raise HTTPException(404, "Dossier not found")
    return FileResponse(path, media_type="application/pdf", filename=filename)
