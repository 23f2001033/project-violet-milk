"""
Tron / TRC-20 support.

Runs OFFLINE against fixture payloads shaped exactly like TronGrid's.

The two guarantees that matter most here are unit correctness (Tron differs
from Ethereum in four silent ways) and token verification - on Tron a token
called "USDT" is not necessarily USDT.
"""

from backend.app.models import Asset, Chain, NodeType
from backend.app.engines.pipeline import make_source
from backend.app.sources.tron import (
    VERIFIED_TOKENS, TronSource, is_tron_address,
)

CASE = "TRON-TEST"
GENUINE_USDT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
BINANCE_TRON = "TMuA6YqfCeX8EhbfYEg5y7S4DqzSJireY9"
SOME_ADDR = "TJQQLsfYvwK1gJyET4C7hvPdJ2YyNcAUbL"


def _trc20(value, contract, symbol="USDT", decimals=6, ts=1772649612000):
    return [{
        "transaction_id": "a" * 64, "block_timestamp": ts,
        "from": BINANCE_TRON, "to": SOME_ADDR, "type": "Transfer",
        "value": str(value),
        "token_info": {"symbol": symbol, "address": contract,
                       "decimals": decimals, "name": symbol},
    }]


# ------------------------------------------------------------- addressing

def test_tron_and_ethereum_addresses_are_distinguishable():
    assert is_tron_address(BINANCE_TRON) is True
    assert is_tron_address(GENUINE_USDT) is True
    assert is_tron_address("0xa7f39c1d8e4b2a5f7c3d9e0a1b8c6d4e5f2a67e9") is False
    assert is_tron_address("") is False
    assert is_tron_address("Tshort") is False


def test_the_chain_is_chosen_from_the_address():
    """An investigator pastes an address; they should not have to declare
    which network it belongs to."""
    assert make_source("c", "live", BINANCE_TRON).source_name() == "TronSource"
    assert make_source(
        "c", "live", "0xa7f39c1d8e4b2a5f7c3d9e0a1b8c6d4e5f2a67e9"
    ).source_name().startswith("EtherscanSource")
    assert make_source("c", "synthetic", "").source_name() == "SyntheticSource"


# --------------------------------------------------- token verification

def test_genuine_usdt_is_recognised_by_contract():
    edges = TronSource(CASE)._to_edges(_trc20(5_200_000_000, GENUINE_USDT), [])
    assert len(edges) == 1
    assert edges[0].asset == Asset.USDT
    assert edges[0].amount == 5200.0


def test_a_fake_usdt_is_not_reported_as_usdt():
    """THE Tron-specific hazard. Anyone can deploy a contract whose symbol is
    "USDT"; live traffic contains lookalikes such as "USDTT". A scammer can
    mint fake USDT into a victim's wallet to distort any tool that trusts the
    ticker, so verification is by CONTRACT, never by symbol."""
    fake = "TGXjZQCTdH6ioWL3acappQEzo6sEPhCsGy"     # real lookalike contract
    edges = TronSource(CASE)._to_edges(
        _trc20(7_529_940_740_670_350_000, fake, symbol="USDT"), [])
    assert len(edges) == 1
    assert edges[0].asset == Asset.TOKEN, "a fake USDT must not read as USDT"
    assert edges[0].asset != Asset.USDT


def test_the_verified_registry_is_keyed_by_contract():
    assert GENUINE_USDT in VERIFIED_TOKENS
    assert VERIFIED_TOKENS[GENUINE_USDT] == "USDT"
    for addr in VERIFIED_TOKENS:
        assert is_tron_address(addr), "registry keys must be Tron contracts"


# ----------------------------------------------------------- unit safety

def test_milliseconds_are_not_read_as_seconds():
    """Tron reports milliseconds. Reading them as seconds dates every
    transaction to 1970 and destroys the timeline deltas."""
    edges = TronSource(CASE)._to_edges(
        _trc20(1_000_000, GENUINE_USDT, ts=1772649612000), [])
    assert edges[0].timestamp.startswith("2026")


def test_token_decimals_are_honoured():
    six = TronSource(CASE)._to_edges(_trc20(1_000_000, GENUINE_USDT), [])
    assert six[0].amount == 1.0
    eighteen = TronSource(CASE)._to_edges(
        _trc20(10 ** 18, GENUINE_USDT, decimals=18), [])
    assert eighteen[0].amount == 1.0


def test_native_trx_is_converted_from_sun():
    """1 TRX = 1,000,000 sun, and the transfer fields are nested inside
    raw_data.contract[0].parameter.value."""
    native = [{
        "txID": "b" * 64,
        "raw_data": {
            "timestamp": 1772649612000,
            "contract": [{
                "type": "TransferContract",
                "parameter": {"value": {
                    "owner_address": BINANCE_TRON, "to_address": SOME_ADDR,
                    "amount": 2_500_000,
                }},
            }],
        },
    }]
    edges = TronSource(CASE)._to_edges([], native)
    assert len(edges) == 1
    assert edges[0].amount == 2.5
    assert edges[0].asset == Asset.TRX


def test_non_transfer_contracts_are_ignored():
    native = [{"txID": "c" * 64, "raw_data": {
        "timestamp": 1772649612000,
        "contract": [{"type": "TriggerSmartContract", "parameter": {"value": {}}}],
    }}]
    assert TronSource(CASE)._to_edges([], native) == []


def test_zero_value_transfers_are_dropped():
    assert TronSource(CASE)._to_edges(_trc20(0, GENUINE_USDT), []) == []


def test_malformed_rows_are_skipped_not_fatal():
    edges = TronSource(CASE)._to_edges(
        [{"nonsense": True}] + _trc20(1_000_000, GENUINE_USDT), [])
    assert len(edges) == 1


# -------------------------------------------------------------- labelling

def test_tron_labels_are_case_sensitive():
    """Unlike Ethereum, Base58 addresses must NOT be lowercased - doing so
    makes every curated Tron label silently miss."""
    src = TronSource(CASE)
    assert src.get_label(GENUINE_USDT) is not None
    assert src.get_label(GENUINE_USDT.lower()) is None


def test_nodes_are_tagged_as_tron():
    node = TronSource(CASE)._node_for(SOME_ADDR)
    assert node.chain == Chain.TRON
    assert node.node_type == NodeType.UNKNOWN
    assert node.label is None


def test_source_identifies_itself_as_live():
    assert TronSource(CASE).is_live() is True
