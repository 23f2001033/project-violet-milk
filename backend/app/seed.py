"""
Demo case seeding.  Owner: BE3

Idempotent. Pre-populates case CP-CYBER-2026-001 so the application opens on a
worked case rather than an empty shell - the demo starts at the Command Center
with something real on screen.
"""

import json
from datetime import datetime, timezone

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

# ---------------------------------------------------------------- team cases
# One case per officer, so each team member opens their own graph and the
# custody log records who worked what. Case 001 stays with Demo Test 1
# (IO_SHARMA) because its figures are the ones the integrity tests assert.
#
# The typologies are chosen from what Indian casework actually looks like, not
# from what flatters the software: a mule-network funnel, a chain-hopping trail
# that ends in a pool too dilute to report, and a short one that resolves.
TEAM_CASES = [
    {
        "case_id": "CP-CYBER-2026-002",
        "fir_ref": "FIR-2026-CHD-5518",
        "ncrp_ref": "1930-NCRP-2026-88214",
        "victim_name": "Six complainants (synthetic)",
        "victim_amount_inr": 943000.0,
        "incident_datetime": "2026-08-19T09:12:00+05:30",
        "seed_wallet": None,          # filled from the generated dataset
        "seed_utr": "94110820309 1",
        "io_name": "DEMO_2",
        "notes": ("Task-based 'part-time job' fraud. Six complainants, six "
                  "mule accounts funnelling into two aggregator UPI handles, "
                  "cash-out through a P2P trader into USDT on Tron."),
    },
    {
        "case_id": "CP-CYBER-2026-003",
        "fir_ref": "FIR-2026-CHD-4402",
        "ncrp_ref": "1930-NCRP-2026-77190",
        "victim_name": "Four complainants (synthetic)",
        "victim_amount_inr": 1217000.0,
        "incident_datetime": "2026-07-03T14:26:00+05:30",
        "seed_wallet": None,
        "seed_utr": "553011177 42",
        "io_name": "DEMO_3",
        "notes": ("Digital arrest fraud with deliberate chain-hopping: "
                  "Ethereum to a bridge to Tron and back to an exchange. Part "
                  "of the trail ends in a pool too dilute to report, and part "
                  "returns to India through a P2P payout."),
    },
    {
        "case_id": "CP-CYBER-2026-004",
        "fir_ref": "FIR-2026-CHD-6031",
        "ncrp_ref": "1930-NCRP-2026-91055",
        "victim_name": "Complainant (synthetic)",
        "victim_amount_inr": 185000.0,
        "incident_datetime": "2026-09-01T11:04:00+05:30",
        "seed_wallet": None,
        "seed_utr": "330891204471",
        "io_name": "DEMO_4",
        "notes": ("Straightforward UPI fraud. Three hops to a KYC-bearing "
                  "Indian exchange, and the production order can go out the "
                  "same day."),
    },
]


def _seed_wallet_for(case_id: str) -> str | None:
    """Read the seed address out of the generated dataset.

    Taking it from the CSV rather than repeating it here means the case record
    and the graph can never disagree about which address is being traced.
    """
    import csv as _csv
    from .config import DATA_DIR
    path = DATA_DIR / "cases" / case_id / "nodes.csv"
    if not path.is_file():
        return None
    with path.open(newline="", encoding="utf-8") as fh:
        for row in _csv.DictReader(fh):
            if row.get("is_seed", "").lower() == "true":
                return row["node_id"]
    return None


def seed_team_cases() -> None:
    """Create the per-officer cases, skipping any whose dataset is absent."""
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    for spec in TEAM_CASES:
        seed_wallet = _seed_wallet_for(spec["case_id"])
        if not seed_wallet:
            continue
        with cursor() as conn:
            if conn.execute("SELECT 1 FROM cases WHERE case_id = ?",
                            (spec["case_id"],)).fetchone():
                continue
            conn.execute(
                "INSERT INTO cases (case_id, fir_ref, ncrp_ref, victim_name, "
                "victim_amount_inr, incident_datetime, seed_wallet, seed_utr, "
                "io_name, notes, status, data_mode, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,'active','synthetic',?,?)",
                (spec["case_id"], spec["fir_ref"], spec["ncrp_ref"],
                 spec["victim_name"], spec["victim_amount_inr"],
                 spec["incident_datetime"], seed_wallet, spec["seed_utr"],
                 spec["io_name"], spec["notes"], now, now),
            )
        audit_record(spec["case_id"], spec["io_name"])


def audit_record(case_id: str, user_id: str) -> None:
    """A case that appears with no history looks fabricated. Give each one the
    creation entry an officer would have generated."""
    from .services import audit as _audit
    from .models import AuditAction as _A
    _audit.record(case_id, _A.CASE_CREATED, case_id, user_id=user_id,
                  details={"seeded": True})
