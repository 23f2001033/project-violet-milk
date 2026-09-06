"""
Analysis pipeline — the one place the engines are composed.

Routers call `analyse()` and never orchestrate engines themselves, so trace,
graph, risk, dilution and timeline can never disagree about the same case.

Order matters: dilution must run before risk, because a node's illicit ratio is
an input to its assessment.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache

from ..models import (
    CyEdge, CyEdgeData, CyElements, CyNode, CyNodeData, DataMode,
    DilutionResult, Edge, GraphResponse, GraphStats, Node, NodeType,
    RiskAssessment, TimelineEvent,
)
from ..sources.base import DataSource
from ..sources.synthetic import SyntheticSource
from .anomaly import AnomalyResult, detect as detect_anomalies
from .dilution import compute_dilution
from .graph_engine import bounded_trace
from .risk_engine import assess
from .timeline import build_timeline


@dataclass
class CaseAnalysis:
    case_id: str
    seed: str
    source_name: str
    is_live: bool
    nodes: list[Node]
    edges: list[Edge]
    hop_depth: dict[str, int]
    truncated: bool
    ingested_count: int
    dilution: DilutionResult
    illicit_ratio: dict[str, float]
    risk: dict[str, RiskAssessment]
    timeline: list[TimelineEvent]
    traced_at: str
    # Secondary lead signal only. Deliberately NOT an input to `risk` - the
    # deterministic rules stay the sole basis for any score in the dossier.
    anomaly: AnomalyResult | None = None

    # ---------------------------------------------------------- projections

    def stats(self) -> GraphStats:
        return GraphStats(
            nodes=len(self.nodes),
            edges=len(self.edges),
            max_depth_reached=max(self.hop_depth.values(), default=0),
            traced_at=self.traced_at,
            source=self.source_name,
            truncated=self.truncated,
            ingested_edges=self.ingested_count,
        )

    def graph(self) -> GraphResponse:
        cy_nodes = [
            CyNode(data=CyNodeData(
                id=n.node_id,
                label=n.label,
                type=n.node_type,
                chain=n.chain,
                risk_score=self.risk[n.node_id].score,
                risk_level=self.risk[n.node_id].level,
                illicit_ratio=self.illicit_ratio.get(n.node_id, 0.0),
                balance=n.balance,
                is_seed=n.is_seed,
                label_confidence=n.label_confidence,
            ))
            for n in self.nodes
        ]
        cy_edges = [
            CyEdge(data=CyEdgeData(
                id=e.edge_id,
                source=e.from_node,
                target=e.to_node,
                amount=e.amount,
                asset=e.asset,
                timestamp=e.timestamp,
                evidence_type=e.evidence_type,
                tx_hash=e.tx_hash,
                block_number=e.block_number,
                hop_depth=e.hop_depth,
            ))
            for e in self.edges
        ]
        return GraphResponse(
            case_id=self.case_id,
            data_mode=DataMode.LIVE if self.is_live else DataMode.SYNTHETIC,
            stats=self.stats(),
            elements=CyElements(nodes=cy_nodes, edges=cy_edges),
        )


def _ingested(case_id: str, known: set[str]) -> tuple[list[Node], list[Edge]]:
    """Edges parsed from uploaded evidence, plus any nodes they introduce.

    Imported here rather than at module scope: `db` imports config, and a
    top-level import would make the engine package depend on storage.
    """
    from ..db import ingested_edges
    from ..models import Asset, Chain, EvidenceType, NodeType

    rows = ingested_edges(case_id)
    if not rows:
        return [], []

    edges = [
        Edge(
            edge_id=r["edge_id"], case_id=case_id,
            from_node=r["from_node"], to_node=r["to_node"],
            amount=r["amount"], asset=Asset(r["asset"]),
            timestamp=r["timestamp"],
            evidence_type=EvidenceType(r["evidence_type"]),
            utr=r["utr"], tx_hash=r["tx_hash"],
            source_evidence_id=r["evidence_id"],
        )
        for r in rows
    ]

    # Anything the upload introduced that the bundled dataset did not already
    # know about becomes an UNKNOWN node - never silently typed or labelled.
    fresh = {e.from_node for e in edges} | {e.to_node for e in edges}
    nodes = [
        Node(node_id=nid, case_id=case_id, node_type=NodeType.UNKNOWN,
             chain=Chain.ETHEREUM if nid.startswith("0x") else Chain.BANK_INR,
             prior_balance=0.0)
        for nid in sorted(fresh - known)
    ]
    return nodes, edges


def make_source(case_id: str, data_mode: str = "synthetic") -> DataSource:
    if str(data_mode).lower() == "live":
        from ..sources.etherscan import EtherscanSource
        return EtherscanSource(case_id)
    return SyntheticSource(case_id)


def analyse(
    case_id: str,
    seed: str,
    source: DataSource | None = None,
    max_depth: int = 3,
    min_amount: float = 0.0,
    max_edges_per_node: int = 20,
    time_window_hours: int = 72,
    incident_at: str | None = None,
    data_mode: str = "synthetic",
) -> CaseAnalysis:
    src = source or make_source(case_id, data_mode)

    if hasattr(src, "all_nodes"):
        # Bundled dataset: the whole case is already in memory.
        all_nodes = src.all_nodes()
        all_edges = src.all_edges()
        # Transfers parsed from evidence the officer uploaded are merged in, so
        # an ingested file genuinely appears in the graph.
        ing_nodes, ing_edges = _ingested(case_id, {n.node_id for n in all_nodes})
        all_nodes += ing_nodes
        all_edges += ing_edges
        ingested_count = len(ing_edges)
    else:
        # Live source: it must walk the chain itself, because discovering the
        # neighbourhood costs API calls and only the source knows how to pace
        # them. It returns an already-bounded neighbourhood; the engines then
        # apply the case's own bounds on top.
        ingested_count = 0
        all_nodes, all_edges = src.expand(
            seed, max_depth=max_depth, max_edges_per_node=max_edges_per_node
        )
        # A live trace has no incident anchor and no curated prior balances, so
        # the time window would discard everything. Widen it deliberately
        # rather than silently returning an empty graph.
        incident_at = None

    nodes, edges, hop, truncated = bounded_trace(
        all_nodes, all_edges, seed,
        max_depth=max_depth,
        min_amount=min_amount,
        max_edges_per_node=max_edges_per_node,
        time_window_hours=time_window_hours,
        incident_at=incident_at,
    )

    # Dilution BEFORE risk - the ratio is an input to the assessment.
    # A live source has no curated prior balances and no victim node, so it
    # runs in propagation mode with the seed as the taint origin. Without this
    # split, live traces reported 0.0 for every node.
    dilution, ratios = compute_dilution(
        case_id, nodes, edges,
        prior_balances_available=not src.is_live(),
    )

    victim_debit = next(
        (e.timestamp for e in sorted(edges, key=lambda x: x.timestamp)
         if e.evidence_type.value == "confirmed_bank"),
        None,
    )

    risk = {
        n.node_id: assess(
            case_id, n, nodes, edges, hop, ratios, victim_debit_at=victim_debit
        )
        for n in nodes
    }

    return CaseAnalysis(
        case_id=case_id,
        seed=seed,
        source_name=src.source_name(),
        is_live=src.is_live(),
        nodes=nodes,
        edges=edges,
        hop_depth=hop,
        truncated=truncated,
        ingested_count=ingested_count,
        dilution=dilution,
        illicit_ratio=ratios,
        risk=risk,
        timeline=build_timeline(case_id, nodes, edges),
        traced_at=datetime.now(timezone.utc).isoformat(),
        # Runs AFTER risk, and its result is never fed back in.
        anomaly=detect_anomalies(nodes, edges),
    )


@lru_cache(maxsize=16)
def _cached(case_id: str, seed: str, depth: int, min_amount: float,
            per_node: int, window: int, data_mode: str) -> CaseAnalysis:
    return analyse(
        case_id, seed, max_depth=depth, min_amount=min_amount,
        max_edges_per_node=per_node, time_window_hours=window,
        data_mode=data_mode,
    )


def get_analysis(
    case_id: str, seed: str, max_depth: int = 3, min_amount: float = 0.0,
    max_edges_per_node: int = 20, time_window_hours: int = 72,
    data_mode: str = "synthetic",
) -> CaseAnalysis:
    """Cached entry point. Traces are pure functions of their bounds, so
    repeating one within a demo costs nothing - and on stage it means a live
    trace is fetched once and then replays instantly."""
    return _cached(case_id, seed.lower(), max_depth, min_amount,
                   max_edges_per_node, time_window_hours, data_mode)


def clear_cache() -> None:
    _cached.cache_clear()
