"""Graph Engine router  ·  owner: BE1  ·  Phase 2: real bounded traversal."""

from fastapi import APIRouter, HTTPException

from ..config import MAX_EDGES_PER_NODE, MAX_TRACE_DEPTH
from ..db import cursor
from ..engines.pipeline import get_analysis
from ..models import (
    AuditAction, GraphResponse, Label, TraceRequest, TraceResult,
)
from ..models import AuthUser
from ..services import audit
from .auth import RequireUser
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
def run_trace(case_id: str, payload: TraceRequest,
              user: AuthUser = RequireUser):
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

    mode = payload.data_mode.value
    a = get_analysis(
        case_id, payload.seed,
        max_depth=payload.max_depth,
        min_amount=payload.min_amount,
        max_edges_per_node=payload.max_edges_per_node,
        time_window_hours=payload.time_window_hours,
        data_mode=mode,
    )
    if not a.nodes:
        raise HTTPException(
            404,
            f"No transactions found for {payload.seed}"
            + (" on Ethereum mainnet." if mode == "live"
               else " in the bundled dataset."),
        )

    audit.record(
        case_id, AuditAction.TRACE_RUN, payload.seed, user_id=user.user_id,
        details={"max_depth": payload.max_depth, "nodes": len(a.nodes),
                 "edges": len(a.edges), "source": a.source_name,
                 "truncated": a.truncated, "data_mode": mode},
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
def get_graph(case_id: str, seed: str | None = None,
              data_mode: str = "synthetic"):
    """`seed` and `data_mode` let the UI render a live mainnet trace without
    mutating the stored case. Omitted, it returns the case's own synthetic
    graph - so the scripted demo path is unaffected by live experiments."""
    target = seed or _seed_for(case_id)

    # A live address is hub-and-spoke: one wallet with dozens of counterparties.
    # At the default cap that produced 59 nodes - technically correct, and
    # unreadable on a projector at the back of a room. A demonstration graph
    # must be legible or it communicates nothing, so live traces use a tighter
    # per-node cap and report `truncated` so the bound is never hidden.
    kwargs = ({"max_edges_per_node": 6, "max_depth": 2}
              if data_mode == "live" else {})

    a = get_analysis(case_id, target, data_mode=data_mode, **kwargs)
    if not a.nodes:
        raise HTTPException(404, f"No transactions found for {target}")
    return a.graph()


@router.get("/labels/{address}", response_model=Label,
            summary="Resolve an address label")
def get_label(address: str):
    # Phase 6 adds the curated known_addresses.json lookup for live mode.
    found = SyntheticSource("lookup").get_label(address)
    if not found:
        raise HTTPException(404, f"No label on record for {address}")
    return found
