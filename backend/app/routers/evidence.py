"""Evidence Parser  ·  owner: BE3  ·  Phase 2: dual hashing + persistence.

The dual-hash rule is the legal spine of this module. The browser hashes the
file with Web Crypto BEFORE upload, the server re-hashes on receipt, and the
two must match. A mismatch means the file mutated in transit, so the evidence
is rejected rather than silently stored - an evidence table that accepts
unverified files is worse than no evidence table.
"""

import csv
import io
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..models import AuthUser
from .auth import RequireUser

from ..db import cursor, row_to_evidence
from ..engines.pipeline import clear_cache
from ..models import AuditAction, Evidence
from ..services import audit, column_mapper, hashing, ingestion

router = APIRouter(prefix="/api/cases", tags=["evidence"])

ALLOWED = {"csv", "pdf", "txt"}
MAX_BYTES = 25 * 1024 * 1024


@router.get("/{case_id}/evidence", response_model=list[Evidence],
            summary="List uploaded evidence")
def list_evidence(case_id: str):
    with cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM evidence WHERE case_id = ? ORDER BY uploaded_at ASC",
            (case_id,),
        ).fetchall()
    return [row_to_evidence(r) for r in rows]


@router.post("/{case_id}/evidence", response_model=Evidence, status_code=201,
             summary="Upload evidence (CSV/PDF/TXT)")
async def upload_evidence(
    case_id: str,
    file: UploadFile = File(...),
    sha256_client: str = Form(..., description="Web Crypto hash computed pre-upload"),
    is_synthetic: bool = Form(True),
    account_ref: str = Form(""),
    user: AuthUser = RequireUser,
):
    # Identity comes from the verified session. It used to be a form field,
    # which meant anyone could file evidence as any officer.
    uploaded_by = user.user_id
    with cursor() as conn:
        if not conn.execute(
            "SELECT 1 FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone():
            raise HTTPException(404, f"Case {case_id} not found")

    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        raise HTTPException(
            415, f"Unsupported file type '.{ext}'. Accepts CSV, PDF or TXT."
        )

    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "File exceeds the 25 MB limit.")

    sha256_server = hashing.sha256_bytes(raw)
    if not hashing.matches(sha256_client, sha256_server):
        raise HTTPException(
            422,
            "Integrity check failed: the file changed between the browser and "
            "the server. Evidence rejected and not stored.",
        )

    row_count = None
    mapping = None
    if ext == "csv":
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(422, "CSV is not valid UTF-8 text.")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        row_count = max(0, len(rows) - 1)  # minus the header
        if rows:
            # AI feature 1: resolve this bank's column names onto the case
            # schema. Heuristics run first and the model only fills gaps, so a
            # failure here degrades the mapping - never the upload.
            mapping, _prov = column_mapper.map_columns(
                [h.strip() for h in rows[0] if h.strip()]
            )

    record = Evidence(
        evidence_id=f"EV-{uuid.uuid4().hex[:8]}",
        case_id=case_id,
        filename=file.filename or "unnamed",
        file_type=ext,
        size_bytes=len(raw),
        sha256_client=sha256_client.strip().lower(),
        sha256_server=sha256_server,
        hash_match=True,
        is_synthetic=is_synthetic,
        row_count=row_count,
        column_mapping=mapping,
        uploaded_at=datetime.now(timezone.utc).isoformat(),
        uploaded_by=uploaded_by,
    )

    with cursor() as conn:
        conn.execute(
            "INSERT INTO evidence (evidence_id, case_id, filename, file_type, "
            "size_bytes, sha256_client, sha256_server, hash_match, "
            "is_synthetic, row_count, column_mapping, uploaded_at, uploaded_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (record.evidence_id, record.case_id, record.filename,
             record.file_type.value, record.size_bytes, record.sha256_client,
             record.sha256_server, 1, int(record.is_synthetic),
             record.row_count,
             json.dumps(record.column_mapping) if record.column_mapping else None,
             record.uploaded_at, record.uploaded_by),
        )

    # Parse the file into transfers so the trace can actually see it. Until
    # this existed the uploader hashed, stored and audited a file that the
    # graph then ignored entirely.
    ingest_report = None
    if ext == "csv" and mapping:
        parsed, ingest_report = ingestion.normalise_rows(
            raw, mapping, case_id, record.evidence_id,
            account_ref=account_ref or None,
        )
        if parsed:
            with cursor() as conn:
                conn.executemany(
                    "INSERT INTO ingested_txn (edge_id, case_id, evidence_id, "
                    "from_node, to_node, amount, asset, timestamp, "
                    "evidence_type, utr, tx_hash) "
                    "VALUES (:edge_id, :case_id, :evidence_id, :from_node, "
                    ":to_node, :amount, :asset, :timestamp, :evidence_type, "
                    ":utr, :tx_hash)",
                    parsed,
                )
            # A new file changes the graph, so the memoised trace is stale.
            clear_cache()

    audit.record(
        case_id, AuditAction.EVIDENCE_UPLOADED, record.filename,
        user_id=uploaded_by, target_hash=sha256_server,
        details={"rows": row_count, "bytes": record.size_bytes,
                 **({"ingested": ingest_report["ingested"],
                     "skipped": ingest_report["skipped"],
                     "shape": ingest_report["shape"]} if ingest_report else {})},
    )
    record.ingestion = ingest_report
    return record
