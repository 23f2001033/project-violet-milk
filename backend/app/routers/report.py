"""Report Engine router  ·  owner: BE3  ·  Phase 5: Sec 63 BSA dossier."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import REPORTS_DIR
from ..db import cursor, row_to_evidence
from ..engines.pipeline import get_analysis
from ..engines.report_engine import build_dossier
from ..engines.str_engine import build_str_document
from ..models import (
    AnchorRecord, AnomalyFinding, AnomalyResponse, AuditAction, ReportResponse,
    STRResponse,
)
from ..services import anchor as anchor_service
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

    # Evidence digests are known BEFORE generation, so their anchors CAN be
    # printed in the document. The dossier's own digest cannot be - printing
    # it would change the bytes being hashed - so that anchor is returned by
    # the API and written to the custody log instead.
    ev_anchors = {}
    for e in evidence:
        rec = anchor_service.read_cached(e["sha256_server"])
        if rec:
            ev_anchors[e["filename"]] = rec

    path, digest, pages = build_dossier(
        analysis, case, evidence, audit_before, text, provenance,
        audit_verification=audit_service.verify(case_id).model_dump(mode="json"),
        evidence_anchors=ev_anchors,
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

    # Anchor the dossier's own digest AFTER generation - it cannot be printed
    # inside the document it describes, for the same reason the hash cannot be.
    # The anchor is returned here and written to the custody log instead.
    anchor_record = anchor_service.anchor_digest(digest)
    if anchor_record.get("anchored"):
        audit_service.record(
            case_id, AuditAction.EVIDENCE_ANCHORED, path.name,
            user_id=case.get("io_name", "IO_SHARMA"), target_hash=digest,
            details={"tx_hash": anchor_record.get("tx_hash"),
                     "block_number": anchor_record.get("block_number"),
                     "chain_id": anchor_record.get("chain_id")},
        )

    return ReportResponse(
        case_id=case_id,
        filename=path.name,
        sha256=digest,
        generated_at=analysis.traced_at,
        page_count=pages,
        download_url=f"/api/cases/{case_id}/report/{path.name}",
        anchor=AnchorRecord(**anchor_record),
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


@router.post("/{case_id}/str", response_model=STRResponse,
             summary="Generate a DRAFT FIU-IND Suspicious Transaction Report")
def generate_str(case_id: str):
    """Produces a reviewable draft, never a filing.

    There is deliberately no endpoint that files an STR. FIU-IND's FINnet
    portal has no public submission API, and lodging a report requires the
    submitting organisation to be a registered Reporting Entity whose
    Principal Officer signs it. A button that claimed to file would be false.
    """
    with cursor() as conn:
        row = conn.execute(
            "SELECT * FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, f"Case {case_id} not found")

    case = dict(row)
    if not case.get("seed_wallet"):
        raise HTTPException(422, "Case has no seed wallet to report on.")

    analysis = get_analysis(case_id, case["seed_wallet"])
    path, digest, fields, reference = build_str_document(analysis, case)

    audit_service.record(
        case_id, AuditAction.REPORT_GENERATED, path.name,
        user_id=case.get("io_name", "IO_SHARMA"), target_hash=digest,
        details={"kind": "STR_DRAFT", "reference": reference, "filed": False},
    )

    return STRResponse(
        case_id=case_id,
        str_reference=reference,
        generated_at=analysis.traced_at,
        filename=path.name,
        sha256=digest,
        download_url=f"/api/cases/{case_id}/report/{path.name}",
        fields=fields,
    )


@router.get("/{case_id}/anomaly", response_model=AnomalyResponse,
            summary="Unsupervised anomaly findings (secondary lead signal)")
def get_anomaly(case_id: str):
    """Isolation Forest + DBSCAN over behavioural graph features.

    Served on its own endpoint with its own shape so it can never be mistaken
    for a risk score. Nothing here contributes to a score or to the statutory
    section of the dossier.
    """
    with cursor() as conn:
        row = conn.execute(
            "SELECT seed_wallet FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
    if not row or not row["seed_wallet"]:
        raise HTTPException(404, f"Case {case_id} not found")

    a = get_analysis(case_id, row["seed_wallet"])
    r = a.anomaly
    if r is None:
        raise HTTPException(503, "Anomaly engine unavailable")

    return AnomalyResponse(
        case_id=case_id, version=r.version, trained=r.trained, reason=r.reason,
        findings=[
            AnomalyFinding(node_id=nid, score=r.scores.get(nid, 0.0),
                           cluster=r.clusters.get(nid, -1),
                           explanation=r.explanations.get(nid, ""))
            for nid in r.outliers
        ],
        cluster_sizes={str(k): v for k, v in r.cluster_sizes.items()},
    )


@router.get("/{case_id}/anchor/{digest}", response_model=AnchorRecord,
            summary="Verify a digest against the chain")
def verify_anchor(case_id: str, digest: str):
    """Read-only, so anyone auditing a dossier can run it without credentials.

    That is the point of anchoring: verification must not depend on trusting
    — or even having access to — this server.
    """
    return AnchorRecord(**anchor_service.verify_digest(digest))


@router.post("/{case_id}/anchor/{digest}", response_model=AnchorRecord,
             summary="Anchor a digest on-chain")
def create_anchor(case_id: str, digest: str):
    with cursor() as conn:
        if not conn.execute("SELECT 1 FROM cases WHERE case_id = ?",
                            (case_id,)).fetchone():
            raise HTTPException(404, f"Case {case_id} not found")

    record = anchor_service.anchor_digest(digest)
    if record.get("anchored"):
        audit_service.record(
            case_id, AuditAction.EVIDENCE_ANCHORED, digest,
            target_hash=digest,
            details={"tx_hash": record.get("tx_hash"),
                     "block_number": record.get("block_number"),
                     "chain_id": record.get("chain_id")},
        )
    return AnchorRecord(**record)
