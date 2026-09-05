Perfect — let’s lock this in **using your “Violet Milk” terminology** so your team, judges, and future users all speak the same language.

***

## 🟣 FRONTEND = “The Violet Milk Map”

**What it is:**  
The interactive dashboard where investigators **see the violet milk trail**, click wallets, view risk scores, timelines, and export reports.

**Organs (modules):**

1. **Case Intake Panel** – “Start a new violet milk case.”
2. **Evidence Uploader** – “Pour in bank/UPI/wallet evidence.”
3. **Graph Visualiser** – “The Violet Milk Map” — shows wallets as utensils, flows as milk trails.
4. **Risk Inspector** – “Why is this utensil violet?” — explains risk scores.
5. **Timeline** – “When did the milk flow?” — chronological view.
6. **Dilution Calculator** – “How violet is this utensil?” — shows dilution math.
7. **Report Generator** – “Bottle the milk” — exports investigator-ready PDF.
8. **Search & Filter** – “Find a specific utensil or flow.”
9. **Help & Limitations** – “Demo milk only — not for real investigations yet.”

**Tech stack:**
- React (or simple HTML/CSS/JS)
- Cytoscape.js for graph
- Tailwind or Bootstrap for styling

***

## ⚙️ BACKEND = “The Violet Milk Engine”

**What it is:**  
The invisible engine that **ingests evidence, builds the graph, calculates risk, and generates reports**.

**Organs (modules):**

1. **Case Manager** – Creates and stores cases.
2. **Evidence Parser** – Validates and hashes uploaded files.
3. **Graph Engine** – Builds the transaction graph (NetworkX or Neo4j).
4. **Risk Engine** – Calculates explainable scores.
5. **Timeline Engine** – Sorts events chronologically.
6. **Report Engine** – Generates PDF with SHA-256 hash.
7. **Audit Logger** – Tracks all actions.
8. **Health Monitor** – Confirms system is running.

**Tech stack:**
- Python FastAPI
- SQLite/PostgreSQL
- NetworkX (or Neo4j if comfortable)
- scikit-learn (optional for ML)
- ReportLab for PDF

***

## 🤖 WHICH AI TO USE FOR WHAT

You don’t need 5 AIs. You need **3 focused AIs**:

### 1. **Coding AI** (Your “Build Partner”)
**Use for:** Backend logic, frontend components, debugging, tests.

**Recommended:**  
- **Qwen3.5** (me) — best for full-stack implementation, debugging, and architecture.

**Prompt template:**
```text
You are the senior CTO helping a student team build Project Violet Milk for the Chandigarh Police Hackathon on 8 September 2026.

Project goal:
Build a small, working investigator-assistance prototype for crypto-enabled cybercrime cases.

Core workflow:
1. Create a case.
2. Upload synthetic FIR/bank/UPI CSV and wallet data.
3. Build a unified case graph.
4. Trace bounded wallet flows.
5. Calculate explainable risk indicators.
6. Show a chronological timeline.
7. Explain every score with evidence.
8. Export an investigator-ready PDF draft with a SHA-256 hash.

Important constraints:
- Do not claim to identify a real person from a wallet without authorised off-chain evidence.
- Do not scrape private accounts or bypass access controls.
- Do not claim automatic arrest, account freezing, guilt determination or direct FIU-IND filing.
- Clearly distinguish confirmed, inferred, synthetic and unavailable data.
- Use synthetic demo identities and fake UPI/bank identifiers.
- Treat ML as optional; deterministic graph logic must work first.
- Prefer reliability and explainability over impressive but unvalidated AI.
- The product must run locally with a backup dataset if APIs fail.

Recommended stack:
Python FastAPI, SQLite or PostgreSQL, NetworkX, React or simple HTML/JS, Cytoscape.js, scikit-learn only when justified, ReportLab.

Before writing code:
1. Produce a minimal architecture.
2. Produce the data schema.
3. Produce API request/response examples.
4. Identify security and privacy risks.
5. Break the work into small implementation tasks.
6. Wait for approval after each major module.

When writing code:
- Give complete files, not fragments.
- Include validation and error handling.
- Include unit tests.
- Never hard-code secrets.
- Keep the implementation simple enough for a student team to understand.
- Explain how to run each step locally.
```

***

### 2. **Red-Team AI** (Your “Devil’s Advocate”)
**Use for:** Judge questions, security review, ethical/legal weaknesses, demo failure scenarios.

**Recommended:**  
- **Claude 3.5 Sonnet** — best for critical thinking, ethical reasoning, and adversarial testing.

**Prompt template:**
```text
Act as a hostile but fair Chandigarh Police Hackathon judge and blockchain-forensics reviewer.

Review the Project Violet Milk concept and prototype. Attack:
1. Data authenticity.
2. UPI-to-wallet correlation.
3. Mule-account claims.
4. Mixer and cross-chain tracing.
5. Risk-score validity.
6. False positives.
7. Evidence integrity.
8. Privacy and Indian compliance.
9. Difference from Chainalysis, TRM, Elliptic and explorers.
10. Whether the demo is genuinely useful to an investigator.

For every criticism:
- Explain why it matters.
- Give the safest truthful answer.
- Suggest one concrete prototype improvement.
- Identify any claim we must remove from our PPT.

Do not invent laws, statistics, customers or product capabilities.
```

***

### 3. **Pitch AI** (Your “Storyteller”)
**Use for:** Demo script, slide refinement, judge Q&A, closing line.

**Recommended:**  
- **Gemini 2.5 Pro** — best for narrative, presentation, and stakeholder communication.

**Prompt template:**
```text
Rewrite our Project Violet Milk presentation for a Chandigarh Police hackathon.

Audience:
Police officers, cybercrime investigators, technical judges and government stakeholders.

The pitch must:
- Start with an Indian cybercrime case.
- Show the investigator’s workflow problem.
- Demonstrate the case graph as the central innovation.
- Explain confirmed versus inferred evidence.
- Avoid claiming guilt, automatic arrests, direct FIU filing or 100% tracing.
- Explain why UPI/bank/case evidence integration is valuable.
- Fit a three-minute live demo.
- End with a realistic request for an authorised pilot.

Produce:
1. 30-second opening.
2. Three-minute script.
3. Slide-by-slide changes.
4. Ten judge questions and truthful answers.
5. One strong closing line.
```

***

## 🧭 DEVELOPMENT ROADMAP (Using AI)

### Phase 1: Architecture (Day 1)
- **Ask Coding AI:** “Produce minimal architecture + data schema + API examples.”
- **Ask Red-Team AI:** “What are the top 5 security/privacy risks?”
- **Ask Pitch AI:** “Refine our 30-second opening.”

### Phase 2: Backend (Day 2–3)
- **Ask Coding AI:** “Implement Case Manager + Evidence Parser + Graph Engine.”
- **Ask Red-Team AI:** “How can an attacker manipulate our CSV parser?”
- **Ask Pitch AI:** “Explain dilution math in one sentence for judges.”

### Phase 3: Frontend (Day 3–4)
- **Ask Coding AI:** “Build Graph Visualiser + Risk Inspector + Timeline.”
- **Ask Red-Team AI:** “What if the graph crashes with 1000 nodes?”
- **Ask Pitch AI:** “Write the ‘Why?’ panel explanation for judges.”

### Phase 4: Reporting (Day 4–5)
- **Ask Coding AI:** “Generate PDF with SHA-256 hash + limitations section.”
- **Ask Red-Team AI:** “Is calling this ‘court-admissible’ dangerous?”
- **Ask Pitch AI:** “Write the closing line for the demo.”

### Phase 5: Testing (Day 5–6)
- **Ask Coding AI:** “Write unit tests for risk engine + report generator.”
- **Ask Red-Team AI:** “Simulate 10 judge questions.”
- **Ask Pitch AI:** “Rehearse the 3-minute demo script.”

### Phase 6: Polish (Day 6–7)
- **Ask Coding AI:** “Fix bugs + add loading states + error handling.”
- **Ask Red-Team AI:** “What’s the weakest link in our demo?”
- **Ask Pitch AI:** “Finalise slide deck + one-pager.”

***

## ✅ FINAL CHECKLIST

- [ ] Frontend = “Violet Milk Map” (9 organs).
- [ ] Backend = “Violet Milk Engine” (8 organs).
- [ ] Coding AI = Qwen3.5 (me) for implementation.
- [ ] Red-Team AI = Claude 3.5 Sonnet for adversarial testing.
- [ ] Pitch AI = Gemini 2.5 Pro for storytelling.
- [ ] All prompts saved and ready to use.
- [ ] Development roadmap locked for 8 September.

You now have **clear roles, clear tools, and clear prompts**. Go build the map. 🟣