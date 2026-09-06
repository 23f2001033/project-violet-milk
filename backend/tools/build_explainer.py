"""
Build the single-PDF prototype explainer: the speech plus every aspect of the
system, in the same house style the product uses for its own court documents.

    .venv\\Scripts\\python.exe backend\\tools\\build_explainer.py

Written to be handed to a judge, printed, or read on a phone the night before.

NOTE ON CHARACTERS: the standard PDF fonts are WinAnsi. The rupee sign U+20B9
is NOT in that set and renders as a black box, which is why every amount here
reads "INR 4,70,000" - the same reason services/formatting.py exists.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from reportlab.lib.pagesizes import A4                        # noqa: E402
from reportlab.lib.units import mm                            # noqa: E402
from reportlab.platypus import (                              # noqa: E402
    KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
)

from backend.app.engines.report_engine import (               # noqa: E402
    BAND, CRIT, INK, MUTED, RULE, VIOLET,
    S_BODY, S_H, S_MONO, S_SMALL, S_SUB, S_TITLE, _cell, _table,
)

OUT = ROOT / "docs" / "Violet_Milk_Prototype_Explainer.pdf"

# ----------------------------------------------------------------- helpers

def H(text):
    return Paragraph(text, S_H)


def P(text):
    return Paragraph(text, S_BODY)


def small(text):
    return Paragraph(text, S_SMALL)


def mono(text):
    return Paragraph(text, S_MONO)


def gap(h=3):
    return Spacer(1, h * mm)


def bullets(items):
    out = []
    for i in items:
        out.append(Paragraph(f"&bull;&nbsp;&nbsp;{i}", S_BODY))
        out.append(Spacer(1, 1.4 * mm))
    return out


def numbered(items):
    out = []
    for n, i in enumerate(items, start=1):
        out.append(Paragraph(f"<b>{n}.</b>&nbsp;&nbsp;{i}", S_BODY))
        out.append(Spacer(1, 1.6 * mm))
    return out


def beat(label, lines):
    """One movement of the speech: a stage label, then what to say."""
    out = [Paragraph(f"<font color='#4A3480'><b>{label}</b></font>", S_SMALL),
           Spacer(1, 1.2 * mm)]
    for ln in lines:
        out.append(Paragraph(ln, S_BODY))
        out.append(Spacer(1, 2 * mm))
    out.append(Spacer(1, 2.5 * mm))
    return out


def kv(rows, w=52):
    return _table([[_cell(k), Paragraph(v, S_BODY)] for k, v in rows],
                  widths=[w * mm, None], header=False)


# -------------------------------------------------------------------- page

def chrome(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(VIOLET)
    canvas.setFont("Helvetica-Bold", 7.5)
    canvas.drawString(18 * mm, h - 12 * mm, "PROJECT VIOLET MILK")
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(w - 18 * mm, h - 12 * mm,
                           "Prototype explainer - Chandigarh Police Hackathon")
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, h - 14 * mm, w - 18 * mm, h - 14 * mm)
    canvas.line(18 * mm, 15 * mm, w - 18 * mm, 15 * mm)
    canvas.setFont("Helvetica", 6.4)
    canvas.drawString(18 * mm, 11 * mm,
                      "Independent student prototype. Not an official police "
                      "system. Synthetic demonstration data.")
    canvas.drawRightString(w - 18 * mm, 11 * mm, f"Page {doc.page}")
    canvas.restoreState()


def cover(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(BAND)
    canvas.rect(0, h - 92 * mm, w, 92 * mm, stroke=0, fill=1)
    canvas.setFillColor(VIOLET)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(18 * mm, h - 34 * mm, "CHANDIGARH POLICE CYBER CRIME UNIT")
    canvas.setFillColor(INK)
    canvas.setFont("Helvetica-Bold", 31)
    canvas.drawString(18 * mm, h - 48 * mm, "Project Violet Milk")
    canvas.setFont("Helvetica", 13)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, h - 60 * mm,
                      "Prototype explainer and presentation script")
    canvas.setFont("Helvetica", 9)
    canvas.drawString(18 * mm, h - 72 * mm,
                      "Tracing cyber-fraud proceeds from an FIR to a court "
                      "dossier and a production order")
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 15 * mm, w - 18 * mm, 15 * mm)
    canvas.setFont("Helvetica", 6.4)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 11 * mm,
                      "Independent student prototype. Not an official police "
                      "system. Synthetic demonstration data.")
    canvas.restoreState()


# -------------------------------------------------------------------- body

def story():
    s: list = []

    # ------------------------------------------------------------- cover
    s.append(Spacer(1, 84 * mm))
    s.append(_table([
        [_cell("Case demonstrated"), mono("CP-CYBER-2026-001")],
        [_cell("Reported loss"), mono("INR 4,70,000")],
        [_cell("Chains traced"), Paragraph("Ethereum, Tron (TRC-20)", S_BODY)],
        [_cell("Automated tests"), mono("224 passing")],
        [_cell("API surface"), mono("23 paths")],
        [_cell("Licence"), Paragraph("MIT - free for any force to use", S_BODY)],
        [_cell("Cost per district"), Paragraph("Nil. No licence, no cloud "
                                               "account, no subscription.", S_BODY)],
        [_cell("Prepared"), Paragraph(date.today().strftime("%d %B %Y"), S_BODY)],
    ], widths=[46 * mm, None], header=False))
    s.append(gap(6))
    s.append(P(
        "This document has two halves. The first is the spoken presentation, "
        "written to be delivered standing, in about six minutes. The second "
        "explains every part of the system in the order a technical reviewer "
        "would want to inspect it."))
    s.append(PageBreak())

    # ------------------------------------------------- PART ONE: the speech
    s.append(Paragraph("Part One - the presentation", S_TITLE))
    s.append(Paragraph("Approximately six minutes, delivered standing",
                       S_SUB))
    s.append(gap(4))
    s.append(P(
        "Deliver the opening without touching the screen. The single most "
        "persuasive thing in this presentation is not a feature; it is that "
        "the system distinguishes what it knows from what it has guessed, and "
        "says so out loud before anyone asks."))
    s.append(gap(3))

    s += beat("OPENING - a specific human being", [
        "Sir, a resident of Chandigarh lost four lakh seventy thousand rupees "
        "to a digital arrest fraud. She did everything correctly. She called "
        "1930 within the hour.",
        "By then it was already too late, and I want to show you exactly how "
        "much too late. Her money left her bank account at ten thirty-one and "
        "four seconds. At ten thirty-two and two seconds - "
        "<b>fifty-eight seconds later</b> - it was USDT on a public "
        "blockchain, outside Indian banking, and outside anything the helpline "
        "can see.",
    ])

    s += beat("THE GAP - name it precisely", [
        "The Citizen Financial Cyber Fraud Reporting and Management System can "
        "freeze her bank account, and it is good at that. But at that "
        "fifty-eighth second the trail goes dark, and the officer who must "
        "write the chargesheet has nothing to work with.",
        "Not because he lacks the law. Section 94 of the Bharatiya Nagarik "
        "Suraksha Sanhita lets him compel any exchange in the country to "
        "produce its records. He lacks one thing only: he does not know "
        "<i>which</i> exchange, or <i>which</i> deposit address to name in "
        "that order.",
        "That is the entire gap. It is not a legal gap and it is not a policy "
        "gap. It is a capability gap, and it is narrow enough to close.",
    ])

    s += beat("WHAT WE BUILT - one sentence", [
        "So we built the thing that begins where 1930 stops, and ends with a "
        "signed piece of paper.",
    ])

    s += beat("CREDIBILITY - lead with the dashed line", [
        "One thing before I show you anything on the screen. On our map, every "
        "solid line is a bank record or a blockchain transaction hash that you "
        "can paste into a public explorer and check yourself. One line is "
        "dashed.",
        "That one we <i>inferred</i> - a thirteen-second gap between a "
        "UPI debit and an exchange deposit. It is a hypothesis, not a proven "
        "transfer. It is drawn differently on the screen, typed differently in "
        "the data, and printed as INFERRED on the face of the court document. "
        "Sixteen confirmed, one inferred.",
        "I mention it first because everything else I say is only worth "
        "something if you believe that distinction is real.",
    ])

    s.append(PageBreak())

    s += beat("THE MAP - show, do not narrate", [
        "This is the money. Victim, mule bank account, exchange, and then the "
        "wallet that received the USDT. That wallet scores sixty-five out of a "
        "hundred, and I can tell you exactly why: twenty points because it is "
        "the case seed, fifteen because funds left three minutes after they "
        "arrived, fifteen for a direct transfer into a mixer, and fifteen "
        "because a cross-chain bridge sits two hops downstream.",
        "Seven rules, fixed weights, evidence cited against each one. No model "
        "produced that number. A defence lawyer can check the addition, and I "
        "can explain it in a witness box.",
    ])

    s += beat("THE TURN - show the honest negative", [
        "Now I will show you something no other prototype today will show you. "
        "Our own tool will tell you it has <i>failed</i>.",
        "Sixty per cent of the tainted funds land in an exchange pool that "
        "already held clean money. The traced share falls to twelve per cent. "
        "Our own threshold is thirty per cent, so the system says NOT FLAGGED. "
        "That pool contains real criminal proceeds and we still report that "
        "the trail ends there.",
        "A tool that only ever says guilty is worthless in a courtroom. That "
        "negative result is what makes the sixty-five on the previous screen "
        "worth believing.",
    ])

    s += beat("THE AI QUESTION - answer before it is asked", [
        "You will want to know where the artificial intelligence is. Here it "
        "is, and look what it did. It flagged the <i>complainant</i>, because "
        "she moved the largest single amount and that makes her a statistical "
        "outlier.",
        "Her risk score is zero. The machine learning produces investigative "
        "leads on a separate screen with a separate shape, and it cannot touch "
        "a score. That is enforced by an automated test, not by a promise on "
        "a slide.",
    ])

    s += beat("CLOSING - Tuesday morning", [
        "Which brings me to the only question that actually matters. On "
        "Tuesday morning, what does the investigating officer do?",
        "He presses one button. Out comes a draft production order under "
        "Section 94, addressed to the exchange, with the deposit address, the "
        "amount, the timestamp and the transaction hash already written into "
        "the Schedule - and every line marked CONFIRMED or INFERRED so "
        "he knows in advance what a defence will contest. He completes his "
        "designation, has it checked, signs it, and serves it.",
        "It runs on one laptop. It works with the wifi unplugged. It costs "
        "nothing per district, and it is MIT licensed, so any force in this "
        "country can take it and use it without asking us.",
        "We are not asking you to believe it is finished. We are asking for "
        "three months in one cyber cell and one number back: how many cases "
        "where the trail continued past the bank. If that number is not "
        "meaningfully above zero, we have not earned anything.",
    ])

    s.append(PageBreak())

    # -------------------------------------------- PART TWO: the system
    s.append(Paragraph("Part Two - every aspect of the system",
                       S_TITLE))
    s.append(Paragraph("In the order a reviewer would inspect it", S_SUB))
    s.append(gap(4))

    # 1. The case
    s.append(H("1. The case being demonstrated"))
    s.append(P(
        "A single synthetic case, built to encode a real laundering pattern "
        "rather than to flatter the software. Every figure below is reproduced "
        "exactly by the engines on every run, and an automated test fails the "
        "build if any of them drift."))
    s.append(gap(2))
    s.append(_table([
        [_cell("Time (IST)"), _cell("Event"), _cell("Basis")],
        [mono("10:31:04"), P("Complainant to mule account, INR 4,70,000, "
                             "UTR 420192830192"), mono("CONFIRMED")],
        [mono("10:31:17"), P("Mule account to exchange deposit address, "
                             "13 seconds later"), mono("INFERRED")],
        [mono("10:32:02"), P("Exchange to seed wallet, 5,200 USDT at the "
                             "locked rate of INR 90.38"), mono("CONFIRMED")],
        [mono("10:35-10:36"), P("Seed disperses to exactly five wallets, one "
                                "directly into a mixer"), mono("CONFIRMED")],
        [mono("10:38-10:39"), P("Dispersal Wallet 1 splits into six smaller "
                                "amounts - structuring"), mono("CONFIRMED")],
        [mono("10:41:12"), P("2,000 USDT into a pool already holding 8,000 "
                             "clean"), mono("CONFIRMED")],
        [mono("10:44:19"), P("Final hop into the mixer. Mixer total: 1,900 "
                             "USDT"), mono("CONFIRMED")],
    ], widths=[24 * mm, None, 24 * mm]))
    s.append(gap(2))
    s.append(small(
        "Fourteen entities, seventeen transfers, thirteen minutes and fifteen "
        "seconds from first debit to final hop."))
    s.append(gap(4))

    # 2. Architecture
    s.append(H("2. Architecture"))
    s.append(P(
        "A <b>DataSource</b> interface with three implementations. The engines "
        "never learn which one is active, which is why a judge can hand over a "
        "live address mid-demonstration and nothing downstream changes."))
    s.append(gap(2))
    s.append(_table([
        [_cell("Layer"), _cell("Components")],
        [P("<b>Sources</b>"), P("SyntheticSource (bundled case), "
                                "EtherscanSource (Ethereum), TronSource "
                                "(TRC-20)")],
        [P("<b>Engines</b>"), P("graph, risk, dilution, timeline, anomaly, "
                                "assets, report, STR, notice, pipeline")],
        [P("<b>Services</b>"), P("audit, auth, anchor, ingestion, column "
                                 "mapper, narrative, LLM client, hashing, "
                                 "formatting")],
        [P("<b>Interface</b>"), P("React single-page application, served by "
                                  "the same process on the same port")],
    ], widths=[30 * mm, None]))
    s.append(gap(2))
    s.append(P(
        "An address routes itself: a value beginning <font face='Courier'>0x"
        "</font> is Ethereum, one beginning <font face='Courier'>T</font> is "
        "Tron. One command, one port, one SQLite file. No container, no "
        "database server, no cloud account."))
    s.append(PageBreak())

    # 3. Organs
    s.append(H("3. The eleven screens, and what each is for"))
    s.append(_table([
        [_cell("Screen"), _cell("What it answers")],
        [P("<b>Command Center</b>"), P("Opens on a worked case. Highest-risk "
                                       "entities and the recent custody trail.")],
        [P("<b>Case Intake</b>"), P("FIR and NCRP references, complainant "
                                    "loss, seed address.")],
        [P("<b>Evidence Ingestion</b>"), P("Upload a bank statement or "
                                           "transfer list. Rows merge into the "
                                           "case graph as typed entities.")],
        [P("<b>Graph Visualiser</b>"), P("The map. Solid is proven, dashed is "
                                         "inferred. Click any entity for a "
                                         "card an officer can act on.")],
        [P("<b>Asset Ledger</b>"), P("Which currency moved, at which layer of "
                                     "the trace, and what it is in rupees.")],
        [P("<b>Timeline</b>"), P("The same events as a clock. This is what "
                                 "makes the fifty-eight seconds land.")],
        [P("<b>Risk Inspector</b>"), P("Opens on the whole case, then the "
                                       "point-by-point arithmetic for any one "
                                       "entity.")],
        [P("<b>Dilution Calculator</b>"), P("How much of what sits at an "
                                            "address is traceable to the "
                                            "complainant.")],
        [P("<b>Flag Agent</b>"), P("Unsupervised model output, kept "
                                   "deliberately apart from scoring.")],
        [P("<b>Sec 63 BSA Dossier</b>"), P("The court document, the STR draft, "
                                           "and the production order draft.")],
        [P("<b>Chain of Custody</b>"), P("Every action, hash-chained, with a "
                                         "verify button that names any broken "
                                         "link.")],
    ], widths=[38 * mm, None]))
    s.append(gap(4))

    # 4. Risk rules
    s.append(H("4. The seven rules"))
    s.append(P(
        "Section 63 of the Bharatiya Sakshya Adhiniyam 2023 requires "
        "explaining how an electronic record was produced. Arithmetic can be "
        "explained to a court; a neural network cannot be cross-examined. That "
        "is the whole reason scoring is deterministic."))
    s.append(gap(2))
    s.append(_table([
        [_cell("Rule"), _cell("Points"), _cell("Fires when")],
        [mono("R1"), mono("+20"), P("Within one hop of the case seed")],
        [mono("R2"), mono("+15"), P("Funds leave within 240 seconds of "
                                    "arriving")],
        [mono("R3"), mono("+15"), P("Interaction with a known mixer contract")],
        [mono("R4"), mono("+15"), P("A cross-chain bridge within two hops "
                                    "downstream")],
        [mono("R5"), mono("+10"), P("Fan-out to more than five addresses")],
        [mono("R6"), mono("+10"), P("Structuring - repeated amounts under a "
                                    "reporting band")],
        [mono("R7"), mono("+15"), P("Time correlation with the victim debit. "
                                    "Suppressed when R1 fires, to avoid "
                                    "counting proximity twice.")],
    ], widths=[16 * mm, 18 * mm, None]))
    s.append(gap(2))
    s.append(P(
        "Bands: 0-24 LOW, 25-49 MEDIUM, 50-74 HIGH, 75-100 CRITICAL. The seed "
        "scores 65. An automated test asserts that every score equals the "
        "clamped sum of its own cited indicators, so a figure that did not "
        "come from these rules would fail the build."))
    s.append(gap(3))
    s.append(_table([
        [_cell("Honest limitation")],
        [P("The weights are reasoned, not calibrated. There is no empirical "
           "basis for twenty points rather than fifteen, and no labelled "
           "ground truth exists to measure a false positive rate against. "
           "What can be defended is that every score is reproducible and "
           "contestable: an accused can point at rule R4 and argue the bridge "
           "inference, which is impossible against an opaque model.")],
    ], widths=[None]))
    s.append(PageBreak())

    # 5. Dilution
    s.append(H("5. Dilution - and why there are two models"))
    s.append(P(
        "When tainted funds enter an address that already holds clean money, "
        "the traceable share falls. Proportional haircut is used because it "
        "makes the fewest assumptions a defence can attack: it says only that "
        "a pool mixes, whereas first-in-first-out requires assumptions about "
        "ordering."))
    s.append(gap(2))
    s.append(_table([
        [_cell("Hop"), _cell("Prior clean"), _cell("Tainted in"),
         _cell("Traceable share")],
        [P("Victim account"), mono("-"), mono("INR 4,70,000"), mono("100%")],
        [P("Seed wallet"), mono("0"), mono("5,200 USDT"), mono("100%")],
        [P("Layering wallet"), mono("1,200"), mono("1,800"), mono("60%")],
        [P("Exchange pool"), mono("8,000"), mono("2,000 at 60%"),
         mono("12% - NOT FLAGGED")],
    ], widths=[36 * mm, 26 * mm, 30 * mm, None]))
    s.append(gap(3))
    s.append(P(
        "<b>The second model exists because the first cannot honestly be "
        "used on a live chain.</b> A public explorer cannot tell you an "
        "address's balance at the moment funds arrived, so there is no "
        "denominator. Rather than print a confidently wrong ratio, live traces "
        "switch to a <font face='Courier'>propagation</font> model that "
        "carries a caveat stating in plain words that it measures reach, not "
        "proportion."))
    s.append(gap(4))

    # 6. Evidence and custody
    s.append(H("6. Evidence, custody and anchoring"))
    s.append(P(
        "Each custody entry hashes the entry before it, so altering any row "
        "breaks every hash that follows. The verify endpoint names the first "
        "broken link. A document's own digest is recorded separately, because "
        "a file cannot contain its own hash - that detached record is "
        "what makes a dossier verifiable afterwards."))
    s.append(gap(2))
    s.append(mono("entry_hash = SHA256(prev_hash | id | time | user | action "
                  "| target)"))
    s.append(gap(3))
    s.append(_table([
        [_cell("What this proves"), _cell("What it does not")],
        [P("That the log has not been altered without detection, and that a "
           "specific document existed in a specific state at a specific "
           "time."),
         P("That the document is true. Anyone with write access to the "
           "database could recompute the chain forward from an edit, which is "
           "why the wording everywhere is <i>detectable</i>, never "
           "tamper-proof.")],
    ], widths=[None, None]))
    s.append(gap(2))
    s.append(P(
        "Optional on-chain anchoring closes that gap by placing the digest "
        "somewhere outside our control. It proves existence and time. It does "
        "not prove authorship or truth, and the dossier says so in those "
        "words."))
    s.append(gap(4))

    s.append(PageBreak())

    # 7. Identity
    s.append(H("7. Identity - where a hex string becomes a person"))
    s.append(P(
        "This is the step most crypto-tracing demonstrations skip. A wallet "
        "address is not a person and this system never claims otherwise; the "
        "STR draft prints NOT IDENTIFIED in those words."))
    s.append(gap(2))
    s.append(P(
        "The lawful route runs through the exchange holding the KYC record, "
        "and the instrument is a written order under Section 94 BNSS 2023. "
        "One button assembles that order's recitals from the trace: the "
        "addressee, the deposit address, the amounts, the timestamps and the "
        "transaction hashes, together with the specific records sought - KYC, "
        "linked Indian bank accounts and UPI handles, IP and device logs, and "
        "the present status of any balance."))
    s.append(gap(2))
    s.append(_table([
        [_cell("Safeguard"), _cell("How it is enforced")],
        [P("Never a signed order"), P("Status is permanently DRAFT. A test "
                                      "walks the API schema and fails the "
                                      "build if any route appears that could "
                                      "issue or serve one.")],
        [P("Never invents an addressee"), P("The legal name and registered "
                                            "address are placeholders. We know "
                                            "an on-chain label, not a "
                                            "company's identity, and serving "
                                            "the wrong entity is a real "
                                            "harm.")],
        [P("Names nobody when nothing was found"),
         P("A trace that reached no exchange says so, rather than nominating "
           "the nearest address.")],
        [P("Ranks by tainted value"), P("A large clean inflow cannot make an "
                                        "address the right one to serve.")],
        [P("Declares its evidence"), P("Every line of the Schedule is marked "
                                       "CONFIRMED or INFERRED on the face of "
                                       "the order.")],
    ], widths=[46 * mm, None]))
    s.append(gap(4))

    # 8. AI
    s.append(H("8. Where the artificial intelligence is, and is not"))
    s.append(_table([
        [_cell("Component"), _cell("Role"), _cell("Touches a score?")],
        [P("Language model"), P("Drafts the officer's narrative paragraph and "
                                "guesses bank CSV column headings"),
         mono("No")],
        [P("Isolation Forest"), P("Flags behavioural outliers as investigative "
                                  "leads"), mono("No")],
        [P("DBSCAN"), P("Clusters wallets with similar behaviour"),
         mono("No")],
        [P("Seven rules"), P("Produce every risk figure in the system"),
         mono("Yes - only these")],
    ], widths=[34 * mm, None, 30 * mm]))
    s.append(gap(3))
    s.append(P(
        "<b>The proof, rather than the promise.</b> The anomaly model flags "
        "the complainant, because she moved the largest single amount and is "
        "therefore a statistical outlier. Her risk score is zero. If the model "
        "influenced scoring, the victim would be the prime suspect. That "
        "automated test is the reason the model is kept off the score."))
    s.append(gap(2))
    s.append(P(
        "Every AI feature degrades to a deterministic path. One test deletes "
        "the API key <i>and</i> the cache, then generates a complete dossier "
        "from the template and the heuristic column mapper. If the provider is "
        "unreachable on the day, nothing stops."))
    s.append(gap(4))

    # 9. Live mode
    s.append(H("9. Live mainnet, and surviving a dead network"))
    s += bullets([
        "Any Ethereum or Tron address can be pasted in and traced against the "
        "real chain, using the same rules, the same custody log and the same "
        "documents.",
        "Calls are self-throttled to three per second and every response is "
        "written to disk.",
        "A circuit breaker trips after three consecutive failures, so a dead "
        "network falls through to cache in about a second rather than sixty.",
        "A stage mode replays pre-tested addresses from disk without any "
        "network call at all. The interface still reports the source as "
        "cached, so a replay can never be presented as a live query.",
        "Traces are bounded - depth three, capped edges per entity, with each "
        "asset given a fair share of that budget so large native-currency "
        "figures cannot starve token transfers out. When a bound is reached "
        "the interface reports it rather than implying completeness.",
    ])
    s.append(gap(4))

    # 10. Cost
    s.append(H("10. Cost and practical feasibility in India today"))
    s.append(_table([
        [_cell("Component"), _cell("What is used"), _cell("Cost")],
        [P("Chain data"), P("Etherscan free tier"), mono("Nil")],
        [P("Tron data"), P("TronGrid free tier"), mono("Nil")],
        [P("Database"), P("SQLite - a single file"), mono("Nil")],
        [P("Software"), P("Python, FastAPI, React - all open source"),
         mono("Nil")],
        [P("AI narrative"), P("Optional; template fallback is tested"),
         mono("Nil")],
        [P("Hardware"), P("One laptop already on the desk"), mono("Existing")],
    ], widths=[32 * mm, None, 24 * mm]))
    s.append(gap(2))
    s.append(P(
        "<b>The marginal cost of adding another district is nil.</b> That is "
        "the argument - not that this is cheaper than the commercial "
        "tools, but that it sits in an entirely different category of purchase "
        "decision. There is no per-seat licence to renew and no procurement "
        "cycle to survive."))
    s.append(PageBreak())

    # 11. Where it sits
    s.append(H("11. Where this sits among systems that already exist"))
    s.append(_table([
        [_cell("System"), _cell("What it does"), _cell("Where it stops")],
        [P("<b>NCRP / 1930</b>"), P("Complaint intake and routing"),
         P("Not an analysis tool")],
        [P("<b>CFCFRMS</b>"), P("Golden-hour bank-to-bank freeze on UTRs"),
         P("The moment funds become crypto")],
        [P("<b>CCTNS</b>"), P("FIR and case records"),
         P("No financial tracing")],
        [P("<b>Commercial tracing</b>"), P("Address attribution at scale"),
         P("Per-seat foreign-currency licence; cloud dependent; no Indian "
           "statutory output")],
        [P("<b>This system</b>"), P("FIR to trace to Sec 63 dossier to Sec 94 "
                                    "production order, offline"),
         P("Attribution - fifteen curated labels, stated in writing")],
    ], widths=[34 * mm, None, 48 * mm]))
    s.append(gap(3))
    s.append(P(
        "We do not compete with commercial attribution and should not pretend "
        "to. Their product is address identification at scale, priced "
        "accordingly, which is why it sits at national agencies rather than in "
        "a district cyber cell. If a force ever buys that data, this workflow "
        "consumes it. An unlabelled address here renders as <i>unknown</i>, "
        "never as clean."))
    s.append(gap(4))

    # 12. Limits
    s.append(H("12. What this system does not claim"))
    s.append(P(
        "Every item below is printed in the repository, in the generated "
        "documents, or both. Volunteering them is cheaper than being caught by "
        "a question."))
    s.append(gap(2))
    s += numbered([
        "<b>The rule weights are not calibrated.</b> They are explainable, "
        "which is the point; they are not validated against outcomes.",
        "<b>The false positive rate is unknown.</b> There is no labelled "
        "ground truth, so any figure would be invented.",
        "<b>Bank clocks and block clocks are not the same clock.</b> Time "
        "correlation across the two is a lead, and is drawn as a dashed edge "
        "for exactly that reason.",
        "<b>Bitcoin is not supported.</b> The data model is account-based; "
        "Bitcoin is UTXO and needs a different graph plus a change-address "
        "heuristic that is itself a source of error.",
        "<b>Attribution is fifteen curated labels.</b> Absence of a label "
        "means unknown, never clean.",
        "<b>Chain reorganisations are not handled.</b> A trace records what "
        "the explorer returned at that moment, which is why the custody log "
        "timestamps it.",
        "<b>The statutory wording is unreviewed.</b> The Section 63 "
        "certificate and Section 94 order were drafted in good faith by "
        "people who are not lawyers, and say so on their face.",
        "<b>The interface is English only.</b> A bilingual interface is a "
        "fortnight of work and has not been done.",
        "<b>It is not affiliated with Chandigarh Police.</b> Stated in the "
        "first lines of the repository and in a permanent banner on every "
        "screen.",
    ])
    s.append(gap(3))

    # 13. Path
    s.append(H("13. What making this official would require"))
    s += numbered([
        "Legal review of the statutory wording, which everything downstream "
        "depends on.",
        "A CERT-In empanelled security audit, the standard prerequisite for "
        "handling case data on government infrastructure.",
        "A decision under the Digital Personal Data Protection Act 2023 on the "
        "AI narrative - either an in-house model, or shipping with the tested "
        "template path and no external transmission at all.",
        "Integration with CCTNS and NCRP, so an officer reads the FIR rather "
        "than retyping it.",
        "An attribution feed - realistically an arrangement with FIU-IND "
        "registered Indian exchanges, or a commercial licence layered "
        "underneath this workflow.",
        "Per-officer accounts and keys held in a hardware security module. "
        "Today there is one seeded officer and a default password the "
        "application itself warns about.",
        "A three-month pilot in one cyber cell, measured on one number: cases "
        "where the trail continued past the bank boundary.",
    ])
    s.append(gap(4))

    s.append(_table([
        [_cell("Closing note")],
        [P("This is an independent student prototype built for a hackathon. "
           "It is not affiliated with, endorsed by, or deployed by Chandigarh "
           "Police, FIU-IND or any law-enforcement agency. Agency names appear "
           "only to describe the intended user of a prototype. All "
           "demonstration identities, accounts, UPI handles and addresses are "
           "synthetic. The software produces investigative leads and "
           "supporting paperwork; it does not constitute a finding of guilt "
           "and does not identify any person without independent verification "
           "under Section 94 BNSS 2023.")],
    ], widths=[None]))

    return s


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title="Project Violet Milk - prototype explainer",
        author="Project Violet Milk",
    )
    doc.build(story(), onFirstPage=cover, onLaterPages=chrome)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
