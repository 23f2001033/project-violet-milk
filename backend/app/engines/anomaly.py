"""
Flag Agent - unsupervised anomaly detection.  Owner: BE2

Isolation Forest (outliers) + DBSCAN (clusters) over behavioural graph
features. This is the ML layer the deck advertises, built honestly.

WHAT IT IS AND IS NOT
---------------------
It is a SECONDARY LEAD-GENERATION signal. It is not part of the risk score,
it cannot change a risk score, and nothing it produces enters the statutory
section of the dossier. The deterministic rules in `risk_engine` remain the
only thing that decides HIGH or CRITICAL.

That separation is the whole point. Section 63 BSA 2023 requires explaining
how an output was produced. We can explain "+15 because the outbound transfer
was 3 minutes after receipt". We cannot put an Isolation Forest in a witness
box. So the model is allowed to say "this wallet behaves unlike its peers -
look at it", and is not allowed to say "this wallet is high risk".

WHY UNSUPERVISED
----------------
XGBoost and friends are supervised: they need wallets labelled fraud /
not-fraud to train on. No such labelled set exists for this case, and
inventing one would mean the model simply rediscovers what we labelled.
Isolation Forest and DBSCAN need no labels - they describe the shape of the
data we actually have.

HONEST LIMITATION, to be volunteered before it is asked: on a small graph
this is descriptive statistics with a fashionable name. Its value grows with
the number of wallets; on 14 nodes it mostly confirms what the rules already
found. We say so rather than dressing it up.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..models import Edge, Node

ANOMALY_VERSION = "anomaly-1.0"
MIN_SAMPLES_FOR_MODEL = 8


@dataclass
class WalletFeatures:
    node_id: str
    in_count: int = 0
    out_count: int = 0
    in_value: float = 0.0
    out_value: float = 0.0
    distinct_counterparties: int = 0
    fastest_turnaround_s: float = -1.0
    pass_through_ratio: float = 0.0

    def vector(self) -> list[float]:
        return [
            float(self.in_count),
            float(self.out_count),
            self.in_value,
            self.out_value,
            float(self.distinct_counterparties),
            # -1 means "never forwarded"; keep it distinguishable from "instant"
            self.fastest_turnaround_s if self.fastest_turnaround_s >= 0 else 1e6,
            self.pass_through_ratio,
        ]

    @staticmethod
    def names() -> list[str]:
        return ["inbound count", "outbound count", "inbound value",
                "outbound value", "counterparties", "fastest turnaround",
                "pass-through ratio"]


@dataclass
class AnomalyResult:
    version: str = ANOMALY_VERSION
    trained: bool = False
    reason: str = ""
    outliers: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    clusters: dict[str, int] = field(default_factory=dict)
    cluster_sizes: dict[int, int] = field(default_factory=dict)
    explanations: dict[str, str] = field(default_factory=dict)


def extract_features(nodes: list[Node], edges: list[Edge]) -> list[WalletFeatures]:
    feats = {n.node_id: WalletFeatures(node_id=n.node_id) for n in nodes}
    partners: dict[str, set[str]] = {n.node_id: set() for n in nodes}
    first_in: dict[str, datetime] = {}
    first_out: dict[str, datetime] = {}

    for e in sorted(edges, key=lambda x: x.timestamp):
        ts = datetime.fromisoformat(e.timestamp)

        if e.to_node in feats:
            f = feats[e.to_node]
            f.in_count += 1
            f.in_value += e.amount
            partners[e.to_node].add(e.from_node)
            first_in.setdefault(e.to_node, ts)

        if e.from_node in feats:
            f = feats[e.from_node]
            f.out_count += 1
            f.out_value += e.amount
            partners[e.from_node].add(e.to_node)
            first_out.setdefault(e.from_node, ts)

    for nid, f in feats.items():
        f.distinct_counterparties = len(partners[nid])
        if nid in first_in and nid in first_out:
            delta = (first_out[nid] - first_in[nid]).total_seconds()
            f.fastest_turnaround_s = delta if delta >= 0 else -1.0
        f.pass_through_ratio = (
            min(f.out_value / f.in_value, 1.0) if f.in_value > 0 else 0.0
        )
    return list(feats.values())


def detect(nodes: list[Node], edges: list[Edge]) -> AnomalyResult:
    feats = extract_features(nodes, edges)

    if len(feats) < MIN_SAMPLES_FOR_MODEL:
        return AnomalyResult(
            trained=False,
            reason=(
                f"Only {len(feats)} entities in the traced set; unsupervised "
                f"detection needs at least {MIN_SAMPLES_FOR_MODEL} to describe "
                "a peer group. Skipped rather than reported on noise."
            ),
        )

    try:
        import numpy as np
        from sklearn.cluster import DBSCAN
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return AnomalyResult(
            trained=False,
            reason="scikit-learn is not installed; the deterministic risk "
                   "engine is unaffected.",
        )

    ids = [f.node_id for f in feats]
    X = np.array([f.vector() for f in feats], dtype=float)
    Xs = StandardScaler().fit_transform(X)

    # random_state is pinned: the same case must produce the same output every
    # time it is run, including on stage.
    forest = IsolationForest(
        n_estimators=200, contamination="auto", random_state=42
    ).fit(Xs)
    raw = forest.decision_function(Xs)      # lower = more anomalous
    flags = forest.predict(Xs)              # -1 = outlier

    labels = DBSCAN(eps=1.4, min_samples=2).fit_predict(Xs)

    result = AnomalyResult(trained=True, reason="")
    means = Xs.mean(axis=0)
    names = WalletFeatures.names()

    for i, nid in enumerate(ids):
        result.scores[nid] = round(float(raw[i]), 4)
        result.clusters[nid] = int(labels[i])
        if flags[i] == -1:
            result.outliers.append(nid)
            # Name the feature that most separates this wallet from its peers,
            # so the flag is inspectable rather than oracular.
            deviations = np.abs(Xs[i] - means)
            top = int(np.argmax(deviations))
            direction = "above" if Xs[i][top] > means[top] else "below"
            result.explanations[nid] = (
                f"{names[top]} is unusually {direction} the peer average "
                f"for this case ({X[i][top]:,.2f})"
            )

    for lab in labels:
        result.cluster_sizes[int(lab)] = result.cluster_sizes.get(int(lab), 0) + 1

    return result
