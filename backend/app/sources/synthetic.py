"""
SyntheticSource — bundled curated dataset.  Owner: BE1

Reads the demo CSVs. Always available, needs no network, and powers the entire
scripted demonstration. This is what makes the demo survive a dead venue wifi.

The live EtherscanSource (Phase 6) implements the same interface, so no engine
downstream knows or cares which one is active.
"""

import csv
from functools import lru_cache

from ..config import DATA_DIR
from ..models import (
    Asset, Chain, Confidence, Edge, EvidenceType, Label, LabelSource, Node,
    NodeType,
)
from .base import DataSource

EDGES_CSV = DATA_DIR / "demo_case.csv"
NODES_CSV = DATA_DIR / "demo_nodes.csv"


@lru_cache(maxsize=1)
def _raw_nodes() -> list[dict]:
    with NODES_CSV.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@lru_cache(maxsize=1)
def _raw_edges() -> list[dict]:
    with EDGES_CSV.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class SyntheticSource(DataSource):
    def __init__(self, case_id: str):
        self.case_id = case_id

    # ------------------------------------------------------------- interface

    def get_transactions(self, address: str, limit: int = 100) -> list[Edge]:
        addr = address.lower()
        hits = [
            r for r in _raw_edges()
            if r["from_node"].lower() == addr or r["to_node"].lower() == addr
        ]
        return [self._to_edge(r) for r in hits[:limit]]

    def get_balance(self, address: str) -> float:
        for r in _raw_nodes():
            if r["node_id"].lower() == address.lower():
                return float(r["balance"])
        return 0.0

    def get_label(self, address: str) -> Label | None:
        for r in _raw_nodes():
            if r["node_id"].lower() == address.lower() and r["label"]:
                return Label(
                    address=r["node_id"],
                    label=r["label"],
                    node_type=NodeType(r["node_type"]),
                    source=LabelSource(r["label_source"]),
                    confidence=Confidence(r["label_confidence"]),
                    reference="bundled synthetic dataset",
                )
        return None

    def source_name(self) -> str:
        return "SyntheticSource"

    def is_live(self) -> bool:
        return False

    # --------------------------------------------------- whole-case helpers

    def all_edges(self) -> list[Edge]:
        return [self._to_edge(r) for r in _raw_edges()]

    def all_nodes(self) -> list[Node]:
        return [self._to_node(r) for r in _raw_nodes()]

    # ---------------------------------------------------------- conversion

    def _to_edge(self, r: dict) -> Edge:
        return Edge(
            edge_id=r["edge_id"],
            case_id=self.case_id,
            from_node=r["from_node"],
            to_node=r["to_node"],
            amount=float(r["amount"]),
            asset=Asset(r["asset"]),
            timestamp=r["timestamp"],
            evidence_type=EvidenceType(r["evidence_type"]),
            tx_hash=r["tx_hash"] or None,
            utr=r["utr"] or None,
            block_number=int(r["block_number"]) if r["block_number"] else None,
        )

    def _to_node(self, r: dict) -> Node:
        return Node(
            node_id=r["node_id"],
            case_id=self.case_id,
            node_type=NodeType(r["node_type"]),
            label=r["label"] or None,
            label_source=LabelSource(r["label_source"]),
            label_confidence=Confidence(r["label_confidence"]),
            chain=Chain(r["chain"]),
            balance=float(r["balance"]),
            prior_balance=float(r["prior_balance"]),
            is_seed=r["is_seed"] == "true",
        )
