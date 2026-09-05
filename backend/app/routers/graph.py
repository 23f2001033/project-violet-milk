"""Graph Engine  ·  owner: BE1  ·  Phase 1 = fixture stubs.

Phase 2 replaces the fixture with SyntheticSource + bounded BFS. The response
shape is frozen and Cytoscape-ready: the frontend performs no transformation.
"""

from fastapi import APIRouter, HTTPException

from ..config import MAX_EDGES_PER_NODE, MAX_TRACE_DEPTH
from ..models import GraphResponse, Label, TraceRequest, TraceResult
from ..stubs import load

router = APIRouter(prefix="/api", tags=["graph"])


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

    graph = load("graph.json")
    return TraceResult(
        case_id=case_id,
        seed=payload.seed,
        stats=graph["stats"],
        node_ids=[n["data"]["id"] for n in graph["elements"]["nodes"]],
        edge_ids=[e["data"]["id"] for e in graph["elements"]["edges"]],
    )


@router.get("/cases/{case_id}/graph", response_model=GraphResponse,
            summary="Cytoscape-ready node/edge elements")
def get_graph(case_id: str):
    return load("graph.json")


@router.get("/labels/{address}", response_model=Label,
            summary="Resolve an address label")
def get_label(address: str):
    # BE1 Phase 2: curated known_addresses.json first, then the provider.
    raise HTTPException(404, f"No label on record for {address}")
