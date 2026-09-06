"""
Generate frontend mock fixtures from the REAL engines.

Phase 1 hand-derived these numbers. Phase 2 replaced that with actual engine
output, so a fixture can no longer disagree with what the backend returns - the
frontend mocks ARE the engine's answer, captured to disk.

Writes identical JSON to both frontend/src/mocks/ and backend/app/data/mocks/.

Run:  python backend/tools/generate_mocks.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.engines.pipeline import analyse            # noqa: E402
from backend.app.main import app  # noqa: F401,E402  (seeds the demo case)
from backend.app.seed import SEED_WALLET, _CASE, _EVIDENCE  # noqa: E402
from backend.app.services import audit as audit_service     # noqa: E402

CASE_ID = "CP-CYBER-2026-001"
OUT_FRONTEND = ROOT / "frontend" / "src" / "mocks"
OUT_BACKEND = ROOT / "backend" / "app" / "data" / "mocks"

# Frozen so fixture diffs show real changes rather than a moving clock.
TRACED_AT = "2026-09-08T10:35:18+05:30"

_CASE_FIELDS = [
    "case_id", "fir_ref", "ncrp_ref", "victim_name", "victim_amount_inr",
    "incident_datetime", "seed_wallet", "seed_utr", "io_name", "notes",
    "status", "data_mode", "created_at", "updated_at",
]
_EVIDENCE_FIELDS = [
    "evidence_id", "case_id", "filename", "file_type", "size_bytes",
    "sha256_client", "sha256_server", "hash_match", "is_synthetic",
    "row_count", "column_mapping", "uploaded_at", "uploaded_by",
]


def _freeze(obj):
    """Pin generated timestamps so regeneration is byte-stable."""
    if isinstance(obj, dict):
        return {
            k: (TRACED_AT if k in {"computed_at", "traced_at"} else _freeze(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_freeze(x) for x in obj]
    return obj


def build() -> dict:
    a = analyse(CASE_ID, SEED_WALLET)

    graph = _freeze(a.graph().model_dump(mode="json"))
    dilution = _freeze(a.dilution.model_dump(mode="json"))
    timeline = _freeze([e.model_dump(mode="json") for e in a.timeline])
    risk = _freeze(a.risk[SEED_WALLET].model_dump(mode="json"))

    case = dict(zip(_CASE_FIELDS, _CASE))
    evidence = dict(zip(_EVIDENCE_FIELDS, _EVIDENCE))
    evidence["hash_match"] = bool(evidence["hash_match"])
    evidence["is_synthetic"] = bool(evidence["is_synthetic"])
    evidence["column_mapping"] = json.loads(evidence["column_mapping"])

    # Read the real chained rows so the fixtures carry genuine hashes.
    audit = _freeze(audit_service.for_case(CASE_ID))
    verification = audit_service.verify(CASE_ID).model_dump(mode="json")

    health = {
        "status": "ok", "data_mode": "synthetic", "version": "0.1.0",
        "components": {"database": True, "graph_engine": True,
                       "report_engine": False, "llm_configured": False,
                       "etherscan_configured": False},
    }

    anomaly = {
        "case_id": CASE_ID,
        "version": a.anomaly.version if a.anomaly else "anomaly-1.0",
        "trained": bool(a.anomaly and a.anomaly.trained),
        "reason": a.anomaly.reason if a.anomaly else "",
        "method": "IsolationForest + DBSCAN over behavioural graph features",
        "advisory": (
            "Unsupervised lead generation only. These findings do not "
            "contribute to any risk score and carry no evidentiary weight. An "
            "entity may be anomalous for entirely lawful reasons - the "
            "complainant is usually an outlier because they moved the largest "
            "single amount."
        ),
        "findings": [
            {"node_id": nid,
             "score": a.anomaly.scores.get(nid, 0.0),
             "cluster": a.anomaly.clusters.get(nid, -1),
             "explanation": a.anomaly.explanations.get(nid, "")}
            for nid in (a.anomaly.outliers if a.anomaly else [])
        ],
        "cluster_sizes": {str(k): v for k, v in
                          (a.anomaly.cluster_sizes if a.anomaly else {}).items()},
    }

    return {
        "anomaly.json": anomaly,
        "graph.json": graph,
        "case.json": case,
        "cases.json": [case],
        "timeline.json": timeline,
        "risk.json": risk,
        "dilution.json": dilution,
        "evidence.json": [evidence],
        "audit.json": audit,
        "audit_verify.json": verification,
        "health.json": health,
    }


def main() -> None:
    payloads = build()
    for target in (OUT_FRONTEND, OUT_BACKEND):
        target.mkdir(parents=True, exist_ok=True)
    for name, payload in payloads.items():
        blob = json.dumps(payload, indent=2, ensure_ascii=False)
        for target in (OUT_FRONTEND, OUT_BACKEND):
            (target / name).write_text(blob, encoding="utf-8")
        print(f"  wrote {name}")

    g = payloads["graph.json"]
    seed = next(n["data"] for n in g["elements"]["nodes"] if n["data"]["is_seed"])
    print(f"\n  nodes={g['stats']['nodes']} edges={g['stats']['edges']}")
    print(f"  seed score={seed['risk_score']} ({seed['risk_level']})")
    print(f"\nfixtures -> {OUT_FRONTEND}\n           {OUT_BACKEND}")


if __name__ == "__main__":
    main()
