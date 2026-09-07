"""
Demo case seeding.  Owner: BE3

Idempotent. Pre-populates case CP-CYBER-2026-001 so the application opens on a
worked case rather than an empty shell - the demo starts at the Command Center
with something real on screen.
"""

import json

from .config import DEMO_CASE_ID
from .db import cursor, init_db
from .models import AuditAction

SEED_WALLET = "0xa7f39c1d8e4b2a5f7c3d9e0a1b8c6d4e5f2a67e9"

# Shown under the signed-in name in the header and on the dossier.
TEAM = "Team CyberNautics"
EVIDENCE_HASH = (
    "9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a"
)

_CASE = (
    DEMO_CASE_ID,
    "FIR-2026-CHD-4471",
    "1930-NCRP-2026-98124",
    "Complainant (synthetic)",
    470000.0,
    "2026-09-08T10:31:04+05:30",
    SEED_WALLET,
    "420192830192",
    "IO_SHARMA",
    "Victim received funds via UPI prior to USDT conversion.",
    "active",
    "synthetic",
    "2026-09-08T10:30:12+05:30",
    "2026-09-08T10:35:18+05:30",
)

_EVIDENCE = (
    "EV-8f3a2c17", DEMO_CASE_ID, "Bank_Stmt_SBI.csv", "csv", 1258291,
    EVIDENCE_HASH, EVIDENCE_HASH, 1, 1, 17,
    json.dumps({"UTR": "utr", "Txn Date": "timestamp",
                "Withdrawal Amt.": "amount", "Bank": "bank"}),
    "2026-09-08T10:30:45+05:30", "IO_SHARMA",
)

# The demo case arrives with the history an investigating officer would already
# have generated. Live actions append to this trail rather than replacing it.
_AUDIT = [
    ("A-seed0001", DEMO_CASE_ID, "2026-09-08T10:30:12+05:30", "IO_SHARMA",
     AuditAction.CASE_CREATED.value, DEMO_CASE_ID, None,
     json.dumps({}, sort_keys=True)),
    ("A-seed0002", DEMO_CASE_ID, "2026-09-08T10:30:45+05:30", "IO_SHARMA",
     AuditAction.EVIDENCE_UPLOADED.value, "Bank_Stmt_SBI.csv", EVIDENCE_HASH,
     json.dumps({"rows": 17}, sort_keys=True)),
    ("A-seed0003", DEMO_CASE_ID, "2026-09-08T10:35:18+05:30", "IO_SHARMA",
     AuditAction.TRACE_RUN.value, SEED_WALLET, None,
     json.dumps({"max_depth": 3, "nodes": 14, "edges": 17}, sort_keys=True)),
]


def seed_officer() -> None:
    """Create the four demo accounts if absent.

    The password comes from DEMO_OFFICER_PASSWORD. Left at the documented
    default, /health and the UI both say so - an instance on the default must
    never be mistaken for a secured one.
    """
    from . import config
    from .services import auth

    init_db()
    with cursor() as conn:
        exists = conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (config.DEFAULT_IO_NAME,)
        ).fetchone()
    if not exists:
        auth.create_user(
            config.DEFAULT_IO_NAME, "Demo Test 1", TEAM,
            config.DEMO_OFFICER_PASSWORD,
        )
    else:
        # An instance created before the team accounts existed still carries
        # the old title, and it is the string shown in the header. Correct it
        # in place rather than leaving the display to depend on how old the
        # database happens to be.
        with cursor() as conn:
            conn.execute(
                "UPDATE users SET display_name = ?, rank = ? WHERE user_id = ?",
                ("Demo Test 1", TEAM, config.DEFAULT_IO_NAME),
            )

    # One account per team member, so the custody log records who actually did
    # a thing rather than everyone sharing a single identity. They share a
    # password on purpose: this is a demonstration instance, and the banner
    # says so whenever that password is still the documented default.
    for n in (2, 3, 4):
        uid = f"DEMO_{n}"
        with cursor() as conn:
            present = conn.execute(
                "SELECT 1 FROM users WHERE user_id = ?", (uid,)
            ).fetchone()
        if not present:
            auth.create_user(uid, f"Demo Test {n}", TEAM,
                             config.DEMO_OFFICER_PASSWORD)


def seed_demo_case() -> None:
    init_db()
    seed_officer()
    with cursor() as conn:
        exists = conn.execute(
            "SELECT 1 FROM cases WHERE case_id = ?", (DEMO_CASE_ID,)
        ).fetchone()
        if exists:
            return

        conn.execute(
            "INSERT INTO cases (case_id, fir_ref, ncrp_ref, victim_name, "
            "victim_amount_inr, incident_datetime, seed_wallet, seed_utr, "
            "io_name, notes, status, data_mode, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", _CASE,
        )
        conn.execute(
            "INSERT INTO evidence (evidence_id, case_id, filename, file_type, "
            "size_bytes, sha256_client, sha256_server, hash_match, "
            "is_synthetic, row_count, column_mapping, uploaded_at, uploaded_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", _EVIDENCE,
        )
        # Seeded history must form a VALID chain, or the demo case would
        # report itself as tampered the moment anyone verified it.
        from .services.audit import GENESIS, _digest

        prev = GENESIS
        for seq, row in enumerate(_AUDIT, start=1):
            audit_id, cid, ts, user, action, target, thash, details = row
            entry = _digest(prev, audit_id, ts, user, action, target,
                            thash, details)
            conn.execute(
                "INSERT INTO audit_log (audit_id, case_id, timestamp, "
                "user_id, action, target, target_hash, details, seq, "
                "prev_hash, entry_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (audit_id, cid, ts, user, action, target, thash, details,
                 seq, prev, entry),
            )
            prev = entry
