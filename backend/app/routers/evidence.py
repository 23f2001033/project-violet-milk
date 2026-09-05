"""Evidence Parser  ·  owner: BE3  ·  Phase 1 = fixture stubs.

The dual-hash rule is the legal spine of this module: the browser hashes the
file with Web Crypto BEFORE upload, the server re-hashes on receipt, and the
two MUST match. A mismatch means the file mutated in transit and the evidence
is rejected rather than silently stored.
"""

import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..models import Evidence
from ..stubs import load

router = APIRouter(prefix="/api/cases", tags=["evidence"])


@router.get("/{case_id}/evidence", response_model=list[Evidence],
            summary="List uploaded evidence")
def list_evidence(case_id: str):
    return load("evidence.json")


@router.post("/{case_id}/evidence", response_model=Evidence, status_code=201,
             summary="Upload evidence (CSV/PDF/TXT)")
async def upload_evidence(
    case_id: str,
    file: UploadFile = File(...),
    sha256_client: str = Form(..., description="Web Crypto hash computed pre-upload"),
    is_synthetic: bool = Form(True),
    uploaded_by: str = Form("IO_SHARMA"),
):
    raw = await file.read()
    sha256_server = hashlib.sha256(raw).hexdigest()
    match = sha256_server.lower() == sha256_client.lower()

    if not match:
        raise HTTPException(
            422,
            "Integrity check failed: the file changed between the browser and "
            "the server. Evidence rejected.",
        )

    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in {"csv", "pdf", "txt"}:
        raise HTTPException(415, f"Unsupported file type '.{ext}'. Accepts CSV, PDF, TXT.")

    # BE3 Phase 2: parse rows, run the AI column mapper, persist, write audit row.
    return Evidence(
        evidence_id=f"EV-{uuid.uuid4().hex[:8]}",
        case_id=case_id,
        filename=file.filename or "unnamed",
        file_type=ext,
        size_bytes=len(raw),
        sha256_client=sha256_client.lower(),
        sha256_server=sha256_server,
        hash_match=True,
        is_synthetic=is_synthetic,
        row_count=None,
        column_mapping=None,
        uploaded_at=datetime.now(timezone.utc).isoformat(),
        uploaded_by=uploaded_by,
    )
