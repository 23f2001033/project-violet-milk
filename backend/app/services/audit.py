"""Audit Logger - hash-chained chain of custody.  Owner: BE3

Every mutating action writes one row BEFORE the response is returned. There is
no update and no delete path.

WHY THE CHAIN EXISTS
--------------------
Append-only used to be a convention in this module rather than a property of
the data: the rows live in a SQLite file, and anything with that file could
UPDATE or DELETE them silently. A custody log that can be edited without trace
is not a custody log, and it is the legal spine of the dossier.

Each entry now commits to its predecessor:

    entry_hash = SHA256(prev_hash + audit_id + timestamp + user + action
                        + target + target_hash + details)

Tampering with, reordering or removing any row breaks every link after it, and
`verify()` reports exactly where. This does not PREVENT edits - only an
append-only store or external notarisation does that - but it makes them
detectable, which is what a court needs.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from ..db import cursor, row_to_audit
from ..models import AuditAction, AuditLog, AuditVerification

GENESIS = "0" * 64


def _digest(prev_hash: str, audit_id: str, timestamp: str, user_id: str,
            action: str, target: str, target_hash: str | None,
            details_json: str) -> str:
    payload = "|".join([
        prev_hash, audit_id, timestamp, user_id, action, target,
        target_hash or "", details_json,
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _head(conn, case_id: str) -> tuple[int, str]:
    """(next sequence number, hash of the current tail) for this case."""
    row = conn.execute(
        "SELECT seq, entry_hash FROM audit_log WHERE case_id = ? "
        "ORDER BY seq DESC LIMIT 1", (case_id,)
    ).fetchone()
    if not row or not row["entry_hash"]:
        return 1, GENESIS
    return row["seq"] + 1, row["entry_hash"]


def record(
    case_id: str,
    action: AuditAction,
    target: str,
    user_id: str = "IO_SHARMA",
    target_hash: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    audit_id = f"A-{uuid.uuid4().hex[:8]}"
    timestamp = datetime.now(timezone.utc).isoformat()
    details_json = json.dumps(details or {}, sort_keys=True)

    with cursor() as conn:
        seq, prev = _head(conn, case_id)
        entry_hash = _digest(prev, audit_id, timestamp, user_id, action.value,
                             target, target_hash, details_json)
        conn.execute(
            "INSERT INTO audit_log (audit_id, case_id, timestamp, user_id, "
            "action, target, target_hash, details, seq, prev_hash, entry_hash) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (audit_id, case_id, timestamp, user_id, action.value, target,
             target_hash, details_json, seq, prev, entry_hash),
        )

    return AuditLog(
        audit_id=audit_id, case_id=case_id, timestamp=timestamp,
        user_id=user_id, action=action, target=target, target_hash=target_hash,
        details=details or {}, prev_hash=prev, entry_hash=entry_hash,
    )


def _ordered_rows(case_id: str) -> list[dict]:
    """Chain order - the order the entries were actually written in.

    Ordered by the explicit `seq` column, not by rowid (not stable across a
    dump/restore) and not by timestamp (the seeded demo case is dated ahead of
    any live action taken during a rehearsal).
    """
    with cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE case_id = ? ORDER BY seq ASC",
            (case_id,),
        ).fetchall()
    return [row_to_audit(r) for r in rows]


def for_case(case_id: str) -> list[dict]:
    """Chronological chain of custody for display.

    Sorting is done on PARSED datetimes rather than in SQL. Timestamps carry
    mixed UTC and IST offsets, and SQLite's ORDER BY compares them as plain
    strings - so "2026-09-08T10:30:00+05:30" sorts after
    "2026-09-08T09:00:00Z" even though it happened first.
    """
    entries = _ordered_rows(case_id)
    entries.sort(key=lambda e: datetime.fromisoformat(e["timestamp"]))
    return entries


def verify(case_id: str) -> AuditVerification:
    """Re-walk the chain and report the first broken link, if any."""
    rows = _ordered_rows(case_id)
    prev = GENESIS

    for r in rows:
        expected = _digest(
            prev, r["audit_id"], r["timestamp"], r["user_id"], r["action"],
            r["target"], r["target_hash"],
            json.dumps(r["details"], sort_keys=True),
        )
        if r.get("prev_hash") != prev or r.get("entry_hash") != expected:
            return AuditVerification(
                case_id=case_id, entries=len(rows), intact=False,
                broken_at=r["audit_id"], head_hash=prev,
            )
        prev = expected

    return AuditVerification(
        case_id=case_id, entries=len(rows), intact=True, head_hash=prev,
    )
