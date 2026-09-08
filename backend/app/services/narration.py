"""
Bank narration parser - reading the one field that actually carries a
counterparty in an Indian statement.

WHY THIS EXISTS
---------------
The rest of this system starts at a wallet address. An Indian investigating
officer does not: he starts with a bank statement, and the only column that
says anything about WHO received the money is the narration.

    UPI/DR/412345678901/RAHUL K/YESB/rahul@ybl/Payment
    UPI-RAHUL KUMAR-RAHUL@OKAXIS-YESB0YESUPI-412345678901-PAYMENT
    IMPS/P2A/509812345678/RAHUL/HDFC
    NEFT-SBIN524110022-ACME TRADING

The column mapper already identifies that column. Until now ingestion threw it
away, so a statement produced a counterparty called `UTR:412345678901` and
nothing else - technically honest, and far less than the evidence supports.

WHAT IT ESTABLISHES, AND WHAT IT DOES NOT
-----------------------------------------
It establishes the RAIL (UPI, IMPS, NEFT, RTGS), the counterparty's VIRTUAL
PAYMENT ADDRESS where one is present, the PSP handle, and the beneficiary name
string as the bank recorded it.

It does NOT establish which platform received the money. A handle suffix names
the payment service provider - @ybl is Yes Bank, @okaxis is Axis - not the
business behind the VPA. Deciding that `rahul@ybl` belongs to an exchange
requires the bank to say so, which is what a Section 94 BNSS order asks for.
Guessing it from a string would be exactly the fabrication this system refuses
everywhere else.

The value is that the order can now cite a VPA instead of only a UTR, and a
bank can answer "who owns this VPA" far more directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Rails in the order they are worth testing for: UPI dominates retail fraud,
# IMPS and NEFT carry the larger transfers.
RAIL_PATTERNS = [
    ("UPI", re.compile(r"\bUPI\b", re.I)),
    ("IMPS", re.compile(r"\bIMPS\b", re.I)),
    ("NEFT", re.compile(r"\bNEFT\b", re.I)),
    ("RTGS", re.compile(r"\bRTGS\b", re.I)),
    ("ATM", re.compile(r"\bATM\b|\bNWD\b", re.I)),
    ("CARD", re.compile(r"\bPOS\b|\bECOM\b", re.I)),
]

# A VPA is name@handle, matched WHOLE against one delimiter-separated fragment
# rather than searched across the narration. Searching the full string let the
# local part run backwards over a hyphen, so
# "UPI-RAHUL KUMAR-RAHUL@OKAXIS" produced "kumar-rahul@okaxis" - a VPA that
# does not exist, in a field a production order recites verbatim.
VPA = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]{1,48})@([A-Za-z]{2,20})$")

# Fragments that describe the transaction rather than name a party. Without
# this, "BY CASH DEPOSIT" was reported as an identified counterparty.
NOT_A_PARTY = {
    "BY CASH DEPOSIT", "CASH DEPOSIT", "CASH WITHDRAWAL", "ATM WDL",
    "SELF", "TO SELF", "BY TRANSFER", "TRANSFER", "PAYMENT", "PAYMENTS",
    "SERVICE CHARGES", "CHARGES", "INTEREST", "REVERSAL", "REFUND",
    "OPENING BALANCE", "CLOSING BALANCE", "SALARY", "DEPOSIT",
}

# Indian IFSC: four letters, a zero, then six alphanumerics.
IFSC = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")

# A long digit run in a narration is the payment reference the bank assigned.
REFERENCE = re.compile(r"\b(\d{9,22})\b")

# Handles seen widely enough to name the PSP behind them. This maps a handle
# to a BANK, never to a platform, and it is deliberately short - the same
# discipline known_addresses.json follows.
PSP_BANKS = {
    "ybl": "Yes Bank", "okaxis": "Axis Bank", "oksbi": "State Bank of India",
    "okhdfcbank": "HDFC Bank", "okicici": "ICICI Bank", "axl": "Axis Bank",
    "ibl": "IDBI Bank", "upi": "not specific to one PSP",
    "paytm": "Paytm Payments Bank", "apl": "Axis Bank",
    "yapl": "Yes Bank", "jupiteraxis": "Axis Bank",
}

NOT_A_PLATFORM = (
    "A handle names the payment service provider bank, not the business behind "
    "the VPA. Establishing who operates this VPA requires the bank to answer a "
    "Section 94 BNSS 2023 production order."
)


@dataclass
class NarrationFacts:
    raw: str
    rail: str | None = None
    vpa: str | None = None
    psp_handle: str | None = None
    psp_bank: str | None = None
    counterparty_name: str | None = None
    ifsc: str | None = None
    reference: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def identifies_counterparty(self) -> bool:
        """True when the evidence names a party, not merely a reference."""
        return bool(self.vpa or self.counterparty_name)

    def as_dict(self) -> dict:
        return {
            "raw": self.raw,
            "rail": self.rail,
            "vpa": self.vpa,
            "psp_handle": self.psp_handle,
            "psp_bank": self.psp_bank,
            "counterparty_name": self.counterparty_name,
            "ifsc": self.ifsc,
            "reference": self.reference,
            "identifies_counterparty": self.identifies_counterparty,
            "notes": self.notes,
        }


def _name_from(parts: list[str], vpa: str | None) -> str | None:
    """The beneficiary name as the bank recorded it.

    A narration is delimited fragments. The name is the fragment that is
    mostly letters and spaces, is not a rail keyword, and is not the VPA.
    Anything ambiguous is left alone rather than guessed.
    """
    rails = {r for r, _ in RAIL_PATTERNS}
    for p in parts:
        token = p.strip()
        if not token or len(token) < 3 or len(token) > 60:
            continue
        upper = token.upper()
        if upper in rails or upper in {"DR", "CR", "P2A", "P2P"}:
            continue
        if upper in NOT_A_PARTY:
            continue
        if vpa and token.lower() in vpa.lower():
            continue
        if IFSC.fullmatch(token) or token.isdigit():
            continue
        letters = sum(c.isalpha() or c.isspace() for c in token)
        if letters == len(token) and any(c.isalpha() for c in token):
            return token.strip()
    return None


def parse(narration: str | None) -> NarrationFacts:
    """Read what the bank recorded. Never more than that."""
    raw = (narration or "").strip()
    facts = NarrationFacts(raw=raw)
    if not raw:
        return facts

    for name, pattern in RAIL_PATTERNS:
        if pattern.search(raw):
            facts.rail = name
            break

    # Order matters. A hyphen is BOTH a legal character inside a VPA
    # (rahul.k-1@okhdfcbank) and a field delimiter in some banks' narrations
    # (UPI-NAME-VPA-IFSC). So try each whitespace/slash fragment whole first,
    # which keeps a hyphenated VPA intact, and only then split on hyphens,
    # which recovers the VPA from a hyphen-delimited narration. Doing it the
    # other way round loses real addresses; doing only the first invents them.
    fragments = [f.strip() for f in re.split(r"[/|,;\s]+", raw) if f.strip()]
    hyphen_pieces = [x for f in fragments for x in f.split("-") if x]

    m = next((VPA.match(x) for x in fragments if VPA.match(x)), None)
    if not m:
        m = next((VPA.match(x) for x in hyphen_pieces if VPA.match(x)), None)
    if m:
        facts.vpa = f"{m.group(1)}@{m.group(2)}".lower()
        facts.psp_handle = m.group(2).lower()
        facts.psp_bank = PSP_BANKS.get(facts.psp_handle)
        facts.notes.append(NOT_A_PLATFORM)
        if not facts.psp_bank:
            facts.notes.append(
                f"Handle @{facts.psp_handle} is not in the curated PSP list, "
                "so the provider behind it is not identified.")

    ifsc = IFSC.search(raw)
    if ifsc:
        facts.ifsc = ifsc.group(1)

    ref = REFERENCE.search(raw)
    if ref:
        facts.reference = ref.group(1)

    parts = re.split(r"[/\-|,;]+", raw)
    facts.counterparty_name = _name_from(parts, facts.vpa)

    if not facts.identifies_counterparty:
        facts.notes.append(
            "This narration carries no counterparty. The recipient remains "
            "identified only by its payment reference.")

    return facts
