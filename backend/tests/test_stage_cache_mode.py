"""
LIVE_CACHE_FIRST - the stage mode.

Venue wifi that is slow but not dead is the worst case for a live demo: the
circuit breaker never trips, so every call pays full latency. This flag replays
pre-tested addresses from disk instead.

Two things must hold, and both are tested here:

  * it is OFF unless explicitly enabled, so an investigator never gets stale
    chain data by accident;
  * when it is on, the source says so, so a replay is never presented to a
    court - or a judge at a hackathon - as a live pull.
"""

import json

import pytest

from backend.app import config
from backend.app.sources.etherscan import EtherscanSource

ADDR = "0x1111111111111111111111111111111111111111"


@pytest.fixture
def cached_address(tmp_path, monkeypatch):
    """A cache directory holding exactly one pre-tested address."""
    import backend.app.sources.etherscan as es

    monkeypatch.setattr(es, "CACHE_DIR", tmp_path)
    payload = [{
        "hash": "0x" + "ab" * 32, "from": ADDR,
        "to": "0x2222222222222222222222222222222222222222",
        "value": "1000000000000000000", "timeStamp": "1757000000",
        "blockNumber": "19204512", "tokenSymbol": "", "tokenDecimal": "18",
    }]
    (tmp_path / f"1_txlist_{ADDR}.json").write_text(json.dumps(payload),
                                                    encoding="utf-8")
    return tmp_path


def test_off_by_default():
    """The default must be live. A demo convenience that silently became the
    production path would hand an investigator stale chain data."""
    assert config.LIVE_CACHE_FIRST is False


def test_serves_from_disk_without_touching_the_network(cached_address,
                                                       monkeypatch):
    import backend.app.sources.etherscan as es

    monkeypatch.setattr(config, "LIVE_CACHE_FIRST", True)
    monkeypatch.setattr(config, "ETHERSCAN_CONFIGURED", True)

    def explode(*a, **k):
        raise AssertionError("stage mode must not call the network")

    monkeypatch.setattr(es._client, "get", explode)

    rows = EtherscanSource("TEST")._fetch("txlist", ADDR)
    assert len(rows) == 1
    assert rows[0]["blockNumber"] == "19204512"


def test_a_replay_is_labelled_as_cached(cached_address, monkeypatch):
    """THE honesty guarantee: the UI reads source_name(), so a replayed trace
    must not be able to look like a live one."""
    import backend.app.sources.etherscan as es

    monkeypatch.setattr(config, "LIVE_CACHE_FIRST", True)
    monkeypatch.setattr(config, "ETHERSCAN_CONFIGURED", True)
    monkeypatch.setattr(es._client, "get", lambda *a, **k: 1 / 0)

    src = EtherscanSource("TEST")
    assert "cached" not in src.source_name()
    src._fetch("txlist", ADDR)
    assert src.source_name() == "EtherscanSource (cached)"


def test_an_unknown_address_still_goes_to_the_network(cached_address,
                                                     monkeypatch):
    """Stage mode replays what was pre-tested. It must not turn an address
    nobody has ever traced into a silent empty result."""
    import backend.app.sources.etherscan as es

    monkeypatch.setattr(config, "LIVE_CACHE_FIRST", True)
    monkeypatch.setattr(config, "ETHERSCAN_CONFIGURED", True)

    called = {"n": 0}

    class Resp:
        status_code = 200

        def raise_for_status(self): pass

        def json(self): return {"result": []}

    def counted(*a, **k):
        called["n"] += 1
        return Resp()

    monkeypatch.setattr(es._client, "get", counted)
    monkeypatch.setattr(es, "_circuit_open", lambda: False)

    EtherscanSource("TEST")._fetch("txlist",
                             "0x9999999999999999999999999999999999999999")
    assert called["n"] == 1
