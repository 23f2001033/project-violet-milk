"""SQLite persistence.  Owner: BE3

Deliberately plain `sqlite3` - no ORM. Five developers on a three-day build do
not need to learn a mapping layer, and the schema is eight tables of flat rows.
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    case_id           TEXT PRIMARY KEY,
    fir_ref           TEXT NOT NULL,
    ncrp_ref          TEXT NOT NULL,
    victim_name       TEXT NOT NULL,
    victim_amount_inr REAL NOT NULL,
    incident_datetime TEXT NOT NULL,
    seed_wallet       TEXT,
    seed_utr          TEXT,
    io_name           TEXT NOT NULL,
    notes             TEXT DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'active',
    data_mode         TEXT NOT NULL DEFAULT 'synthetic',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id    TEXT PRIMARY KEY,
    case_id        TEXT NOT NULL REFERENCES cases(case_id),
    filename       TEXT NOT NULL,
    file_type      TEXT NOT NULL,
    size_bytes     INTEGER NOT NULL,
    sha256_client  TEXT NOT NULL,
    sha256_server  TEXT NOT NULL,
    hash_match     INTEGER NOT NULL,
    is_synthetic   INTEGER NOT NULL DEFAULT 1,
    row_count      INTEGER,
    column_mapping TEXT,
    uploaded_at    TEXT NOT NULL,
    uploaded_by    TEXT NOT NULL
);

-- Append-only. There is intentionally no UPDATE or DELETE path: the chain of
-- custody must remain reconstructible after the fact.
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id    TEXT PRIMARY KEY,
    case_id     TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    action      TEXT NOT NULL,
    target      TEXT NOT NULL,
    target_hash TEXT,
    details     TEXT NOT NULL DEFAULT '{}',
    -- Tamper-evidence: each row commits to the one before it. Editing or
    -- deleting any row breaks every subsequent link, which /audit reports.
    -- `seq` makes the chain's order explicit rather than relying on SQLite's
    -- rowid, which is not preserved across a dump and restore.
    seq         INTEGER NOT NULL DEFAULT 0,
    prev_hash   TEXT NOT NULL DEFAULT '',
    entry_hash  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS users (
    user_id       TEXT PRIMARY KEY,
    display_name  TEXT NOT NULL,
    rank          TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    active        INTEGER NOT NULL DEFAULT 1
);

-- Transfers parsed out of uploaded evidence. Kept separate from the bundled
-- dataset so the demo case stays reproducible and an ingestion can be
-- attributed back to the exact file it came from.
CREATE TABLE IF NOT EXISTS ingested_txn (
    edge_id       TEXT PRIMARY KEY,
    case_id       TEXT NOT NULL,
    evidence_id   TEXT NOT NULL,
    from_node     TEXT NOT NULL,
    to_node       TEXT NOT NULL,
    amount        REAL NOT NULL,
    asset         TEXT NOT NULL,
    timestamp     TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    utr           TEXT,
    tx_hash       TEXT
);

CREATE INDEX IF NOT EXISTS idx_ingested_case ON ingested_txn(case_id);
CREATE INDEX IF NOT EXISTS idx_evidence_case ON evidence(case_id);
CREATE INDEX IF NOT EXISTS idx_audit_case    ON audit_log(case_id, timestamp);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def cursor(path: Path | None = None):
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(path: Path | None = None) -> None:
    with cursor(path) as conn:
        conn.executescript(SCHEMA)


def healthy() -> bool:
    try:
        with cursor() as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except sqlite3.Error:
        return False


def row_to_case(r: sqlite3.Row) -> dict:
    return dict(r)


def row_to_evidence(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["hash_match"] = bool(d["hash_match"])
    d["is_synthetic"] = bool(d["is_synthetic"])
    d["column_mapping"] = json.loads(d["column_mapping"]) if d["column_mapping"] else None
    return d


def ingested_edges(case_id: str) -> list[dict]:
    """Transfers parsed from evidence uploaded against this case."""
    with cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM ingested_txn WHERE case_id = ? ORDER BY timestamp",
            (case_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def row_to_audit(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["details"] = json.loads(d["details"] or "{}")
    return d
