"""
Check the anchoring configuration, and anchor the demo digests ahead of time.

    python backend/tools/anchor_setup.py            # report status only
    python backend/tools/anchor_setup.py --anchor   # actually send transactions

WHY RUN THIS BEFORE THE DEMO
Anchoring needs the network. Anchor the evidence digests the morning of, and
the receipts are cached to disk - the dossier can then cite a real transaction
with the venue wifi unplugged.

GETTING SET UP (about 20 minutes, all free)
  1. Create a throwaway wallet. Never reuse a personal one; this account signs
     one tiny transaction per document and should hold nothing of value.
  2. Fund it from a Sepolia faucet.
  3. Put an RPC URL and that private key in .env.
  4. Deploy contracts/EvidenceAnchor.sol via Remix (remix.ethereum.org - no
     toolchain to install), paste the address into ANCHOR_CONTRACT_ADDRESS.
     Skipping step 4 is fine: without a contract the digest is anchored as
     transaction calldata instead, which is still permanent.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app import config                       # noqa: E402
from backend.app.db import cursor                    # noqa: E402
from backend.app.main import app  # noqa: F401,E402  (seeds the demo case)
from backend.app.services import anchor              # noqa: E402


def main() -> int:
    st = anchor.status()
    print(f"configured : {st['configured']}")
    print(f"mode       : {st['mode']}")
    print(f"chain      : {st['chain_id']}  ({st['network']})")
    print(f"contract   : {st['contract'] or 'none - will anchor as calldata'}")
    print()

    if not st["configured"]:
        print("Anchoring is OFF. The system runs normally and reports every")
        print("dossier as NOT ANCHORED. To enable it, see the header of this")
        print("file - it takes about 20 minutes and costs nothing.")
        return 0

    with cursor() as conn:
        rows = conn.execute(
            "SELECT filename, sha256_server FROM evidence").fetchall()

    if not rows:
        print("No evidence on record to anchor.")
        return 0

    send = "--anchor" in sys.argv
    print(f"{len(rows)} evidence digest(s) on record\n")

    failures = 0
    for r in rows:
        digest = r["sha256_server"]
        cached = anchor.read_cached(digest)
        if cached and cached.get("anchored"):
            print(f"  [CACHED] {r['filename']}  block "
                  f"{cached.get('block_number')}")
            continue
        if not send:
            print(f"  [ TODO ] {r['filename']}  {digest[:24]}…")
            continue

        out = anchor.anchor_digest(digest)
        if out.get("anchored"):
            print(f"  [ SENT ] {r['filename']}  block {out['block_number']}")
            print(f"           {out['explorer_url']}")
        else:
            failures += 1
            print(f"  [ FAIL ] {r['filename']}  {out.get('reason', '')[:60]}")

    if not send:
        print("\nDry run. Re-run with --anchor to send the transactions.")
    elif failures:
        print(f"\n{failures} digest(s) did not anchor. The dossier still "
              "generates and reports them as not anchored.")
    else:
        print("\nAll digests anchored and cached. The demo can now cite a real "
              "transaction with the network unplugged.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
