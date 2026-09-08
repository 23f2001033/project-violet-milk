# Project Violet Milk

Crypto flow tracking and analytics for Indian cyber-crime investigation.
Built for the **Chandigarh Police Hackathon, 8 September 2026**.

> **⚠ NOT AN OFFICIAL POLICE SYSTEM.**
> This is an independent student project built for a hackathon. It is **not
> affiliated with, endorsed by, or deployed by** Chandigarh Police, FIU-IND, or
> any law-enforcement agency. Agency names appear only to describe the intended
> user of a prototype.
>
> **⚠ DEMONSTRATION / SYNTHETIC DATA MODE.**
> Output provides analytical leads for investigative assistance. It does not
> constitute a legal finding of guilt and does not identify any person without
> independent verification under Section 94 BNSS 2023. All demo identities,
> accounts, UPI handles and addresses are synthetic.
>
> **⚠ STATUTORY TEXT IS UNREVIEWED.**
> The Section 63 BSA 2023 certificate and Section 94 BNSS 2023 references in
> the generated documents were drafted by the authors and have **not** been
> checked by a legal practitioner. Do not rely on them.

---

## Licence

MIT &mdash; see [LICENSE](LICENSE). Any police force, agency or individual may
use, modify and deploy this without permission or payment. If institutional
adoption later needs an explicit patent grant, swap in Apache-2.0 from
apache.org; nothing in the codebase depends on the choice.

---

## Status

| Phase | Scope | State |
|-------|-------|-------|
| **P0** | Foundations — repo, tree, env | ✅ done |
| **P1** | Contract freeze, data model, demo dataset, mocks | ✅ done |
| **P2** | Backend engines (graph / risk / dilution / timeline) | ✅ done |
| **P3** | Frontend organs | ✅ done |
| **P4** | Integration | ✅ done |
| P5 | Sec 63 BSA dossier + AI layer | ✅ |
| P6 | Live mainnet mode | ✅ |
| **P7** | Single-port serving, Flag Agent + STR in UI | ✅ done |
| **P8** | Asset ledger — currency by layer and entity | ✅ done |
| — | Legal review of statutory wording, LICENSE, rehearse | ⬜ remaining |

The full specification lives in **`SPEC.md`**. Read it before writing code.

---

## Quick start

> **Windows note:** this machine has **`python`, not `python3`**. Commands using
> `python3` or `pip3` will fail.

### 1. Backend

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
Copy-Item .env.example .env      # then paste your keys into .env
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
```

Interactive API contract → <http://127.0.0.1:8000/docs>

If PowerShell refuses to run the activate script:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

App → <http://localhost:5173>

`src/api.js` runs against the live backend (`USE_MOCKS = false`). Set it back
to `true` to develop any organ with the backend switched off - the fixtures in
`src/mocks/` are generated from the real engines, so they cannot drift.

### 3. Blockchain anchoring (optional)

```powershell
.venv\Scripts\python.exe backend\tools\anchor_setup.py           # status
.venv\Scripts\python.exe backend\tools\anchor_setup.py --anchor  # send
```

Off by default. With it off the system runs normally and reports every dossier
as NOT ANCHORED. Setup takes ~20 minutes and costs nothing — see the header of
`anchor_setup.py`.

### 4. Tests

```powershell
.venv\Scripts\python.exe -m pytest backend\tests -q
```

### 5. Reset before demonstrating

Rehearsing appends to the custody log and leaves PDFs on disk - after a day of
practice the demo case had 434 custody entries and a twenty-one page dossier,
most of it a record of rehearsal. Clear it so a judge sees an investigation
rather than a practice session:

```powershell
.venv\Scripts\python.exe backend	oolseset_demo.py
```

Keeps `.env`, the live chain cache, the AI cache and anchor receipts. The next
start re-seeds four officers, four cases and six custody entries.

### 6. Demo day

Run these in order **while you still have working internet**, then leave the
server up. Every command spells out `.venv\Scripts\python.exe` on purpose: a
bare `python` picks up whatever interpreter is first on PATH, and a global
Python that happens to have FastAPI but not `eth-account` fails deep inside
`services/anchor.py` rather than at the first import.

```powershell
.venv\Scripts\python.exe backend\tools\prewarm_ai.py
```

```powershell
.venv\Scripts\python.exe backend\tools\pretest_live.py
```

```powershell
cd frontend; npm run build; cd ..
```

```powershell
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000
```

Everything is then served from <http://127.0.0.1:8000> - one process, one port,
no separate frontend server.

`pretest_live.py` is slow the first time and that is expected: it is populating
`data/live_cache/`, and a busy address can take a minute. `[SLOW]` only means
the trace exceeded the 10-second budget on a cold fetch. Run it a second time
and the same addresses replay from disk. **Let it finish** - interrupting it
leaves that address partially cached.

---

## Deploying to Render (free)

The repository carries a `Dockerfile` and a `render.yaml` Blueprint. In the
Render dashboard choose **New -> Blueprint**, point it at this repository, and
Render will build the image and prompt for the secrets.

One image, one port: the SPA is built in the first stage and served by the same
FastAPI process, so there is no separate frontend service to wire up.

Set these when prompted:

| Variable | Value |
|----------|-------|
| `DEMO_OFFICER_PASSWORD` | **Anything except the documented demo password.** The default is published in this README, so a public instance left on it is open to anyone. |
| `ETHERSCAN_API_KEY` | Optional. Without it live mode serves the committed cache. |
| `LLM_API_KEY` | Optional. Without it the narrative uses the deterministic template. |

`AUTH_SECRET` is generated by Render. `LIVE_CACHE_FIRST` is set to `true` in the
Blueprint, so live traces replay from the committed cache rather than letting a
stranger burn your API quota. `ANCHOR_PRIVATE_KEY` is deliberately absent - a
signing key does not belong on a free public host, and anchoring stays local.

**What the free plan costs you.** The instance sleeps after about 15 minutes
idle and takes roughly 50 seconds to wake, so open the link yourself before
sending it to anyone. There is no persistent disk, so `violet.db`, generated
PDFs and anchor receipts reset on every deploy or restart - the demo case
re-seeds itself at import, so the app is always usable, but **the custody log is
not a durable record on this plan.** Attach a paid disk before that matters.

Note that `vercel.json` is a *different* thing: it publishes the frontend alone
with `VITE_USE_MOCKS=true`, which is fixtures, not the working system. Do not
present that URL as a live deployment.

---

## Architecture in one paragraph

A **DataSource** interface has three implementations — `SyntheticSource`
(bundled CSV), `EtherscanSource` (Ethereum) and `TronSource` (TRC-20, the
dominant rail for Indian fraud proceeds). A pasted address routes itself:
`0x…` is Ethereum, `T…` is Tron. The graph, risk, dilution, timeline
and report engines never know which is active, so a judge can hand us a real
address mid-demo and nothing downstream changes. Scoring is **deterministic
rules, never ML**: Section 63 BSA 2023 requires explaining how evidence was
produced, and arithmetic can be explained to a court where a neural network
cannot. AI is confined to the edges — reading messy bank CSV formats and
drafting the officer's narrative — and every AI feature degrades to a template
if the provider is unreachable.

---

## Repository layout

```
backend/
  app/
    models.py          ← SINGLE SOURCE OF TRUTH for every shape
    config.py          ← env loading
    stubs.py           ← Phase-1 fixture loader
    main.py            ← FastAPI entrypoint
    routers/           ← one module per endpoint group
    sources/base.py    ← the DataSource contract
    engines/           ← graph, risk, dilution, timeline, report (Phase 2)
    services/          ← llm_client, hashing, audit (Phase 2/5)
    data/
      demo_case.csv    ← 17 edges — the demo narrative
      demo_nodes.csv   ← 14 nodes + prior balances for dilution
      mocks/           ← generated fixtures (also copied to frontend)
  tools/generate_mocks.py
  tests/
frontend/
  src/
    api.js             ← the ONLY place fetch() is called
    mocks/             ← generated fixtures
    organs/            ← UI organs (Phase 3)
```

---

## File ownership

Five developers, strict ownership, no shared files.

| Dev | Owns |
|-----|------|
| **BE1** | `sources/`, `engines/graph_engine.py`, `routers/graph.py` |
| **BE2** | `engines/risk_engine.py`, `dilution.py`, `timeline.py`, `routers/risk.py`, `routers/timeline.py` |
| **BE3** | `db.py`, `routers/cases.py`, `evidence.py`, `audit.py`, `report.py`, `services/` |
| **FE1** | `CommandCenter`, `CaseIntake`, `EvidenceUploader`, `Timeline` |
| **FE2** | `GraphVisualiser`, `RiskInspector`, `DilutionPanel`, `ReportExport` |

Branch per developer. `models.py` and `api.js` change only by agreement — they
are the contract.

---

## Locked demo numbers

These are enforced by `backend/tests/test_dataset_integrity.py`. **Phase 2
engines must reproduce them exactly.**

| Fact | Value |
|------|-------|
| Case | `CP-CYBER-2026-001` |
| Victim loss | ₹4,70,000 |
| Locked FX rate | **₹90.38 / USDT** |
| Graph size | 14 nodes, 17 edges |
| Seed wallet risk | **65 / HIGH** (R1+R2+R3+R4; R5 deliberately not firing) |
| Dilution rescue | **60% → 12%**, NOT flagged |
| Inferred edges | exactly 1 (the UPI→exchange correlation) |
| Dilution model (curated) | `haircut` — a true proportion |
| Dilution model (live) | `propagation` — **reach, not proportion** |
| Custody chain | hash-chained; `/audit/verify` names any broken link |
| Asset ledger | INR + USDT convert at the locked rate; ETH/TRX/TOKEN report **no rate**, never zero |
| Evidence anchoring | optional; proves existence + time, **not** authorship |

---

## Regenerating fixtures

After editing either demo CSV:

```powershell
.venv\Scripts\python.exe backend\tools\generate_mocks.py
.venv\Scripts\python.exe -m pytest backend\tests -q
```

This writes identical JSON to `backend/app/data/mocks/` and
`frontend/src/mocks/`, so the two halves cannot drift.
