"""Audit Logger — append-only chain of custody.  Owner: BE3

Every mutating action writes one row BEFORE the response is returned. There is
no update and no delete: an audit trail that can be edited is not an audit
trail, and BNSS 2023 expects evidence handling to be reconstructible.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from ..db import cursor, row_to_audit
from ..models import AuditAction, AuditLog


def record(
    case_id: str,
    action: AuditAction,
    target: str,
    user_id: str = "IO_SHARMA",
    target_hash: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        audit_id=f"A-{uuid.uuid4().hex[:8]}",
        case_id=case_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        user_id=user_id,
        action=action,
        target=target,
        target_hash=target_hash,
        details=details or {},
    )
    with cursor() as conn:
        conn.execute(
            "INSERT INTO audit_log (audit_id, case_id, timestamp, user_id, "
            "action, target, target_hash, details) VALUES (?,?,?,?,?,?,?,?)",
            (entry.audit_id, entry.case_id, entry.timestamp, entry.user_id,
             entry.action.value, entry.target, entry.target_hash,
             json.dumps(entry.details)),
        )
    return entry


def for_case(case_id: str) -> list[dict]:
    """Chronological chain of custody.

    Sorting is done on PARSED datetimes rather than in SQL. Timestamps carry
    mixed UTC and IST offsets, and SQLite's ORDER BY compares them as plain
    strings - so "2026-09-08T10:30:00+05:30" sorts after "2026-09-08T09:00:00Z"
    even though it happened first. Lexical ordering of offset-aware ISO strings
    is simply wrong, and an out-of-order custody log is not a custody log.
    """
    with cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE case_id = ?", (case_id,)
        ).fetchall()
    entries = [row_to_audit(r) for r in rows]
    entries.sort(key=lambda e: datetime.fromisoformat(e["timestamp"]))
    return entries
