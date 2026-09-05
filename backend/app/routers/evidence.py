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

from ..db import cursor, row_to_evidence
from ..models import AuditAction, Evidence
from ..services import audit, hashing

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
    uploaded_by: str = Form("IO_SHARMA"),
):
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
    if ext == "csv":
        try:
            reader = csv.reader(io.StringIO(raw.decode("utf-8-sig")))
            row_count = max(0, sum(1 for _ in reader) - 1)  # minus the header
        except UnicodeDecodeError:
            raise HTTPException(422, "CSV is not valid UTF-8 text.")

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
        column_mapping=None,   # Phase 5: the AI column mapper fills this in
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

    audit.record(
        case_id, AuditAction.EVIDENCE_UPLOADED, record.filename,
        user_id=uploaded_by, target_hash=sha256_server,
        details={"rows": row_count, "bytes": record.size_bytes},
    )
    return record
