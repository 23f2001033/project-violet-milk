"""
AI feature 1 — bank CSV column mapper.  Owner: BE3

Every Indian bank exports a different statement layout. SBI writes "Txn Date",
HDFC "Value Dt", ICICI "Transaction Date"; amounts arrive as "1,20,000.00 Dr"
or split across "Withdrawal Amt." and "Deposit Amt.". Regex alone breaks on the
first unseen format, which is precisely the kind of messy-language problem a
model is good at and a rule is not.

This is a legitimate use of AI: it maps HEADERS, never values, and never
influences a risk score. A deterministic heuristic runs first, and the model is
consulted only for the columns the heuristic could not resolve - so the feature
degrades to "slightly worse mapping", never to a broken upload.
"""

from __future__ import annotations

import json
import re

from . import llm_client

# Canonical fields the case schema needs from a bank statement.
TARGETS = {
    "from_account": "the sending account, wallet address or payer",
    "to_account": "the receiving account, wallet address or payee",
    "asset": "the currency or token symbol (INR, USDT, ETH)",
    "utr": "the UTR / RRN / transaction reference number",
    "amount": "the debited or transferred amount",
    "timestamp": "the transaction date or datetime",
    "bank": "the bank or branch name",
    "description": "the narration or remarks",
}

# Classification is HEADER-FIRST and ordered by specificity, not field-first.
#
# A field-first loop is subtly wrong: iterating fields and grabbing the first
# matching header lets an early, broad pattern steal a header that belongs to a
# later field. With "amount" checked before "timestamp", the header "Value Dt"
# matched amount's \bvalue\b and was mapped as the transaction amount - a DATE
# column silently read as money. Classifying each header once, most-specific
# rule first, removes that whole class of error.
_RULES: tuple[tuple[str, str], ...] = (
    # Direction first. "from"/"to" are unambiguous, and leaving them until
    # after the broader patterns lets "To Address" get claimed as something
    # else - which would silently reverse the direction of every edge.
    ("from_account",
     r"\b(from|sender|payer|source|remitter|from[ _]?address|"
     r"from[ _]?account|from[ _]?wallet)\b"),
    ("to_account",
     r"\b(to|receiver|payee|beneficiary|destination|to[ _]?address|"
     r"to[ _]?account|to[ _]?wallet)\b"),
    # Dates next: they are the most commonly mis-claimed.
    ("timestamp", r"\b(date|dt|time|timestamp|datetime|posted|txn[ _]?dt)\b"),
    ("utr", r"\b(utr|rrn|ref(erence)?[ _]?(no|num|number|id)?|txn[ _]?id|"
            r"transaction[ _]?id|cheque|chq)\b"),
    # "balance" is deliberately excluded - a closing balance is not the
    # transferred amount.
    ("amount", r"\b(amount|amt|debit|withdrawal|deposit|credit|inr|rs|value)\b"),
    ("asset", r"\b(asset|currency|token|symbol|ccy)\b"),
    ("bank", r"\b(bank|branch|ifsc|institution)\b"),
    # Plurals matter: "Transaction Remarks" must match, and \bremark\b does not.
    ("description", r"\b(desc|descriptions?|narrations?|remarks?|"
                    r"particulars?|details?)\b"),
)


def heuristic_map(headers: list[str]) -> dict[str, str]:
    """Best-effort mapping with no network call. Always runs first."""
    out: dict[str, str] = {}
    for h in headers:
        norm = h.strip().lower().replace(".", " ").replace("/", " ")
        for field, pattern in _RULES:
            if field in out:
                continue
            if re.search(pattern, norm):
                out[field] = h
                break
    return out


SYSTEM = (
    "You map bank-statement CSV column headers onto a fixed schema for an "
    "Indian police cyber-crime case file. Reply with JSON only - no prose, no "
    "code fences. Keys are the schema fields; values are the EXACT header "
    "string from the supplied list. Omit any field with no clear match. Never "
    "invent a header that is not in the list."
)


def ai_map(headers: list[str]) -> tuple[dict[str, str], str]:
    fields = "\n".join(f"- {k}: {v}" for k, v in TARGETS.items())
    user = (
        f"Schema fields:\n{fields}\n\n"
        f"CSV headers:\n{json.dumps(headers)}\n\n"
        'Return JSON like {"utr": "<header>", "amount": "<header>"}.'
    )
    content, provenance = llm_client.complete(SYSTEM, user, max_tokens=700)
    if not content:
        return {}, provenance

    # Models sometimes wrap JSON in fences despite instructions.
    text = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.MULTILINE)
    try:
        parsed = json.loads(text.strip())
    except json.JSONDecodeError:
        return {}, "unavailable"

    # Trust nothing: keep only mappings that name a real header.
    valid = {
        k: v for k, v in parsed.items()
        if k in TARGETS and isinstance(v, str) and v in headers
    }
    return valid, provenance


def map_columns(headers: list[str]) -> tuple[dict[str, str], str]:
    """Return (mapping, provenance).

    The heuristic result is the floor. AI is asked only about what is still
    missing, and its answer is accepted only for those gaps - so a confused
    model can add coverage but never overwrite a confident local match.
    """
    base = heuristic_map(headers)
    if len(base) == len(TARGETS):
        return base, "heuristic"

    ai, provenance = ai_map(headers)
    if not ai:
        return base, "heuristic"

    merged = dict(base)
    for field, header in ai.items():
        if field not in merged and header not in merged.values():
            merged[field] = header
    return merged, f"heuristic+{provenance}"
