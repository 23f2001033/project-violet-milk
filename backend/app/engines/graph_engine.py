"""
Graph Engine — bounded traversal.  Owner: BE1

A real scam wallet at depth 5 touches millions of addresses. Unbounded
traversal freezes the browser and exhausts the API rate limit mid-demo, so
every bound below is load-bearing rather than decorative.

Traversal is UNDIRECTED. Money laundering evidence runs both ways from a seed:
downstream shows where funds went, upstream reconstructs the on-ramp (victim ->
bank -> exchange) that gives the case its context.
"""

from datetime import datetime, timedelta

import networkx as nx

from ..models import Edge, Node


def build_graph(nodes: list[Node], edges: list[Edge]) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for n in nodes:
        g.add_node(n.node_id, node=n)
    for e in edges:
        g.add_edge(e.from_node, e.to_node, key=e.edge_id, edge=e)
    return g


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def bounded_trace(
    nodes: list[Node],
    edges: list[Edge],
    seed: str,
    max_depth: int = 3,
    min_amount: float = 0.0,
    max_edges_per_node: int = 20,
    time_window_hours: int = 72,
    incident_at: str | None = None,
) -> tuple[list[Node], list[Edge], dict[str, int], bool]:
    """Breadth-first expansion from `seed` under all four bounds.

    Returns (kept_nodes, kept_edges, hop_depth_by_node, truncated).
    `truncated` is True when a bound actually clipped something - the UI must
    say so rather than implying the graph is complete.
    """
    by_id = {n.node_id.lower(): n for n in nodes}
    seed_key = seed.lower()
    if seed_key not in by_id:
        return [], [], {}, False

    truncated = False

    # --- filter the candidate edge set before traversing --------------------
    candidates: list[Edge] = []
    window_start = window_end = None
    if incident_at:
        anchor = _parse(incident_at)
        window_start = anchor - timedelta(hours=time_window_hours)
        window_end = anchor + timedelta(hours=time_window_hours)

    for e in edges:
        if e.amount < min_amount:
            truncated = True
            continue
        if window_start is not None:
            ts = _parse(e.timestamp)
            if not (window_start <= ts <= window_end):
                truncated = True
                continue
        candidates.append(e)

    # --- adjacency, undirected -------------------------------------------
    adj: dict[str, list[Edge]] = {}
    for e in candidates:
        adj.setdefault(e.from_node.lower(), []).append(e)
        adj.setdefault(e.to_node.lower(), []).append(e)

    # --- BFS --------------------------------------------------------------
    hop: dict[str, int] = {seed_key: 0}
    frontier = [seed_key]
    kept_edges: dict[str, Edge] = {}

    while frontier:
        nxt: list[str] = []
        for current in frontier:
            depth = hop[current]
            if depth >= max_depth:
                continue

            incident = adj.get(current, [])
            # Keep the largest flows first - that is where the money actually is.
            ranked = sorted(incident, key=lambda x: x.amount, reverse=True)
            if len(ranked) > max_edges_per_node:
                ranked = ranked[:max_edges_per_node]
                truncated = True

            for e in ranked:
                kept_edges[e.edge_id] = e
                other = (
                    e.to_node.lower()
                    if e.from_node.lower() == current
                    else e.from_node.lower()
                )
                if other not in hop:
                    hop[other] = depth + 1
                    nxt.append(other)
        frontier = nxt

    kept_nodes = [by_id[k] for k in hop if k in by_id]
    hop_by_node = {by_id[k].node_id: v for k, v in hop.items() if k in by_id}

    # Drop edges whose far endpoint was never reached within the depth bound.
    reached = set(hop)
    final_edges = [
        e for e in kept_edges.values()
        if e.from_node.lower() in reached and e.to_node.lower() in reached
    ]
    if len(final_edges) != len(kept_edges):
        truncated = True

    final_edges.sort(key=lambda e: e.timestamp)
    for e in final_edges:
        e.hop_depth = hop_by_node.get(e.to_node, 0)

    return kept_nodes, final_edges, hop_by_node, truncated
