# Project Violet Milk

Crypto flow tracking and analytics for Indian cyber-crime investigation.
Built for the **Chandigarh Police Hackathon, 8 September 2026**.

> **⚠ DEMONSTRATION / SYNTHETIC DATA MODE.**
> Output provides analytical leads for investigative assistance. It does not
> constitute a legal finding of guilt and does not identify any person without
> independent verification under Section 94 BNSS 2023. All demo identities,
> accounts, UPI handles and addresses are synthetic.

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
| P6 | Live mainnet mode | ⬜ next |
| P7 | Harden, correct the deck, rehearse | ⬜ |

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
python -m uvicorn backend.app.main:app --reload --port 8000
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

**The frontend runs with the backend switched off.** `src/api.js` has
`USE_MOCKS = true`, so every organ renders from the generated fixtures. Flip it
to `false` at Phase 4 integration.

### 3. Tests

```powershell
.venv\Scripts\python.exe -m pytest backend\tests -q
```

---

## Architecture in one paragraph

A **DataSource** interface has two implementations — `SyntheticSource` (bundled
CSV) and `EtherscanSource` (live mainnet). The graph, risk, dilution, timeline
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

---

## Regenerating fixtures

After editing either demo CSV:

```powershell
.venv\Scripts\python.exe backend\tools\generate_mocks.py
.venv\Scripts\python.exe -m pytest backend\tests -q
```

This writes identical JSON to `backend/app/data/mocks/` and
`frontend/src/mocks/`, so the two halves cannot drift.
