"""
Evidence ingestion - turning an uploaded CSV into graph edges.  Owner: BE3

Until now the uploader hashed, stored, column-mapped and audited a file, and
then the trace ignored it entirely: the graph always read the bundled dataset.
A judge who uploaded a file and asked "now show me that data" would have found
nothing. This module closes that gap.

TWO SHAPES, because real evidence arrives in two forms
------------------------------------------------------
TRANSFER LIST - the CSV names both ends of each movement (from/to columns).
Each row becomes a direct edge. This is what a wallet export or a curated
case file looks like.

BANK STATEMENT - the far more common case, and the awkward one. A statement is
ONE ACCOUNT'S LEDGER: it has a UTR, a date and an amount, but it does not name
the counterparty. There is no honest way to invent one, so each row becomes an
edge between the statement's account and a counterparty node identified ONLY
by its UTR - `UTR:420192830192`. That node is explicitly unidentified, which
is exactly what the evidence supports. Resolving it to a real party requires a
Section 94 BNSS production order to the bank.

Amounts and dates are parsed defensively: Indian statements carry
"4,70,000.00 Dr", bare lakh grouping, and at least three date orderings.
A row that cannot be parsed is skipped and counted, never guessed at.
"""

from __future__ import annotations

import csv
import io
import re
import uuid
from datetime import datetime, timezone

from ..models import Asset, EvidenceType
from . import narration as narration_service

# Indian statements: "4,70,000.00 Dr", "(1,200.50)", "INR 5,200", "-470000"
_AMOUNT_CLEAN = re.compile(r"[^\d.\-]")
_DEBIT_MARK = re.compile(r"\b(dr|debit|withdrawal)\b", re.I)

_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
    "%d-%m-%Y %H:%M:%S", "%d-%m-%Y", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y",
    "%d-%m-%y", "%d/%m/%y", "%d-%b-%Y", "%d %b %Y", "%m/%d/%Y",
)


def parse_amount(raw: str) -> float | None:
    """Return a positive magnitude, or None if the cell is not a number.

    Sign and Dr/Cr markers are deliberately discarded: direction is carried by
    the edge, not by the number, and a statement's sign convention depends on
    whose account it is.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    bracketed = text.startswith("(") and text.endswith(")")
    cleaned = _AMOUNT_CLEAN.sub("", text)
    if not cleaned or cleaned in {"-", ".", "-."}:
        return None
    try:
        value = abs(float(cleaned))
    except ValueError:
        return None
    return value if (value or bracketed) else None


def parse_timestamp(raw: str) -> str | None:
    """ISO 8601 with an offset, or None.

    Dates without a timezone are read as IST, because these are Indian bank
    records - assuming UTC would shift every event by five and a half hours
    and quietly corrupt the timeline deltas.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text)
        return dt.isoformat() if dt.tzinfo else f"{dt.isoformat()}+05:30"
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return dt.isoformat() if dt.tzinfo else f"{dt.isoformat()}+05:30"
    return None


def _asset_for(raw: str | None) -> Asset:
    token = (raw or "").strip().upper()
    if token in {"USDT", "USDC", "DAI"}:
        return Asset.USDT
    if token == "ETH":
        return Asset.ETH
    return Asset.INR


def normalise_rows(
    raw_csv: bytes,
    mapping: dict[str, str],
    case_id: str,
    evidence_id: str,
    account_ref: str | None = None,
) -> tuple[list[dict], dict]:
    """Convert an uploaded CSV into edge dicts.

    Returns (rows, report). The report is surfaced to the officer so a partial
    ingestion is visible rather than silent - a file where half the rows failed
    to parse must not look like a clean import.
    """
    text = raw_csv.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    col_from = mapping.get("from_account")
    col_to = mapping.get("to_account")
    col_amount = mapping.get("amount")
    col_time = mapping.get("timestamp")
    col_utr = mapping.get("utr")
    col_asset = mapping.get("asset")
    col_bank = mapping.get("bank")
    col_desc = mapping.get("description")

    shape = "transfer_list" if (col_from and col_to) else "bank_statement"
    rows: list[dict] = []
    skipped: list[str] = []

    for n, r in enumerate(reader, start=2):          # row 1 is the header
        amount = parse_amount(r.get(col_amount)) if col_amount else None
        ts = parse_timestamp(r.get(col_time)) if col_time else None
        utr = (r.get(col_utr) or "").strip() if col_utr else ""
        # The narration is the ONLY column in an Indian statement that says
        # anything about who received the money. It was mapped and then
        # discarded, so a statement produced a counterparty called
        # "UTR:412345678901" and nothing else.
        facts = narration_service.parse(r.get(col_desc) if col_desc else None)

        if amount is None:
            skipped.append(f"row {n}: no readable amount")
            continue
        if ts is None:
            skipped.append(f"row {n}: no readable date")
            continue

        if shape == "transfer_list":
            src = (r.get(col_from) or "").strip()
            dst = (r.get(col_to) or "").strip()
            if not src or not dst:
                skipped.append(f"row {n}: missing counterparty")
                continue
            evidence_type = EvidenceType.CONFIRMED_ONCHAIN if src.startswith("0x") \
                else EvidenceType.CONFIRMED_BANK
        else:
            # A statement names one side only. The counterparty is recorded as
            # unidentified-but-referenced rather than invented.
            account = (
                account_ref
                or (r.get(col_bank) or "").strip()
                or "STATEMENT ACCOUNT"
            )
            if not utr:
                skipped.append(f"row {n}: no UTR to identify the counterparty")
                continue
            src, dst = account, f"UTR:{utr}"
            evidence_type = EvidenceType.CONFIRMED_BANK

        rows.append({
            "edge_id": f"ING-{uuid.uuid4().hex[:10]}",
            "case_id": case_id,
            "evidence_id": evidence_id,
            "from_node": src,
            "to_node": dst,
            "amount": amount,
            "asset": _asset_for(r.get(col_asset) if col_asset else None).value,
            "timestamp": ts,
            "evidence_type": evidence_type.value,
            "utr": utr or None,
            "tx_hash": None,
            # Read from the evidence, never inferred. The VPA is what makes a
            # production order to the bank answerable: "who owns this handle"
            # is a far more direct question than "who received this UTR".
            "narration": facts.as_dict() if facts.raw else None,
        })

    named = [r for r in rows if (r.get("narration") or {}).get(
        "identifies_counterparty")]
    vpas = sorted({r["narration"]["vpa"] for r in named
                   if r["narration"].get("vpa")})
    rails = sorted({r["narration"]["rail"] for r in rows
                    if (r.get("narration") or {}).get("rail")})

    report = {
        "shape": shape,
        "ingested": len(rows),
        # What the narration actually established, stated as a count rather
        # than a claim about any one platform.
        "narration": {
            "rows_naming_a_counterparty": len(named),
            "rails_seen": rails,
            "vpas_found": vpas,
            "note": (
                "A VPA identifies a payment handle, not the business behind "
                "it. Establishing who operates one requires the bank to "
                "answer a Section 94 BNSS 2023 production order."
            ),
        },
        "skipped": len(skipped),
        # Cap the reasons: a badly-formed file should not produce a wall of text.
        "reasons": skipped[:8],
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }
    return rows, report
