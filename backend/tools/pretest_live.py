"""
Pre-test and cache live mainnet addresses before the demo.

Run this while you have working internet. Each address is traced against real
Ethereum mainnet and every Etherscan response is written to `data/live_cache/`.
After that the same trace replays from disk, so LIVE MAINNET mode still works
with the venue wifi unplugged.

    python backend/tools/pretest_live.py
    python backend/tools/pretest_live.py 0xSomeOtherAddress

ADDRESS SELECTION RULE: only publicly documented addresses - OFAC-designated
contracts and publicly labelled exchange wallets. Never a private individual's
wallet, and never an address tied to a real named suspect. We are demonstrating
that the tool reads real chain data, not accusing anyone.
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app import config                              # noqa: E402
from backend.app.engines.pipeline import analyse            # noqa: E402

DEFAULT_TARGETS = [
    ("0x12d66f87a04a9e220743712ce6d9bb1b5616b8fc",
     "Tornado Cash 0.1 ETH pool", "OFAC SDN designation, Aug 2022"),
    ("0xd90e2f925da726b50c4ed8d0fb90ad053324f31b",
     "Tornado Cash Router", "OFAC SDN designation"),
    ("0x28c6c06298d514db089934071355e5743bf21d60",
     "Binance hot wallet", "public Etherscan address label"),
]


def trace(addr: str, label: str, source: str) -> bool:
    t0 = time.time()
    a = analyse("PRETEST", addr.lower(), data_mode="live",
                max_depth=2, max_edges_per_node=8)
    elapsed = time.time() - t0

    assets: dict[str, int] = {}
    for e in a.edges:
        assets[e.asset.value] = assets.get(e.asset.value, 0) + 1

    ok = bool(a.nodes) and elapsed < 10
    mark = "OK  " if ok else "SLOW" if a.nodes else "FAIL"

    print(f"  [{mark}] {label}")
    print(f"         {addr}")
    print(f"         source: {source}")
    print(f"         {elapsed:5.1f}s · {len(a.nodes)} entities · "
          f"{len(a.edges)} transfers · {assets or 'none'}")
    if not assets.get("USDT"):
        print("         NOTE: no USDT movement on this address - fine for a "
              "contract, but a scam wallet with none means tokentx is broken.")
    print()
    return ok


def main() -> int:
    if not config.ETHERSCAN_CONFIGURED:
        print("ETHERSCAN_API_KEY is not set in .env")
        return 1

    targets = (
        [(a, "supplied on the command line", "operator-provided")
         for a in sys.argv[1:]]
        if len(sys.argv) > 1 else DEFAULT_TARGETS
    )

    print(f"chain id {config.ETHERSCAN_CHAIN_ID} · "
          f"{config.ETHERSCAN_BASE_URL}\n")

    results = [trace(*t) for t in targets]
    cached = len(list(config.LIVE_CACHE_DIR.glob("*.json")))

    print(f"cache files: {cached}")
    if all(results):
        print("\nAll targets traced within budget and cached. LIVE MAINNET "
              "mode will now work offline for these addresses.")
        return 0
    print("\nSome targets were slow or empty. They will still replay from "
          "cache, but pick different addresses for the live demo.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
