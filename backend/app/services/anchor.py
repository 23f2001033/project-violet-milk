"""
Blockchain evidence anchoring.  Owner: BE1

Publishes the SHA-256 of a generated dossier to a public chain, so the fact
that the document existed at a given time survives independently of this
server.

WHAT AN ANCHOR PROVES - and the limits, which must travel with every claim
-------------------------------------------------------------------------
PROVES   the digest existed at or before the anchoring block, and that record
         cannot be revised afterwards. If this machine is later compromised,
         rebuilt, or its database rewritten, the on-chain record still stands
         and a substituted PDF will not match it.

DOES NOT prove who wrote the document. Anyone can anchor any digest.
DOES NOT make the document tamper-proof - it makes substitution DETECTABLE.
DOES NOT give a precise clock: `block.timestamp` is proposer-set and drifts by
         seconds. Say "at or before block N", never "at 10:35:02".

Two levels of guarantee, chosen by configuration:

  CONTRACT MODE  a call to EvidenceAnchor.anchor(bytes32). The digest lands in
                 contract storage and an indexed event, so it is queryable by
                 anyone forever.
  CALLDATA MODE  a zero-value self-transaction carrying the digest in the data
                 field. Needs no deployed contract, costs less, and is still
                 permanently readable - the fallback when no contract address
                 is configured.

Receipts are cached to disk. Anchor once before the demo and the dossier can
cite the transaction with the network unplugged.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx
from eth_account import Account
from eth_utils import keccak, to_checksum_address

from .. import config

log = logging.getLogger(__name__)

CACHE_DIR = config.DATA_DIR / "anchors"

# keccak("anchor(bytes32)")[:4] and keccak("anchorOf(bytes32)")[:4]
SEL_ANCHOR = keccak(text="anchor(bytes32)")[:4].hex()
SEL_ANCHOR_OF = keccak(text="anchorOf(bytes32)")[:4].hex()

EXPLORERS = {
    1: "https://etherscan.io",
    11155111: "https://sepolia.etherscan.io",
    17000: "https://holesky.etherscan.io",
}


def explorer_tx(tx_hash: str, chain_id: int) -> str:
    base = EXPLORERS.get(chain_id, "https://etherscan.io")
    return f"{base}/tx/{tx_hash}"


def build_transaction(sender: str, digest: str, nonce: int,
                      gas_price: int) -> dict[str, Any]:
    """Construct the anchoring transaction.

    Extracted so the two modes can be asserted directly, without reaching
    into eth-account's signing internals from a test.
    """
    if config.ANCHOR_CONTRACT_ADDRESS:
        to_addr = to_checksum_address(config.ANCHOR_CONTRACT_ADDRESS)
        data = "0x" + SEL_ANCHOR + digest
        gas = 90_000
    else:
        # No contract: a zero-value self-send carrying the digest as calldata.
        # Permanently readable, no deployment required.
        to_addr = sender
        data = "0x" + digest
        gas = 40_000

    return {
        "nonce": nonce, "to": to_addr, "value": 0, "gas": gas,
        "gasPrice": gas_price, "data": data,
        "chainId": config.ANCHOR_CHAIN_ID,
    }


def _cache_path(digest: str):
    return CACHE_DIR / f"{digest.lower()}.json"


def read_cached(digest: str) -> dict[str, Any] | None:
    p = _cache_path(digest)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _write_cache(digest: str, receipt: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(digest).write_text(json.dumps(receipt, indent=2),
                                   encoding="utf-8")


def _rpc(method: str, params: list) -> Any:
    r = httpx.post(
        config.ANCHOR_RPC_URL,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=config.ANCHOR_TIMEOUT_SECONDS,
    )
    r.raise_for_status()
    body = r.json()
    if "error" in body:
        raise RuntimeError(body["error"].get("message", "RPC error"))
    return body.get("result")


def status() -> dict[str, Any]:
    """What anchoring is able to do right now, without touching the network."""
    return {
        "configured": config.ANCHOR_CONFIGURED,
        "mode": ("contract" if config.ANCHOR_CONTRACT_ADDRESS
                 else "calldata" if config.ANCHOR_CONFIGURED else "unavailable"),
        "chain_id": config.ANCHOR_CHAIN_ID,
        "contract": config.ANCHOR_CONTRACT_ADDRESS or None,
        "network": EXPLORERS.get(config.ANCHOR_CHAIN_ID, "unknown"),
    }


def anchor_digest(digest: str) -> dict[str, Any]:
    """Publish `digest` on-chain. Returns a receipt, cached to disk.

    A digest already anchored is returned from cache rather than re-sent: the
    earliest anchor is the evidentially meaningful one, and the contract
    reverts on a duplicate anyway.
    """
    digest = digest.lower().removeprefix("0x")
    if len(digest) != 64:
        raise ValueError("A SHA-256 digest must be 64 hex characters.")

    cached = read_cached(digest)
    if cached and cached.get("anchored"):
        return cached

    if not config.ANCHOR_CONFIGURED:
        return {
            "digest": digest, "anchored": False,
            "reason": "Anchoring is not configured on this instance "
                      "(ANCHOR_RPC_URL and ANCHOR_PRIVATE_KEY are unset). "
                      "The dossier's SHA-256 is still issued as a detached "
                      "record in the chain-of-custody log.",
            **status(),
        }

    try:
        # The key is used only to sign. It is never logged, returned, or
        # written to the receipt.
        account = Account.from_key(config.ANCHOR_PRIVATE_KEY)
        sender = account.address

        nonce = int(_rpc("eth_getTransactionCount", [sender, "pending"]), 16)
        gas_price = int(_rpc("eth_gasPrice", []), 16)

        tx = build_transaction(sender, digest, nonce, gas_price)
        signed = account.sign_transaction(tx)
        tx_hash = _rpc("eth_sendRawTransaction",
                       ["0x" + signed.raw_transaction.hex()])

        receipt = _await_receipt(tx_hash)
        block_number = int(receipt["blockNumber"], 16) if receipt else None
        block = (_rpc("eth_getBlockByNumber", [receipt["blockNumber"], False])
                 if receipt else None)
        block_time = int(block["timestamp"], 16) if block else None

        out = {
            "digest": digest,
            "anchored": True,
            "tx_hash": tx_hash,
            "block_number": block_number,
            "block_time": block_time,
            "anchored_by": sender,
            "explorer_url": explorer_tx(tx_hash, config.ANCHOR_CHAIN_ID),
            "anchored_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            **status(),
        }
        _write_cache(digest, out)
        return out

    except Exception as exc:  # noqa: BLE001 - degrade, never break a report
        log.warning("Anchoring failed (%s)", exc.__class__.__name__)
        return {
            "digest": digest, "anchored": False,
            "reason": f"Anchoring did not complete: {exc.__class__.__name__}. "
                      "The dossier is unaffected - its SHA-256 remains "
                      "recorded in the chain-of-custody log.",
            **status(),
        }


def _await_receipt(tx_hash: str, attempts: int = 20) -> dict | None:
    """Poll for inclusion. A pending anchor is not yet evidence of anything."""
    for _ in range(attempts):
        receipt = _rpc("eth_getTransactionReceipt", [tx_hash])
        if receipt and receipt.get("blockNumber"):
            return receipt
        time.sleep(3)
    return None


def verify_digest(digest: str) -> dict[str, Any]:
    """Read the anchor back from the chain.

    Read-only, so it needs no key and can be run by anyone auditing the
    dossier - which is the point. Falls back to the cached receipt when the
    network is unreachable, and says which it used.
    """
    digest = digest.lower().removeprefix("0x")
    cached = read_cached(digest)

    if not config.ANCHOR_RPC_URL or not config.ANCHOR_CONTRACT_ADDRESS:
        if cached:
            return {**cached, "source": "cached receipt",
                    "note": "On-chain read unavailable; showing the receipt "
                            "recorded when the anchor was made."}
        return {"digest": digest, "anchored": False, "source": "none",
                "reason": "No anchor on record for this digest."}

    try:
        result = _rpc("eth_call", [{
            "to": to_checksum_address(config.ANCHOR_CONTRACT_ADDRESS),
            "data": "0x" + SEL_ANCHOR_OF + digest,
        }, "latest"])
        raw = (result or "0x").removeprefix("0x")
        if len(raw) < 192:
            raise RuntimeError("unexpected return data")

        block_time = int(raw[0:64], 16)
        block_number = int(raw[64:128], 16)
        anchored_by = "0x" + raw[128:192][-40:]

        return {
            "digest": digest,
            "anchored": block_number != 0,
            "block_number": block_number or None,
            "block_time": block_time or None,
            "anchored_by": to_checksum_address(anchored_by)
            if block_number else None,
            "source": "on-chain read",
            "explorer_url": (cached or {}).get("explorer_url"),
            **status(),
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("Anchor verification failed (%s)", exc.__class__.__name__)
        if cached:
            return {**cached, "source": "cached receipt",
                    "note": "Chain unreachable; showing the recorded receipt."}
        return {"digest": digest, "anchored": False, "source": "unavailable",
                "reason": f"Could not reach the chain: {exc.__class__.__name__}"}
