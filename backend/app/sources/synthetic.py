"""
SyntheticSource — bundled curated dataset.  Owner: BE1

Reads the demo CSVs. Always available, needs no network, and powers the entire
scripted demonstration. This is what makes the demo survive a dead venue wifi.

The live EtherscanSource (Phase 6) implements the same interface, so no engine
downstream knows or cares which one is active.
"""

import csv
import pathlib
from functools import lru_cache
from pathlib import Path

from ..config import DATA_DIR
from ..models import (
    Asset, Chain, Confidence, Edge, EvidenceType, Label, LabelSource, Node,
    NodeType,
)
from .base import DataSource

EDGES_CSV = DATA_DIR / "demo_case.csv"
NODES_CSV = DATA_DIR / "demo_nodes.csv"
CASES_DIR = DATA_DIR / "cases"


@lru_cache(maxsize=32)
def _read(path_str: str) -> tuple[dict, ...]:
    """Cached per PATH rather than globally.

    This was `maxsize=1` over two module-level files, which is why every case
    saw the same graph no matter which one was open. Keying on the path is
    what makes a per-case dataset possible at all.
    """
    with pathlib.Path(path_str).open(newline="", encoding="utf-8") as fh:
        return tuple(csv.DictReader(fh))


def _paths_for(case_id: str) -> tuple[Path, Path]:
    """A case's own CSVs when it has them, otherwise the bundled demo pair.

    CP-CYBER-2026-001 has no directory on purpose: it is the locked dataset
    whose figures the integrity tests assert, and it must keep reading exactly
    the files it always has.
    """
    d = CASES_DIR / case_id
    if (d / "nodes.csv").is_file() and (d / "edges.csv").is_file():
        return d / "nodes.csv", d / "edges.csv"
    return NODES_CSV, EDGES_CSV


def _raw_nodes(case_id: str = "") -> tuple[dict, ...]:
    return _read(str(_paths_for(case_id)[0]))


def _raw_edges(case_id: str = "") -> tuple[dict, ...]:
    return _read(str(_paths_for(case_id)[1]))


class SyntheticSource(DataSource):
    def __init__(self, case_id: str):
        self.case_id = case_id

    # ------------------------------------------------------------- interface

    def get_transactions(self, address: str, limit: int = 100) -> list[Edge]:
        addr = address.lower()
        hits = [
            r for r in _raw_edges(self.case_id)
            if r["from_node"].lower() == addr or r["to_node"].lower() == addr
        ]
        return [self._to_edge(r) for r in hits[:limit]]

    def get_balance(self, address: str) -> float:
        for r in _raw_nodes(self.case_id):
            if r["node_id"].lower() == address.lower():
                return float(r["balance"])
        return 0.0

    def get_label(self, address: str) -> Label | None:
        for r in _raw_nodes(self.case_id):
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
        return [self._to_edge(r) for r in _raw_edges(self.case_id)]

    def all_nodes(self) -> list[Node]:
        return [self._to_node(r) for r in _raw_nodes(self.case_id)]

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
