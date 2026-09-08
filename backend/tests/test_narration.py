"""
Bank narration parsing - reading the counterparty an Indian statement records.

This is the field the whole INR side of a case turns on, and it is the field
most easily over-read. The tests below are weighted accordingly: more of them
guard against claiming too much than against extracting too little.
"""

import pytest

from backend.app.services import narration
from backend.app.services.ingestion import normalise_rows

STATEMENT = b"""Txn Date,Narration,Withdrawal Amt.,Chq/Ref Number
08/09/2026,UPI/DR/412345678901/RAHUL K/YESB/rahul@ybl/Payment,"4,70,000.00",412345678901
08/09/2026,IMPS/P2A/509812345678/PRIYA S/HDFC,"1,20,000.00",509812345678
08/09/2026,BY CASH DEPOSIT,"50,000.00",778899001122
"""

MAPPING = {"timestamp": "Txn Date", "description": "Narration",
           "amount": "Withdrawal Amt.", "utr": "Chq/Ref Number"}


# ----------------------------------------------------------- what it reads

@pytest.mark.parametrize("text,rail", [
    ("UPI/DR/412345678901/RAHUL K/YESB/rahul@ybl/Payment", "UPI"),
    ("IMPS/P2A/509812345678/PRIYA S/HDFC", "IMPS"),
    ("NEFT-SBIN0001234-ACME TRADING", "NEFT"),
    ("RTGS CREDIT FROM XYZ", "RTGS"),
    ("BY CASH DEPOSIT", None),
])
def test_it_identifies_the_rail(text, rail):
    assert narration.parse(text).rail == rail


@pytest.mark.parametrize("text,vpa", [
    ("UPI/DR/412345678901/RAHUL K/YESB/rahul@ybl/Payment", "rahul@ybl"),
    # A hyphen is a field delimiter here, and the VPA must not run backwards
    # over it into the preceding name.
    ("UPI-RAHUL KUMAR-RAHUL@OKAXIS-YESB0YESUPI-412345678901", "rahul@okaxis"),
    # A hyphen is ALSO legal inside a VPA, and one must survive.
    ("UPI/DR/998877665544/PRIYA/rahul.k-1@okhdfcbank/", "rahul.k-1@okhdfcbank"),
    ("IMPS/P2A/509812345678/RAHUL/HDFC", None),
])
def test_it_extracts_the_virtual_payment_address(text, vpa):
    """A wrong VPA is worse than none: a production order recites it verbatim,
    and a bank asked about an address that does not exist answers nothing."""
    assert narration.parse(text).vpa == vpa


def test_it_names_the_psp_bank_behind_a_handle():
    f = narration.parse("UPI/DR/1/X/YESB/someone@ybl/Payment")
    assert f.psp_handle == "ybl"
    assert f.psp_bank == "Yes Bank"


def test_an_unknown_handle_is_reported_as_unidentified():
    f = narration.parse("UPI/DR/1/X/someone@notarealpsp/Payment")
    assert f.psp_bank is None
    assert any("not in the curated PSP list" in n for n in f.notes)


def test_it_reads_the_ifsc_and_the_reference():
    f = narration.parse("NEFT-HDFC0001234-412345678901-ACME TRADING")
    assert f.ifsc == "HDFC0001234"
    assert f.reference == "412345678901"


# --------------------------------------------------- what it refuses to claim

def test_a_handle_is_never_reported_as_a_platform():
    """THE guarantee. @ybl is Yes Bank, the payment service provider. It says
    nothing about whether the VPA belongs to an exchange, and inferring one
    would be the same fabrication this project refuses everywhere else."""
    f = narration.parse("UPI/DR/1/X/YESB/binance@ybl/Payment")
    assert f.psp_bank == "Yes Bank"
    joined = " ".join(f.notes)
    assert "not the business behind" in joined
    assert "94 BNSS" in joined
    # The local part is data, never an identification.
    assert "exchange" not in joined.lower().replace("exchange to", "")


def test_a_transaction_descriptor_is_not_a_counterparty():
    """"BY CASH DEPOSIT" names nobody. Reporting it as an identified party
    would inflate what the statement establishes."""
    f = narration.parse("BY CASH DEPOSIT")
    assert f.counterparty_name is None
    assert f.identifies_counterparty is False
    assert any("no counterparty" in n for n in f.notes)


def test_an_empty_narration_establishes_nothing():
    for value in (None, "", "   "):
        f = narration.parse(value)
        assert f.rail is None and f.vpa is None
        assert f.identifies_counterparty is False


# ------------------------------------------------------------ in ingestion

def test_ingestion_reads_the_narration_it_used_to_discard():
    """The column mapper always identified this column; ingestion threw it
    away, so a statement produced a counterparty called UTR:... and no more."""
    rows, report = normalise_rows(STATEMENT, MAPPING, "CASE", "EV", "SBI_TEST")
    assert report["ingested"] == 3
    assert rows[0]["narration"]["vpa"] == "rahul@ybl"
    assert rows[0]["narration"]["rail"] == "UPI"
    assert rows[0]["narration"]["counterparty_name"] == "RAHUL K"


def test_the_report_counts_what_was_established():
    rows, report = normalise_rows(STATEMENT, MAPPING, "CASE", "EV", "SBI_TEST")
    n = report["narration"]
    assert n["rows_naming_a_counterparty"] == 2   # the cash deposit names none
    assert n["rails_seen"] == ["IMPS", "UPI"]
    assert n["vpas_found"] == ["rahul@ybl"]
    assert "94 BNSS" in n["note"]


def test_the_counterparty_node_is_still_utr_identified():
    """Narration enriches the row; it does not rename the node. A statement
    still names one side only, and the counterparty stays explicitly
    unidentified until a bank answers for it."""
    rows, _ = normalise_rows(STATEMENT, MAPPING, "CASE", "EV", "SBI_TEST")
    assert all(r["to_node"].startswith("UTR:") for r in rows)


def test_a_statement_without_a_narration_column_still_ingests():
    plain = b"""Txn Date,Withdrawal Amt.,Chq/Ref Number
08/09/2026,"1,000.00",111222333444
"""
    rows, report = normalise_rows(
        plain, {"timestamp": "Txn Date", "amount": "Withdrawal Amt.",
                "utr": "Chq/Ref Number"}, "CASE", "EV", "SBI_TEST")
    assert report["ingested"] == 1
    assert rows[0]["narration"] is None
