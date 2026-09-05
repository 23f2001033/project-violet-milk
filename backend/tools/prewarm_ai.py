"""
Pre-warm the AI cache before the demo.

Run this once while you still have working internet. Every AI response used by
the demonstration is fetched live and written to `data/ai_cache/`, after which
the network is optional: if Groq is unreachable on stage, `llm_client` replays
the cached answer and nothing visibly changes.

    python backend/tools/prewarm_ai.py

Rule of thumb for demo day: run it the morning of, and again on the venue wifi
if you get the chance.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app import config                                    # noqa: E402
from backend.app.db import cursor                                 # noqa: E402
from backend.app.engines.pipeline import get_analysis             # noqa: E402
from backend.app.main import app  # noqa: F401,E402  (seeds the demo case)
from backend.app.services import column_mapper, narrative         # noqa: E402

# Column layouts the demo might be handed. Add any bank format you plan to
# drop in live so its mapping is cached too.
BANK_HEADERS = [
    ["Sl No", "Value Dt", "Chq/Ref Number", "Narration", "Withdrawal Amt.",
     "Deposit Amt.", "Closing Balance", "Bank Name"],
    ["Txn Date", "Description", "Ref No./Cheque No.", "Debit", "Credit",
     "Balance"],
    ["Transaction Date", "Transaction Remarks", "Withdrawal Amount (INR )",
     "Deposit Amount (INR )", "S No."],
    ["date", "utr", "amount", "bank", "remarks"],
]


def main() -> int:
    if not config.LLM_CONFIGURED:
        print("LLM is not configured - set LLM_BASE_URL, LLM_API_KEY and "
              "LLM_MODEL in .env first.")
        return 1

    print(f"provider : {config.LLM_BASE_URL}")
    print(f"model    : {config.LLM_MODEL}\n")

    failures = 0

    with cursor() as conn:
        cases = [dict(r) for r in conn.execute(
            "SELECT * FROM cases WHERE seed_wallet IS NOT NULL").fetchall()]

    for case in cases:
        analysis = get_analysis(case["case_id"], case["seed_wallet"])
        _, prov = narrative.build(analysis, case)
        ok = prov.startswith("ai")
        failures += 0 if ok else 1
        print(f"  narrative  {case['case_id']:<22} {prov}")

    for headers in BANK_HEADERS:
        _, prov = column_mapper.map_columns(headers)
        print(f"  mapper     {headers[1][:22]:<22} {prov}")

    cached = len(list((config.DATA_DIR / 'ai_cache').glob('*.json')))
    print(f"\ncache entries: {cached}")

    if failures:
        print(f"\n{failures} narrative(s) fell back to the template. The demo "
              "still works, but check the key and rerun.")
        return 1

    print("\nCache warm. The demo will now survive a dead network.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
