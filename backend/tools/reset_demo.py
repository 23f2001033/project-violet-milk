"""
Reset the demonstration to a clean state.

    .venv\\Scripts\\python.exe backend\\tools\\reset_demo.py

WHY THIS EXISTS
---------------
Rehearsing is not free. Every trace, dossier and STR draft appends to the
hash-chained custody log and drops a PDF on disk, and after a day of practice
CP-CYBER-2026-001 was carrying 434 custody entries and 245 generated files.
The dossier had grown to twenty-one pages, most of it a custody appendix full
of rehearsal runs.

That is not a bug - the log is append-only by design and it is doing exactly
what it should. But it is the wrong thing to put in front of a judge, who
should see the trail of an investigation rather than the trail of a practice
session.

Run this the morning of the demonstration. The database is recreated and
re-seeded on the next start: four officers, four cases, six custody entries.

WHAT IT DOES NOT TOUCH
----------------------
.env, the live chain cache, the AI cache, or the anchor receipts. Those take
real time and network to rebuild and there is no reason to lose them.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app import config  # noqa: E402


def main() -> int:
    removed = []

    if config.DB_PATH.exists():
        size = config.DB_PATH.stat().st_size
        config.DB_PATH.unlink()
        removed.append(f"{config.DB_PATH.name} ({size:,} bytes)")

    reports = config.REPORTS_DIR
    if reports.is_dir():
        pdfs = list(reports.glob("*.pdf"))
        for f in pdfs:
            f.unlink()
        if pdfs:
            removed.append(f"{len(pdfs)} generated PDFs")

    if not removed:
        print("Already clean - nothing to remove.")
    else:
        for line in removed:
            print(f"  removed  {line}")

    print()
    print("Kept: .env, live_cache, ai_cache, anchor receipts.")
    print("Start the server and it re-seeds four officers, four cases,")
    print("and six custody entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
