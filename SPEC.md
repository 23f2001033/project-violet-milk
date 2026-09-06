# Project Violet Milk — Build Specification

**Full illustrated spec:** <https://claude.ai/code/artifact/92a053ee-0142-4880-a013-cf1614ad6a5a>

This file is the in-repo quick reference for the frozen parts. When this file
and the artifact disagree, **this file wins** — it sits next to the code.

---

## 1. Frozen decisions

| Layer | Choice | Not |
|---|---|---|
| API | FastAPI + Uvicorn | Flask |
| DB | SQLite (stdlib) | PostgreSQL |
| Graph | NetworkX | Neo4j |
| Scoring | Deterministic rules | Isolation Forest / DBSCAN / XGBoost |
| Frontend | React 18 + Vite (JS) | Next.js, TypeScript |
| Graph render | Cytoscape.js | D3 |
| PDF | ReportLab | WeasyPrint |
| LLM | OpenAI-compatible adapter | any vendor SDK |
| Chain data | Etherscan V2 | Bitquery |

**Why no ML:** Section 63 BSA 2023 requires explaining how electronic evidence
was produced. Arithmetic can be explained to a court; a neural network cannot be
cross-examined. On self-generated synthetic data, ML would also merely
rediscover what we planted — circular, and indefensible under questioning.

---

## 2. Risk rules (SPEC §05)

| ID | Indicator | Points | Trigger |
|---|---|---|---|
| R1 | Proximity to seed | +20 | within 1 hop of the case seed |
| R2 | Rapid dispersal | +15 | outbound < 4 min after receipt |
| R3 | Mixer interaction | +15 | counterparty in curated mixer list |
| R4 | Cross-chain bridge | +15 | bridge reached within 2 hops |
| R5 | Fan-out | +10 | **more than** 5 distinct downstream addresses |
| R6 | Structuring | +10 | 3+ transfers just below a round threshold |
| R7 | Time correlation | +15 | on-chain receipt within 15 min of bank debit |

Maximum = 100, clamped to `[0, 100]`.

**Bands:** `0–24 LOW` · `25–49 MEDIUM` · `50–74 HIGH` · `75–100 CRITICAL`

> **Hard rule:** every indicator must carry a concrete `evidence` string — a tx
> hash, a count, a time delta. **An indicator with no evidence must never be
> emitted.** "Suspicious pattern detected" with nothing behind it is the exact
> failure mode that gets forensic software thrown out of court.

---

## 3. Dilution — TWO models, never confused

| Mode | When | What the number means |
|---|---|---|
| **haircut** | curated case evidence | a true proportion — prior balances are known |
| **propagation** | live chain data | **REACH, not proportion** — a public explorer cannot supply the historical balance at the moment funds arrived, so there is no denominator |

Live mode previously reported `0.0` for every node: with no victim node the
taint had no origin, so the headline feature silently did nothing on real
data. The seed address is now the origin in live mode, and the result carries
an explicit caveat. **Never present a propagation figure as a dilution
percentage.**

### Proportional haircut (curated mode)

```
illicit_ratio_new = (incoming_amount × illicit_ratio_source)
                    ─────────────────────────────────────────
                       (prior_balance + incoming_amount)
```

- Seed initialised at `1.0`
- Propagate breadth-first in **strict timestamp order**, never graph order
- Reporting threshold: `illicit_ratio >= 0.30`

**Worked example (on stage):** wallet at 60% sends 2,000 USDT into a pool
holding 8,000 clean USDT → `1200 / 10000` = **12%**, below threshold, **not
flagged**.

**Known limitation — say it before a judge does:** the haircut model can be
gamed by padding a wallet with clean funds. Recognised alternatives are FIFO,
LIFO and poison/taint; poison over-flags catastrophically. Naming these
tradeoffs unprompted demonstrates we *chose* a model rather than found one.

---

## 4. Locked demo numbers

Enforced by `backend/tests/test_dataset_integrity.py`. **Phase 2 engines must
reproduce these exactly.**

| Fact | Value |
|---|---|
| Case | `CP-CYBER-2026-001` |
| NCRP ref | `1930-NCRP-2026-98124` |
| Victim loss | ₹4,70,000 |
| **Locked FX rate** | **₹90.38 / USDT** |
| Seed wallet | `0xa7f39c1d8e4b2a5f7c3d9e0a1b8c6d4e5f2a67e9` |
| Graph size | 14 nodes, 17 edges |
| Seed risk | **65 / HIGH** — R1+R2+R3+R4 |
| Seed fan-out | exactly **5** (so R5 does *not* fire, holding the score at 65) |
| Dilution rescue | **60% → 12%**, NOT flagged |
| Inferred edges | exactly **1** (E02, UPI→exchange) |

Every INR↔USDT figure in the dataset, the PDF and the deck derives from the
locked rate. A judge who divides two numbers and finds inconsistency will trust
nothing else in the demo.

---

## 5. API contract (SPEC §08)

Base path `/api`. All JSON. Errors are `{"detail": "..."}`.

| Method | Path | Owner |
|---|---|---|
| GET | `/api/health` | BE3 |
| GET POST | `/api/cases` | BE3 |
| GET PUT | `/api/cases/{id}` | BE3 |
| GET POST | `/api/cases/{id}/evidence` | BE3 |
| POST | `/api/cases/{id}/trace` | BE1 |
| GET | `/api/cases/{id}/graph` | BE1 |
| GET | `/api/cases/{id}/timeline` | BE2 |
| GET | `/api/cases/{id}/nodes/{nid}/risk` | BE2 |
| POST | `/api/cases/{id}/dilution` | BE2 |
| GET | `/api/cases/{id}/audit` | BE3 |
| POST | `/api/cases/{id}/report` | BE3 |
| GET | `/api/labels/{address}` | BE1 |

**The contract is authoritative.** During Phase 4 integration, any shape
mismatch is fixed in the **backend**, never by editing the contract or `api.js`.

Live shapes: <http://127.0.0.1:8000/docs>

---

## 6. Traversal bounds — non-negotiable

A real scam wallet at depth 5 touches millions of addresses. Unbounded
traversal freezes the browser and gets the API key rate-limited mid-demo.

```
max_depth          = 3
max_edges_per_node = 20
min_amount         = configurable floor
time_window_hours  = 72
```

---

## 7. The one detail that decides whether live mode works

Indian crypto-fraud proceeds move as **USDT**, not native ETH.

`EtherscanSource.get_transactions()` **must call both** `account/txlist` **and**
`account/tokentx` and merge the results. An implementation that queries only
`txlist` returns almost nothing on a real scam wallet, and live mode will look
broken on stage.

---

## 8. Confirmed vs inferred

`evidence_type` is the most important field in the system.

| Value | Renders | Meaning |
|---|---|---|
| `confirmed_onchain` | solid edge | proven on the blockchain |
| `confirmed_bank` | solid edge | proven in bank records |
| `inferred_correlation` | **dashed edge** | a **hypothesis**, e.g. a UPI debit and an exchange deposit 13 s apart |

An inferred edge must never render identically to a confirmed transfer, and the
dossier must list the two categories separately. This is what makes our
intellectual honesty visible to a judge.

---

## 8b. Chain of custody is hash-chained

Each audit entry commits to its predecessor:

```
entry_hash = SHA256(prev_hash | audit_id | timestamp | user | action
                    | target | target_hash | canonical(details))
```

`GET /api/cases/{id}/audit/verify` re-walks the chain and names the first
broken link. Ordering uses an explicit `seq` column — not `rowid` (not stable
across a dump/restore) and not `timestamp` (the seeded case is dated ahead of
live actions).

**Say it precisely:** this makes tampering *detectable*, not *impossible*.
Only an append-only store or external notarisation prevents it.

---

## 8c. Blockchain evidence anchoring

The SHA-256 of each ingested file is published to a public chain
(`contracts/EvidenceAnchor.sol`, or as transaction calldata when no contract
is deployed). Receipts are cached, so the dossier can cite a real transaction
offline.

**Say exactly this, and no more:**

| Proves | Does NOT prove |
|---|---|
| the digest existed at or before that block | who created the document — anyone may anchor any digest |
| the record cannot afterwards be revised | that the document is tamper-**proof** — only tamper-**evident** |
| a substituted document no longer matches | a precise time — `block.timestamp` is proposer-set and drifts |

> ⚠️ Do **not** claim anchoring "meets the tamper-proof requirement of Section
> 63(4) BSA 2023". Nobody on this team has verified what that sub-section
> requires. State what the anchor does; leave the statutory mapping to counsel.

The dossier prints anchors for **evidence** digests (known before generation).
The dossier's **own** digest is anchored after generation and returned by the
API — it cannot be printed inside the document it describes, for the same
reason its hash cannot be.

`ANCHOR_PRIVATE_KEY` signs and nothing else: never logged, never returned,
never written to a receipt. Use a testnet key funded from a faucet.

---

## 9. What we must never claim

From the constraints in `project.md`, still binding:

- ❌ identifying a real person from a wallet without authorised off-chain evidence
- ❌ automatic arrest, account freezing, or determination of guilt
- ❌ direct filing with FIU-IND
- ❌ 100% tracing coverage
- ❌ that Chainalysis / TRM cannot do multi-hop tracing — **they can; it is their core product**

What we *do* claim: we produce **investigative leads and the paperwork**. Naming
an owner requires a Section 94 BNSS 2023 order to the exchange for KYC records.
Our output is the annexure that justifies that order.

---

## 10. Phase status

| Phase | Scope | State |
|---|---|---|
| P0 | Foundations | ✅ |
| P1 | Contract freeze, data model, dataset, mocks | ✅ |
| P2 | Backend engines | ✅ |
| P3 | Frontend organs | ✅ |
| P4 | Integration | ✅ |
| P5 | Sec 63 BSA dossier + AI layer | ✅ |
| P6 | Live mainnet mode | ✅ |
| P7 | Single-port serving, Flag Agent + STR in UI | ✅ |
| — | Correct slides 12 & 13, rehearse | ⬜ remaining |

---

## 10b. What the deck claims vs what exists

| Slide | Claim | Status |
|---|---|---|
| 7 | Track / Percentage / Map Agent | ✅ built |
| 7, 8 | Isolation Forest + DBSCAN | ✅ built — secondary lead signal, never a score |
| 7, 8 | scikit-learn in the stack | ✅ true now |
| 7, 11 | FIU-IND STR generator | ✅ built as a **draft** |
| 8 | Etherscan API, wallet labels DB | ✅ built |
| 8 | Backend: Flask | ❌ FastAPI — fix the slide |
| 8 | Neo4j | ❌ NetworkX — deliberate |
| 8 | Bitquery, Blockchain.com | ❌ not wired (needs a key / is Bitcoin) |
| 8 | XGBoost | ❌ **supervised — no labelled fraud set exists** |
| 11 | "FILE STR WITH FIU-IND" | ❌ **impossible** — FINnet has no public API; filing needs registered-entity status |
| 12 | Chainalysis/TRM lack multi-hop tracing | ❌ **false** — it is their core product |
| 13 | "OTC Tracked 100%" | ❌ **impossible** — OTC settles off-chain |
| 13 | "22/year → 100+", "Weeks → Hours" | ❌ no baseline, no deployment, not measured |

A test asserts no STR-filing endpoint can ever exist in this codebase.

---

## 11. Open items

### Known gaps, ranked (from the adversarial review)

| Gap | Status |
|---|---|
| Dilution dead on live data | ✅ fixed — propagation mode |
| Custody log editable without trace | ✅ fixed — hash-chained |
| White screen on a render error | ✅ fixed — ErrorBoundary |
| Uploaded evidence never reaches the trace | ✅ fixed — parsed and merged; `stats.ingested_edges` reports how many |
| **No authentication** — `uploaded_by` is client-supplied | ⚠️ open |
| **Ethereum only** — most Indian USDT fraud is on Tron | ⚠️ open, architecturally ready |
| Rule weights are uncalibrated | ⚠️ by design — that is what a pilot measures |
| Bank clock vs block clock | ⚠️ say "same minute", not "+13 seconds" |
| AI narrative sends case data to Groq | ⚠️ contradicts the data-sovereignty claim |

---

| # | Question | Blocks |
|---|---|---|
| 1 | **LLM provider** — Groq, `openai/gpt-oss-120b`. Key verified against the live `/models` endpoint. | ✅ resolved |
| 2 | **Confirm ₹90.38/USDT** as the locked rate. | ✅ applied |
| 3 | **Live demo addresses** — 3 pre-tested and cached: Tornado Cash 0.1 ETH pool, Tornado Cash Router (both OFAC-designated) and a publicly-labelled Binance hot wallet. Confirm you are happy to use these. | ✅ proposed |
| 4 | **Whose laptop presents,** and has it been tested on an external projector? | P7 |
| 5 | **Has a law student verified** the exact Section 63 BSA / Section 94 BNSS wording? Do not quote statute you have not checked. | P5 |
