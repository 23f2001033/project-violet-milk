"""Graph Engine router  ·  owner: BE1  ·  Phase 2: real bounded traversal."""

from fastapi import APIRouter, HTTPException

from ..config import MAX_EDGES_PER_NODE, MAX_TRACE_DEPTH
from ..db import cursor
from ..engines.pipeline import get_analysis
from ..models import (
    AuditAction, GraphResponse, Label, TraceRequest, TraceResult,
)
from ..services import audit
from ..sources.synthetic import SyntheticSource

router = APIRouter(prefix="/api", tags=["graph"])


def _seed_for(case_id: str) -> str:
    with cursor() as conn:
        row = conn.execute(
            "SELECT seed_wallet FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
    if not row or not row["seed_wallet"]:
        raise HTTPException(404, f"Case {case_id} has no seed wallet on record")
    return row["seed_wallet"]


@router.post("/cases/{case_id}/trace", response_model=TraceResult,
             summary="Run a bounded trace from a seed address")
def run_trace(case_id: str, payload: TraceRequest):
    if payload.max_depth > MAX_TRACE_DEPTH:
        raise HTTPException(
            400,
            f"max_depth {payload.max_depth} exceeds the configured ceiling of "
            f"{MAX_TRACE_DEPTH}. Unbounded traversal on a real wallet will "
            f"exhaust the API rate limit and freeze the browser.",
        )
    if payload.max_edges_per_node > MAX_EDGES_PER_NODE:
        raise HTTPException(
            400, f"max_edges_per_node exceeds the ceiling of {MAX_EDGES_PER_NODE}."
        )

    a = get_analysis(
        case_id, payload.seed,
        max_depth=payload.max_depth,
        min_amount=payload.min_amount,
        max_edges_per_node=payload.max_edges_per_node,
        time_window_hours=payload.time_window_hours,
    )
    if not a.nodes:
        raise HTTPException(404, f"Seed {payload.seed} not present in this dataset")

    audit.record(
        case_id, AuditAction.TRACE_RUN, payload.seed,
        details={"max_depth": payload.max_depth, "nodes": len(a.nodes),
                 "edges": len(a.edges), "source": a.source_name,
                 "truncated": a.truncated},
    )

    return TraceResult(
        case_id=case_id,
        seed=payload.seed,
        stats=a.stats(),
        node_ids=[n.node_id for n in a.nodes],
        edge_ids=[e.edge_id for e in a.edges],
    )


@router.get("/cases/{case_id}/graph", response_model=GraphResponse,
            summary="Cytoscape-ready node/edge elements")
def get_graph(case_id: str):
    return get_analysis(case_id, _seed_for(case_id)).graph()


@router.get("/labels/{address}", response_model=Label,
            summary="Resolve an address label")
def get_label(address: str):
    # Phase 6 adds the curated known_addresses.json lookup for live mode.
    found = SyntheticSource("lookup").get_label(address)
    if not found:
        raise HTTPException(404, f"No label on record for {address}")
    return found
