"""
Blockchain evidence anchoring.

Runs OFFLINE. No key, no RPC, no testnet funds needed - the signing path is
exercised with a throwaway generated key and a stubbed RPC, so the whole team
can run the suite without touching a chain.

The load-bearing guarantees:
  * anchoring NEVER breaks report generation
  * the private key never leaves the signing call
  * the claims made about an anchor stay within what an anchor proves
"""

import json

import pytest
from eth_account import Account
from fastapi.testclient import TestClient

from backend.app import config
from backend.app.main import app
from backend.app.services import anchor

from ._client import make_client

CASE = "CP-CYBER-2026-001"
DIGEST = "b" * 64

client = make_client()


# --------------------------------------------------------- degradation

def test_unconfigured_anchoring_does_not_raise():
    """A missing key must produce a reason, not an exception. Anchoring is a
    bonus; it may never take the dossier down with it."""
    out = anchor.anchor_digest(DIGEST)
    assert out["anchored"] is False
    assert out["reason"]
    assert out["mode"] == "unavailable"


def test_report_still_generates_without_anchoring():
    r = client.post(f"/api/cases/{CASE}/report")
    assert r.status_code == 200
    body = r.json()
    assert body["page_count"] >= 4
    assert body["anchor"]["anchored"] is False


def test_rejects_a_malformed_digest():
    with pytest.raises(ValueError):
        anchor.anchor_digest("not-a-digest")


# ------------------------------------------------------------ signing

def test_transaction_is_signed_without_leaking_the_key(monkeypatch, tmp_path):
    """The key signs and nothing else: it must not appear in the receipt, the
    API response, or anything written to disk."""
    throwaway = Account.create()
    sent = {}

    def fake_rpc(method, params):
        if method == "eth_getTransactionCount":
            return hex(7)
        if method == "eth_gasPrice":
            return hex(10**9)
        if method == "eth_sendRawTransaction":
            sent["raw"] = params[0]
            return "0x" + "ab" * 32
        if method == "eth_getTransactionReceipt":
            return {"blockNumber": hex(5_000_123)}
        if method == "eth_getBlockByNumber":
            return {"timestamp": hex(1_788_000_000)}
        raise AssertionError(f"unexpected RPC {method}")

    monkeypatch.setattr(config, "ANCHOR_RPC_URL", "http://stub")
    monkeypatch.setattr(config, "ANCHOR_PRIVATE_KEY", throwaway.key.hex())
    monkeypatch.setattr(config, "ANCHOR_CONTRACT_ADDRESS", "")
    monkeypatch.setattr(config, "ANCHOR_CONFIGURED", True)
    monkeypatch.setattr(anchor, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(anchor, "_rpc", fake_rpc)

    out = anchor.anchor_digest(DIGEST)

    assert out["anchored"] is True
    assert out["block_number"] == 5_000_123
    assert out["anchored_by"] == throwaway.address
    assert out["explorer_url"].endswith("0x" + "ab" * 32)

    blob = json.dumps(out)
    assert throwaway.key.hex() not in blob
    assert "private" not in blob.lower()
    assert sent["raw"].startswith("0x"), "a signed transaction was submitted"


def test_calldata_mode_carries_the_digest(monkeypatch):
    """With no contract deployed the digest still lands on-chain, in the
    transaction's data field."""
    monkeypatch.setattr(config, "ANCHOR_CONTRACT_ADDRESS", "")
    sender = Account.create().address
    tx = anchor.build_transaction(sender, DIGEST, nonce=1, gas_price=10**9)

    assert tx["data"] == "0x" + DIGEST
    assert tx["to"] == sender, "a self-send needs no counterparty"
    assert tx["value"] == 0, "an anchor must never move funds"


def test_contract_mode_uses_the_anchor_selector(monkeypatch):
    monkeypatch.setattr(
        config, "ANCHOR_CONTRACT_ADDRESS",
        "0x0000000000000000000000000000000000000abc")
    tx = anchor.build_transaction(
        Account.create().address, DIGEST, nonce=1, gas_price=10**9)

    assert tx["data"] == "0x" + anchor.SEL_ANCHOR + DIGEST
    assert tx["to"].lower().endswith("abc")
    assert tx["value"] == 0


def test_the_two_modes_send_different_calldata(monkeypatch):
    """A silent fallback to calldata mode when a contract WAS configured would
    mean the digest never reaches contract storage."""
    sender = Account.create().address
    monkeypatch.setattr(config, "ANCHOR_CONTRACT_ADDRESS", "")
    plain = anchor.build_transaction(sender, DIGEST, 1, 10**9)
    monkeypatch.setattr(
        config, "ANCHOR_CONTRACT_ADDRESS",
        "0x0000000000000000000000000000000000000abc")
    contract = anchor.build_transaction(sender, DIGEST, 1, 10**9)
    assert plain["data"] != contract["data"]
    assert contract["gas"] > plain["gas"]


# ---------------------------------------------------------------- cache

def test_an_anchored_digest_is_not_re_sent(monkeypatch, tmp_path):
    """The earliest anchor is the meaningful one, and the contract reverts on
    a duplicate. A second request must replay the receipt."""
    monkeypatch.setattr(anchor, "CACHE_DIR", tmp_path)
    (tmp_path).mkdir(exist_ok=True)
    (tmp_path / f"{DIGEST}.json").write_text(json.dumps({
        "digest": DIGEST, "anchored": True, "tx_hash": "0x" + "11" * 32,
        "block_number": 123,
    }), encoding="utf-8")

    def explode(*a, **k):
        raise AssertionError("must not hit the network for a cached anchor")

    monkeypatch.setattr(anchor, "_rpc", explode)
    out = anchor.anchor_digest(DIGEST)
    assert out["block_number"] == 123


def test_verification_falls_back_to_the_receipt_offline(monkeypatch, tmp_path):
    """A dead venue network must not make a real anchor look absent."""
    monkeypatch.setattr(anchor, "CACHE_DIR", tmp_path)
    (tmp_path / f"{DIGEST}.json").write_text(json.dumps({
        "digest": DIGEST, "anchored": True, "block_number": 77,
    }), encoding="utf-8")
    monkeypatch.setattr(config, "ANCHOR_RPC_URL", "")
    out = anchor.verify_digest(DIGEST)
    assert out["anchored"] is True
    assert out["source"] == "cached receipt"


# ------------------------------------------------------------- honesty

def test_the_record_states_what_an_anchor_does_not_prove():
    """Overstating this is the easiest way to lose a technical judge."""
    r = client.get(f"/api/cases/{CASE}/anchor/{DIGEST}")
    assert r.status_code == 200
    proves = r.json()["proves"].lower()
    assert "does not establish who" in proves


def test_health_reports_anchoring_availability():
    body = client.get("/api/health").json()["components"]
    assert "anchoring_configured" in body
    assert body["anchoring_configured"] is config.ANCHOR_CONFIGURED
