"""
Generate frontend mock fixtures from the demo dataset.

Phase 1 deliverable. Both frontend developers build every organ against these
files with the backend switched off, and the backend stubs serve the exact same
JSON - so the two halves cannot drift apart before integration in Phase 4.

The dilution ratios and risk scores below are DERIVED BY HAND from the rules in
SPEC sections 05 and 06, and are locked by backend/tests/test_dataset_integrity.py.
When BE2 implements the real engines in Phase 2, those engines must reproduce
these exact numbers. That is the acceptance test.

Run:  python backend/tools/generate_mocks.py
"""

import csv
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "backend" / "app" / "data"
OUT = ROOT / "frontend" / "src" / "mocks"

CASE_ID = "CP-CYBER-2026-001"
SEED = "0xa7f39c1d8e4b2a5f7c3d9e0a1b8c6d4e5f2a67e9"
TRACED_AT = "2026-09-08T10:35:18+05:30"

# --- verified against SPEC 06 (haircut) -------------------------------------
ILLICIT_RATIO = {
    "VICTIM_4471": 0.0,
    "SBI_XXXXXXXX8891": 1.0,
    "0x3f1a7d92c04e8b56af10d3e7b829c45d6e0a71bc": 1.0,
    SEED: 1.0,
    "0x8589f2c47b1d0a63e95482f7ca1b3d6e0f4a0b6f": 1.0,
    "0x9c04a7e3b21d5f86c0a94e7d2b83f150c6ead21e": 1.0,
    "0x2d81b6f09c3a7e54d21b8f60a93c7e15d40b7f43": 0.60,   # 1200 clean + 1800 dirty
    "0x5e77c1a03d9b62f48e07c5a1b3d92f60e84ca908": 1.0,
    "0x1b93d5f27a08c6e41d3b90f52a7c68e04b1d4c67": 1.0,
    "0x7a2fe80c14d3b96a05e72f18c4d60b39a7e2b115": 1.0,
    "0x4c60a2d19f38b75e0c2a6d491f83b70e5c2ae882": 1.0,
    "0xe38b17d02c95a4f61b83d07e29c5a4f18b6039da": 1.0,
    "0xbb17d4a09e26c35f81b0d7a94e13c68f05b2c530": 1.0,
    "0xd90f42a17c58e03b96d1f47a20c85e39b7f481ab": 0.12,   # THE RESCUE - not flagged
}

# --- derived from the 7 rules in SPEC 05 ------------------------------------
RISK_SCORE = {
    "VICTIM_4471": 0,
    "SBI_XXXXXXXX8891": 35,
    "0x3f1a7d92c04e8b56af10d3e7b829c45d6e0a71bc": 35,
    SEED: 65,                                              # matches the UI mockup
    "0x8589f2c47b1d0a63e95482f7ca1b3d6e0f4a0b6f": 35,
    "0x9c04a7e3b21d5f86c0a94e7d2b83f150c6ead21e": 75,
    "0x2d81b6f09c3a7e54d21b8f60a93c7e15d40b7f43": 20,
    "0x5e77c1a03d9b62f48e07c5a1b3d92f60e84ca908": 35,
    "0x1b93d5f27a08c6e41d3b90f52a7c68e04b1d4c67": 20,
    "0x7a2fe80c14d3b96a05e72f18c4d60b39a7e2b115": 15,
    "0x4c60a2d19f38b75e0c2a6d491f83b70e5c2ae882": 0,
    "0xe38b17d02c95a4f61b83d07e29c5a4f18b6039da": 0,
    "0xbb17d4a09e26c35f81b0d7a94e13c68f05b2c530": 15,
    "0xd90f42a17c58e03b96d1f47a20c85e39b7f481ab": 0,
}

HOP_DEPTH = {
    "VICTIM_4471": 3, "SBI_XXXXXXXX8891": 2,
    "0x3f1a7d92c04e8b56af10d3e7b829c45d6e0a71bc": 1,
    SEED: 0,
    "0x8589f2c47b1d0a63e95482f7ca1b3d6e0f4a0b6f": 1,
    "0x9c04a7e3b21d5f86c0a94e7d2b83f150c6ead21e": 1,
    "0x2d81b6f09c3a7e54d21b8f60a93c7e15d40b7f43": 1,
    "0x5e77c1a03d9b62f48e07c5a1b3d92f60e84ca908": 1,
    "0x1b93d5f27a08c6e41d3b90f52a7c68e04b1d4c67": 1,
    "0x7a2fe80c14d3b96a05e72f18c4d60b39a7e2b115": 2,
    "0x4c60a2d19f38b75e0c2a6d491f83b70e5c2ae882": 2,
    "0xe38b17d02c95a4f61b83d07e29c5a4f18b6039da": 2,
    "0xbb17d4a09e26c35f81b0d7a94e13c68f05b2c530": 2,
    "0xd90f42a17c58e03b96d1f47a20c85e39b7f481ab": 2,
}


def level(score: int) -> str:
    if score >= 75:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "LOW"


def read(name):
    with (DATA / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def build():
    nodes = read("demo_nodes.csv")
    edges = read("demo_case.csv")

    # ---------------------------------------------------------- graph.json
    cy_nodes = []
    for n in nodes:
        nid = n["node_id"]
        score = RISK_SCORE[nid]
        cy_nodes.append({"data": {
            "id": nid,
            "label": n["label"],
            "type": n["node_type"],
            "chain": n["chain"],
            "risk_score": score,
            "risk_level": level(score),
            "illicit_ratio": ILLICIT_RATIO[nid],
            "balance": float(n["balance"]),
            "is_seed": n["is_seed"] == "true",
            "label_confidence": n["label_confidence"],
        }})

    cy_edges = [{"data": {
        "id": e["edge_id"],
        "source": e["from_node"],
        "target": e["to_node"],
        "amount": float(e["amount"]),
        "asset": e["asset"],
        "timestamp": e["timestamp"],
        "evidence_type": e["evidence_type"],
        "tx_hash": e["tx_hash"] or None,
        "block_number": int(e["block_number"]) if e["block_number"] else None,
        "hop_depth": HOP_DEPTH.get(e["to_node"], 0),
    }} for e in edges]

    graph = {
        "case_id": CASE_ID,
        "data_mode": "synthetic",
        "stats": {
            "nodes": len(cy_nodes), "edges": len(cy_edges),
            "max_depth_reached": 3, "traced_at": TRACED_AT,
            "source": "SyntheticSource", "truncated": False,
        },
        "elements": {"nodes": cy_nodes, "edges": cy_edges},
    }

    # ----------------------------------------------------------- case.json
    case = {
        "case_id": CASE_ID,
        "fir_ref": "FIR-2026-CHD-4471",
        "ncrp_ref": "1930-NCRP-2026-98124",
        "victim_name": "Complainant (synthetic)",
        "victim_amount_inr": 470000.0,
        "incident_datetime": "2026-09-08T10:31:04+05:30",
        "seed_wallet": SEED,
        "seed_utr": "420192830192",
        "io_name": "IO_SHARMA",
        "notes": "Victim received funds via UPI prior to USDT conversion.",
        "status": "active",
        "data_mode": "synthetic",
        "created_at": "2026-09-08T10:30:12+05:30",
        "updated_at": TRACED_AT,
    }

    # ------------------------------------------------------- timeline.json
    timeline, prev = [], None
    labels = {
        "E01": ("Victim initiates UPI transfer of INR 4,70,000", "bank"),
        "E02": ("Correlated deposit detected at exchange (INFERRED)", "bank"),
        "E03": ("Seed wallet receives 5,200 USDT", "onchain"),
        "E04": ("Funds routed to mixer contract", "onchain"),
    }
    for e in edges:
        ts = datetime.fromisoformat(e["timestamp"])
        delta = int((ts - prev).total_seconds()) if prev else 0
        desc, src = labels.get(
            e["edge_id"],
            (f"Transfer of {float(e['amount']):,.0f} {e['asset']}", "onchain"),
        )
        timeline.append({
            "event_id": f"EV-{e['edge_id']}",
            "case_id": CASE_ID,
            "timestamp": e["timestamp"],
            "event_type": e["evidence_type"],
            "description": desc,
            "node_id": e["to_node"],
            "edge_id": e["edge_id"],
            "delta_seconds_prev": delta,
            "source": src,
        })
        prev = ts

    # ----------------------------------------------------------- risk.json
    risk_seed = {
        "node_id": SEED, "case_id": CASE_ID,
        "score": 65, "level": "HIGH", "illicit_ratio": 1.0,
        "engine_version": "risk-1.0", "computed_at": TRACED_AT,
        "indicators": [
            {"rule_id": "R1", "name": "Proximity to known scam cluster",
             "points": 20, "evidence": "hop_depth=0 (case seed address)",
             "confidence": "confirmed"},
            {"rule_id": "R2", "name": "Rapid automated dispersal",
             "points": 15,
             "evidence": "received 10:32:02, first outbound 10:35:02 (+3m00s)",
             "confidence": "confirmed"},
            {"rule_id": "R3", "name": "Mixer contract interaction",
             "points": 15, "evidence": "E04 -> 0x8589...0b6f, 1,500 USDT",
             "confidence": "confirmed"},
            {"rule_id": "R4", "name": "Cross-chain bridge exposure",
             "points": 15, "evidence": "bridge 0xbb17...c530 reached within 2 hops",
             "confidence": "inferred"},
        ],
    }

    # ------------------------------------------------------- dilution.json
    dilution = {
        "case_id": CASE_ID, "threshold": 0.30, "version": "haircut-1.0",
        "computed_at": TRACED_AT,
        "steps": [
            {"node_id": SEED, "prior_balance": 0.0, "incoming_amount": 5200.0,
             "incoming_ratio": 1.0, "dirty_received": 5200.0,
             "total_after": 5200.0, "illicit_ratio": 1.0, "flagged": True},
            {"node_id": "0x2d81b6f09c3a7e54d21b8f60a93c7e15d40b7f43",
             "prior_balance": 1200.0, "incoming_amount": 1800.0,
             "incoming_ratio": 1.0, "dirty_received": 1800.0,
             "total_after": 3000.0, "illicit_ratio": 0.60, "flagged": True},
            {"node_id": "0xd90f42a17c58e03b96d1f47a20c85e39b7f481ab",
             "prior_balance": 8000.0, "incoming_amount": 2000.0,
             "incoming_ratio": 0.60, "dirty_received": 1200.0,
             "total_after": 10000.0, "illicit_ratio": 0.12, "flagged": False},
        ],
    }

    # ------------------------------------------------------- evidence.json
    evidence = [{
        "evidence_id": "EV-8f3a2c17", "case_id": CASE_ID,
        "filename": "Bank_Stmt_SBI.csv", "file_type": "csv",
        "size_bytes": 1258291,
        "sha256_client": "9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a",
        "sha256_server": "9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a",
        "hash_match": True, "is_synthetic": True, "row_count": 17,
        "column_mapping": {"UTR": "utr", "Txn Date": "timestamp",
                           "Withdrawal Amt.": "amount", "Bank": "bank"},
        "uploaded_at": "2026-09-08T10:30:45+05:30", "uploaded_by": "IO_SHARMA",
    }]

    # ---------------------------------------------------------- audit.json
    audit = [
        {"audit_id": "A-001", "case_id": CASE_ID,
         "timestamp": "2026-09-08T10:30:12+05:30", "user_id": "IO_SHARMA",
         "action": "CASE_CREATED", "target": CASE_ID, "target_hash": None,
         "details": {}},
        {"audit_id": "A-002", "case_id": CASE_ID,
         "timestamp": "2026-09-08T10:30:45+05:30", "user_id": "IO_SHARMA",
         "action": "EVIDENCE_UPLOADED", "target": "Bank_Stmt_SBI.csv",
         "target_hash": "9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a",
         "details": {"rows": 17}},
        {"audit_id": "A-003", "case_id": CASE_ID, "timestamp": TRACED_AT,
         "user_id": "IO_SHARMA", "action": "TRACE_RUN", "target": SEED,
         "target_hash": None,
         "details": {"max_depth": 3, "nodes": 14, "edges": 17}},
    ]

    health = {
        "status": "ok", "data_mode": "synthetic", "version": "0.1.0",
        "components": {"database": True, "graph_engine": True,
                       "report_engine": True, "llm_configured": False,
                       "etherscan_configured": False},
    }

    return {
        "graph.json": graph,
        "case.json": case,
        "cases.json": [case],
        "timeline.json": timeline,
        "risk.json": risk_seed,
        "dilution.json": dilution,
        "evidence.json": evidence,
        "audit.json": audit,
        "health.json": health,
    }


def main():
    # Written to BOTH locations from one source, so the frontend fixtures and
    # the backend Phase-1 stubs are byte-identical and cannot drift.
    targets = [OUT, ROOT / "backend" / "app" / "data" / "mocks"]
    for t in targets:
        t.mkdir(parents=True, exist_ok=True)

    for name, payload in build().items():
        blob = json.dumps(payload, indent=2, ensure_ascii=False)
        for t in targets:
            (t / name).write_text(blob, encoding="utf-8")
        print(f"  wrote {name}")

    for t in targets:
        print(f"\nmock fixtures -> {t}")


if __name__ == "__main__":
    main()
