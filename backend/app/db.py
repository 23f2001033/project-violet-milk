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
    details     TEXT NOT NULL DEFAULT '{}'
);

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


def row_to_audit(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["details"] = json.loads(d["details"] or "{}")
    return d
