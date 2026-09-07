"""
Generate the per-officer demonstration cases.

    .venv\\Scripts\\python.exe backend\\tools\\generate_cases.py

CP-CYBER-2026-001 is NOT produced here. It is the locked dataset whose numbers
are asserted by test_dataset_integrity, and it stays exactly as committed.

The three cases below are modelled on typologies that actually dominate Indian
cyber-fraud casework rather than on whatever makes the software look good:

  002  Task-based "part-time job" fraud with a mule network. Many small
       victims, aggregation through collector accounts, cash-out via a P2P
       trader into USDT on TRON - which is the rail the proceeds really move
       on, not Ethereum.

  003  Digital arrest fraud with chain-hopping. Fewer victims, larger amounts,
       and a deliberate ETH -> bridge -> TRON -> exchange path that exists to
       break a single-chain tracer. Includes a pool that dilutes the taint
       below the reporting threshold, because that outcome is real.

  004  A short UPI trail that ends at a KYC'd Indian exchange in three hops.
       Deliberately simple. Not every case is a maze, and a tool that only
       ever produces a spider's web is lying about the job.

Everything is deterministic: transaction hashes are sha256(edge_id), so the
files regenerate byte-identically and a demonstration cannot drift between
rehearsal and stage.
"""

from __future__ import annotations

import csv
import hashlib
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "backend" / "app" / "data" / "cases"

NODE_COLS = ["node_id", "node_type", "label", "chain", "prior_balance",
             "balance", "is_seed", "label_source", "label_confidence"]
EDGE_COLS = ["edge_id", "from_node", "to_node", "amount", "asset", "timestamp",
             "evidence_type", "tx_hash", "utr", "block_number"]

IST = "+05:30"


def tx(edge_id: str) -> str:
    """Deterministic 32-byte hash. Regenerating must never change a hash that
    has already been recited in a generated production order."""
    return "0x" + hashlib.sha256(edge_id.encode()).hexdigest()


def addr(seed: str) -> str:
    """A stable synthetic Ethereum address."""
    return "0x" + hashlib.sha256(seed.encode()).hexdigest()[:40]


def tron_addr(seed: str) -> str:
    """A stable synthetic Tron address.

    Base58 excludes 0, O, I and l; using the full alphabet would produce
    addresses that our own validator rejects.
    """
    b58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    h = hashlib.sha256(seed.encode()).digest()
    return "T" + "".join(b58[b % len(b58)] for b in h[:33])


class Case:
    def __init__(self, case_id: str, start: str):
        self.case_id = case_id
        self.t0 = datetime.fromisoformat(start)
        self.nodes: list[dict] = []
        self.edges: list[dict] = []
        self._n = 0

    def node(self, node_id, node_type, label="", chain="ethereum",
             prior=0.0, balance=0.0, seed=False, src=None, conf=None):
        self.nodes.append({
            "node_id": node_id,
            "node_type": node_type,
            "label": label,
            "chain": chain,
            "prior_balance": f"{prior:.2f}",
            "balance": f"{balance:.2f}",
            "is_seed": "true" if seed else "false",
            "label_source": src or ("curated" if label else "none"),
            "label_confidence": conf or ("confirmed" if label else "unknown"),
        })
        return node_id

    def edge(self, frm, to, amount, asset, minutes, kind="confirmed_onchain",
             utr="", block=None):
        self._n += 1
        eid = f"{self.case_id}-E{self._n:03d}"
        ts = (self.t0 + timedelta(minutes=minutes)).isoformat() + IST
        self.edges.append({
            "edge_id": eid,
            "from_node": frm,
            "to_node": to,
            "amount": f"{amount:.2f}",
            "asset": asset,
            "timestamp": ts,
            "evidence_type": kind,
            "tx_hash": "" if kind == "confirmed_bank" else tx(eid),
            "utr": utr,
            "block_number": block or "",
        })
        return eid

    def write(self):
        d = OUT_DIR / self.case_id
        d.mkdir(parents=True, exist_ok=True)
        with (d / "nodes.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, NODE_COLS)
            w.writeheader()
            w.writerows(self.nodes)
        with (d / "edges.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, EDGE_COLS)
            w.writeheader()
            w.writerows(self.edges)
        print(f"  {self.case_id}: {len(self.nodes)} nodes, "
              f"{len(self.edges)} transfers -> {d.relative_to(ROOT)}")


# --------------------------------------------------------------------- 002

def case_002() -> Case:
    """Task-based fraud, mule network, cash-out to USDT on Tron.

    The shape that matters here is the FUNNEL: many small victims who each
    individually fall below the amount that gets a case prioritised, feeding
    two collector accounts that together hold a figure nobody would ignore.
    That is the argument for tracing rather than triaging by amount.
    """
    c = Case("CP-CYBER-2026-002", "2026-08-19T09:12:00")

    victims = [
        ("VICTIM_8801", "Complainant 1 (synthetic)", 118000),
        ("VICTIM_8802", "Complainant 2 (synthetic)", 96500),
        ("VICTIM_8803", "Complainant 3 (synthetic)", 242000),
        ("VICTIM_8804", "Complainant 4 (synthetic)", 87000),
        ("VICTIM_8805", "Complainant 5 (synthetic)", 315000),
        ("VICTIM_8806", "Complainant 6 (synthetic)", 84500),
    ]
    mules = [
        ("HDFC_XXXXXXXX2245", "Mule Account - HDFC (synthetic)"),
        ("PNB_XXXXXXXX7710", "Mule Account - PNB (synthetic)"),
        ("SBI_XXXXXXXX3391", "Mule Account - SBI (synthetic)"),
        ("ICICI_XXXXXXXX5502", "Mule Account - ICICI (synthetic)"),
        ("AXIS_XXXXXXXX8834", "Mule Account - Axis (synthetic)"),
        ("KOTAK_XXXXXXXX1188", "Mule Account - Kotak (synthetic)"),
    ]

    for (vid, vlabel, amt), (mid, mlabel) in zip(victims, mules):
        c.node(vid, "victim", vlabel, "bank_inr", prior=amt)
        c.node(mid, "bank_account", mlabel, "bank_inr")

    collectors = [
        c.node("COLLECT_UPI_4471", "upi_handle",
               "Aggregator UPI handle (synthetic)", "upi"),
        c.node("COLLECT_UPI_4472", "upi_handle",
               "Aggregator UPI handle (synthetic)", "upi"),
    ]
    p2p = c.node("P2P_TRADER_INR_09", "exchange",
                 "P2P trader - INR to USDT (synthetic)", "upi",
                 conf="inferred")

    # Victim -> mule, minutes apart across a single morning.
    for i, ((vid, _, amt), (mid, _)) in enumerate(zip(victims, mules)):
        c.edge(vid, mid, amt, "INR", i * 7, "confirmed_bank",
               utr=f"9411{i}82030{i}91")

    # Mules -> collectors. Six accounts funnel into two.
    for i, ((mid, _), (_, _, amt)) in enumerate(zip(mules, victims)):
        c.edge(mid, collectors[i % 2], amt * 0.985, "INR", 42 + i * 4,
               "confirmed_bank", utr=f"7720{i}4471{i}03")

    # Collectors -> P2P trader. INFERRED: a UPI debit and a trader credit
    # minutes apart is a correlation, not a proven transfer.
    c.edge(collectors[0], p2p, 493000, "INR", 74, "inferred_correlation")
    c.edge(collectors[1], p2p, 429000, "INR", 79, "inferred_correlation")

    # Cash-out to USDT on Tron at the locked demo rate.
    seed = c.node(tron_addr("c2-seed"), "wallet", "Target Seed Wallet", "tron",
                  seed=True)
    c.edge(p2p, seed, 10200.00, "USDT", 96, block=64_112_009)

    # Layering: fan-out to seven, then a second ring. Amounts deliberately
    # sit under round reporting bands - that is what structuring looks like.
    mixer = c.node(tron_addr("c2-mixer"), "mixer",
                   "Mixing service (synthetic)", "tron", balance=3700)

    # Dispersal begins under three minutes after the funds land. That window
    # is the whole signature of an automated cash-out, and it is what R2 looks
    # for; a human moving money by hand does not manage it.
    layer1 = [c.node(tron_addr(f"c2-L1-{i}"), "wallet", chain="tron")
              for i in range(7)]
    c.edge(seed, mixer, 600, "USDT", 98, block=64_112_018)
    for i, w in enumerate(layer1):
        c.edge(seed, w, [2400, 1900, 1750, 1500, 1200, 900, 550][i], "USDT",
               99 + i * 2, block=64_112_020 + i)
    bridge = c.node(tron_addr("c2-bridge"), "bridge",
                    "Cross-chain bridge (synthetic)", "tron", conf="inferred")
    c.edge(layer1[0], mixer, 2400, "USDT", 128, block=64_112_071)
    c.edge(layer1[1], mixer, 700, "USDT", 133, block=64_112_078)
    c.edge(layer1[2], bridge, 1750, "USDT", 140, block=64_112_090)

    # Bridge lands on Ethereum, then to an offshore exchange.
    eth_hop = c.node(addr("c2-eth-hop"), "wallet", chain="ethereum")
    offshore = c.node(addr("c2-offshore"), "exchange",
                      "Offshore exchange deposit (synthetic)", "ethereum",
                      prior=41000, balance=42730, conf="inferred")
    c.edge(bridge, eth_hop, 1730, "USDT", 154, block=19_880_411)
    c.edge(eth_hop, offshore, 1730, "USDT", 168, block=19_880_520)

    # A domestic, KYC-bearing exchange - the addressee a production order can
    # actually be served on.
    domestic = c.node(tron_addr("c2-domestic"), "exchange",
                      "Indian VDA exchange deposit (synthetic)", "tron",
                      prior=2600, balance=4100, conf="inferred")
    c.edge(layer1[3], domestic, 1500, "USDT", 147, block=64_112_101)
    c.edge(layer1[4], domestic, 1200, "USDT", 151, block=64_112_108)

    # Remainder dribbles onward, small and slow.
    tail = [c.node(tron_addr(f"c2-T{i}"), "wallet", chain="tron")
            for i in range(4)]
    c.edge(layer1[5], tail[0], 900, "USDT", 176, block=64_112_140)
    c.edge(layer1[6], tail[1], 550, "USDT", 182, block=64_112_151)
    c.edge(tail[0], tail[2], 620, "USDT", 205, block=64_112_206)
    c.edge(tail[1], tail[3], 380, "USDT", 214, block=64_112_231)
    c.edge(tail[2], mixer, 620, "USDT", 236, block=64_112_290)
    return c


# --------------------------------------------------------------------- 003

def case_003() -> Case:
    """Digital arrest fraud, chain-hopping, and a pool that dilutes the taint.

    Built to make one point an officer needs and no brochure admits: the trail
    can end. The exchange pool here receives genuine proceeds and still falls
    under the reporting threshold, and the tool says so.
    """
    c = Case("CP-CYBER-2026-003", "2026-07-03T14:26:00")

    victims = [
        ("VICTIM_5511", "Complainant - retired (synthetic)", 640000),
        ("VICTIM_5512", "Complainant - salaried (synthetic)", 310000),
        ("VICTIM_5513", "Complainant - small trader (synthetic)", 175000),
        ("VICTIM_5514", "Complainant - student (synthetic)", 92000),
    ]
    for vid, lbl, amt in victims:
        c.node(vid, "victim", lbl, "bank_inr", prior=amt)

    mules = [c.node(m, "bank_account", f"Mule Account - {b} (synthetic)",
                    "bank_inr")
             for m, b in [("BOB_XXXXXXXX4417", "Bank of Baroda"),
                          ("CANARA_XXXXXXXX9903", "Canara"),
                          ("IDFC_XXXXXXXX2276", "IDFC First")]]

    for i, (vid, _, amt) in enumerate(victims):
        c.edge(vid, mules[i % 3], amt, "INR", i * 11, "confirmed_bank",
               utr=f"5530{i}1177{i}42")

    cex_in = c.node(addr("c3-cex-in"), "exchange",
                    "CEX Deposit Address (synthetic)", "ethereum",
                    conf="inferred")
    for i, m in enumerate(mules):
        c.edge(m, cex_in, [950000, 175000, 92000][i], "INR", 58 + i * 6,
               "inferred_correlation")

    seed = c.node(addr("c3-seed"), "wallet", "Target Seed Wallet", "ethereum",
                  seed=True)
    c.edge(cex_in, seed, 4.42, "ETH", 84, block=20_114_880)
    c.edge(cex_in, seed, 9100.00, "USDT", 88, block=20_114_902)

    mixer = c.node(addr("c3-mixer"), "mixer", "Mixing service (synthetic)",
                   "ethereum", balance=3900)

    # Split within the rapid-dispersal window, then hop chains deliberately.
    hops = [c.node(addr(f"c3-H{i}"), "wallet", chain="ethereum")
            for i in range(5)]
    c.edge(seed, mixer, 700, "USDT", 90, block=20_114_925)
    for i, h in enumerate(hops):
        c.edge(seed, h, [3200, 2400, 1800, 1100, 600][i], "USDT",
               91 + i * 2, block=20_114_930 + i * 3)
    c.edge(seed, hops[0], 4.42, "ETH", 118, block=20_115_010)

    bridge = c.node(addr("c3-bridge"), "bridge",
                    "Cross-chain bridge (synthetic)", "ethereum",
                    conf="inferred")
    c.edge(hops[1], bridge, 2400, "USDT", 131, block=20_115_066)
    c.edge(hops[2], bridge, 1800, "USDT", 138, block=20_115_094)

    tron_land = c.node(tron_addr("c3-tron"), "wallet", chain="tron")
    c.edge(bridge, tron_land, 4150, "USDT", 152, block=63_907_441)

    c.edge(hops[0], mixer, 3200, "USDT", 144, block=20_115_120)

    # THE POOL. Real proceeds arrive, and the traceable share collapses.
    pool = c.node(addr("c3-pool"), "wallet", "High-liquidity pool (clean)",
                  "ethereum", prior=39000, balance=43150, conf="inferred")
    c.edge(tron_land, pool, 4150, "USDT", 171, block=20_115_260)

    # A slice comes back to India through a P2P trader paying out in rupees -
    # the leg that makes the case actionable again.
    p2p_out = c.node("P2P_TRADER_INR_31", "exchange",
                     "P2P trader - USDT to INR (synthetic)", "upi",
                     conf="inferred")
    payout = c.node("YESB_XXXXXXXX6640", "bank_account",
                    "Payout account (synthetic)", "bank_inr")
    c.edge(hops[3], p2p_out, 1100, "USDT", 186, block=20_115_301)
    c.edge(p2p_out, payout, 99400, "INR", 214, "inferred_correlation")

    dom = c.node(addr("c3-domestic"), "exchange",
                 "Indian VDA exchange deposit (synthetic)", "ethereum",
                 prior=1400, balance=2000, conf="inferred")
    c.edge(hops[4], dom, 600, "USDT", 197, block=20_115_340)
    return c


# --------------------------------------------------------------------- 004

def case_004() -> Case:
    """A short UPI trail that ends somewhere a notice can be served.

    Kept small on purpose. Most demonstrations only ever show the maze; an
    officer also needs to see the case that resolves in three hops, because
    that is the one where a production order goes out the same day.
    """
    c = Case("CP-CYBER-2026-004", "2026-09-01T11:04:00")

    v = c.node("VICTIM_2290", "victim", "Complainant (synthetic)",
               "bank_inr", prior=185000)

    mule = c.node("UNION_XXXXXXXX3308", "bank_account",
                  "Mule Account - Union Bank (synthetic)", "bank_inr")
    upi = c.node("scampay@oksbi", "upi_handle",
                 "UPI handle (synthetic)", "upi")
    dep = c.node(addr("c4-dep"), "exchange",
                 "Indian VDA exchange deposit (synthetic)", "ethereum",
                 conf="inferred")
    seed = c.node(addr("c4-seed"), "wallet", "Target Seed Wallet", "ethereum",
                  seed=True)
    onward = [c.node(addr(f"c4-W{i}"), "wallet", chain="ethereum")
              for i in range(3)]

    c.edge(v, mule, 185000, "INR", 0, "confirmed_bank", utr="330891204471")
    c.edge(mule, upi, 185000, "INR", 6, "confirmed_bank", utr="330891204472")
    c.edge(upi, dep, 185000, "INR", 13, "inferred_correlation")
    c.edge(dep, seed, 2046.00, "USDT", 22, block=20_551_770)
    c.edge(seed, onward[0], 1200, "USDT", 31, block=20_551_802)
    c.edge(seed, onward[1], 500, "USDT", 36, block=20_551_819)
    c.edge(seed, onward[2], 340, "USDT", 41, block=20_551_833)
    c.edge(onward[0], dep, 1200, "USDT", 68, block=20_551_940)
    return c


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("generating demonstration cases (001 is locked and untouched)")
    for build in (case_002, case_003, case_004):
        build().write()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
