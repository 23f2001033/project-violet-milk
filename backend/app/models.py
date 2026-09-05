"""
Project Violet Milk - canonical data model.

SINGLE SOURCE OF TRUTH. Every router, engine and service imports its shapes
from this file. No module may redefine an entity locally.

Frozen at the end of Phase 1 (SPEC section 04). Changing anything here means
telling all five developers, because the frontend mock fixtures are generated
to match these shapes exactly.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

ENGINE_VERSION = "risk-1.0"
DILUTION_VERSION = "haircut-1.0"


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class CaseStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class DataMode(str, Enum):
    SYNTHETIC = "synthetic"
    LIVE = "live"


class FileType(str, Enum):
    CSV = "csv"
    PDF = "pdf"
    TXT = "txt"


class NodeType(str, Enum):
    VICTIM = "victim"
    BANK_ACCOUNT = "bank_account"
    UPI_HANDLE = "upi_handle"
    EXCHANGE = "exchange"
    WALLET = "wallet"
    MIXER = "mixer"
    BRIDGE = "bridge"
    CONTRACT = "contract"
    UNKNOWN = "unknown"


class Chain(str, Enum):
    ETHEREUM = "ethereum"
    BANK_INR = "bank_inr"
    UPI = "upi"
    NONE = "none"


class LabelSource(str, Enum):
    CURATED = "curated"
    ETHERSCAN = "etherscan"
    NONE = "none"


class Confidence(str, Enum):
    """How strongly a claim is supported.

    This drives solid-vs-dashed edge rendering and the confirmed-vs-inferred
    split in the court dossier. It is the field that makes our intellectual
    honesty visible to a judge - never collapse these into one value.
    """
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class EvidenceType(str, Enum):
    CONFIRMED_ONCHAIN = "confirmed_onchain"
    CONFIRMED_BANK = "confirmed_bank"
    INFERRED_CORRELATION = "inferred_correlation"


class Asset(str, Enum):
    ETH = "ETH"
    USDT = "USDT"
    INR = "INR"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AuditAction(str, Enum):
    CASE_CREATED = "CASE_CREATED"
    CASE_UPDATED = "CASE_UPDATED"
    EVIDENCE_UPLOADED = "EVIDENCE_UPLOADED"
    TRACE_RUN = "TRACE_RUN"
    RISK_COMPUTED = "RISK_COMPUTED"
    DILUTION_COMPUTED = "DILUTION_COMPUTED"
    REPORT_GENERATED = "REPORT_GENERATED"
    MODE_SWITCHED = "MODE_SWITCHED"


# ---------------------------------------------------------------------------
# Case
# ---------------------------------------------------------------------------

class CaseCreate(BaseModel):
    fir_ref: str = Field(..., examples=["FIR-2026-XYZ"])
    ncrp_ref: str = Field(..., examples=["1930-NCRP-2026-98124"])
    victim_name: str = Field(..., description="Synthetic identity only.")
    victim_amount_inr: float
    incident_datetime: str = Field(..., description="ISO 8601 with offset.")
    seed_wallet: str | None = None
    seed_utr: str | None = None
    io_name: str = Field(..., examples=["IO_SHARMA"])
    notes: str = ""


class Case(CaseCreate):
    case_id: str = Field(..., examples=["CP-CYBER-2026-001"])
    status: CaseStatus = CaseStatus.ACTIVE
    data_mode: DataMode = DataMode.SYNTHETIC
    created_at: str
    updated_at: str


class CaseUpdate(BaseModel):
    notes: str | None = None
    status: CaseStatus | None = None
    seed_wallet: str | None = None
    data_mode: DataMode | None = None


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

class Evidence(BaseModel):
    evidence_id: str
    case_id: str
    filename: str
    file_type: FileType
    size_bytes: int
    sha256_client: str = Field(
        ..., description="Computed in the browser via Web Crypto BEFORE upload."
    )
    sha256_server: str = Field(
        ..., description="Recomputed on receipt. Must equal sha256_client."
    )
    hash_match: bool = Field(
        ..., description="False means the file mutated in transit - reject it."
    )
    is_synthetic: bool = True
    row_count: int | None = None
    column_mapping: dict[str, str] | None = Field(
        None, description="Resolved by the AI column mapper, or None if unmapped."
    )
    uploaded_at: str
    uploaded_by: str


# ---------------------------------------------------------------------------
# Graph primitives
# ---------------------------------------------------------------------------

class Node(BaseModel):
    node_id: str
    case_id: str
    node_type: NodeType
    label: str | None = None
    label_source: LabelSource = LabelSource.NONE
    label_confidence: Confidence = Confidence.UNKNOWN
    chain: Chain = Chain.NONE
    balance: float | None = None
    prior_balance: float = Field(
        0.0,
        description="Clean holdings before any traced funds arrived. "
                    "Denominator input for the dilution haircut.",
    )
    is_seed: bool = False
    first_seen: str | None = None
    last_seen: str | None = None


class Edge(BaseModel):
    edge_id: str
    case_id: str
    from_node: str
    to_node: str
    amount: float
    asset: Asset
    timestamp: str
    evidence_type: EvidenceType
    tx_hash: str | None = None
    utr: str | None = None
    block_number: int | None = None
    hop_depth: int = 0
    source_evidence_id: str | None = None


class Label(BaseModel):
    address: str
    label: str
    node_type: NodeType
    source: LabelSource
    confidence: Confidence
    reference: str | None = Field(
        None, description="Where the label came from, e.g. an OFAC SDN listing."
    )


# ---------------------------------------------------------------------------
# Trace + graph responses
# ---------------------------------------------------------------------------

class TraceRequest(BaseModel):
    seed: str
    max_depth: int = 3
    min_amount: float = 0.0
    max_edges_per_node: int = 20
    time_window_hours: int = 72
    data_mode: DataMode = DataMode.SYNTHETIC


class GraphStats(BaseModel):
    nodes: int
    edges: int
    max_depth_reached: int
    traced_at: str
    source: str = Field(..., description="DataSource.source_name()")
    truncated: bool = Field(
        False, description="True when traversal bounds clipped the graph."
    )


class TraceResult(BaseModel):
    case_id: str
    seed: str
    stats: GraphStats
    node_ids: list[str]
    edge_ids: list[str]


class CyNodeData(BaseModel):
    id: str
    label: str | None = None
    type: NodeType
    chain: Chain
    risk_score: int = 0
    risk_level: RiskLevel = RiskLevel.LOW
    illicit_ratio: float = 0.0
    balance: float | None = None
    is_seed: bool = False
    label_confidence: Confidence = Confidence.UNKNOWN


class CyEdgeData(BaseModel):
    id: str
    source: str
    target: str
    amount: float
    asset: Asset
    timestamp: str
    evidence_type: EvidenceType
    tx_hash: str | None = None
    block_number: int | None = None
    hop_depth: int = 0


class CyNode(BaseModel):
    data: CyNodeData


class CyEdge(BaseModel):
    data: CyEdgeData


class CyElements(BaseModel):
    nodes: list[CyNode]
    edges: list[CyEdge]


class GraphResponse(BaseModel):
    case_id: str
    data_mode: DataMode
    stats: GraphStats
    elements: CyElements


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------

class RiskIndicator(BaseModel):
    rule_id: str = Field(..., examples=["R1"])
    name: str
    points: int
    evidence: str = Field(
        ...,
        min_length=1,
        description="Concrete proof - a tx hash, a count, a time delta. "
                    "An indicator with no evidence must never be emitted.",
    )
    confidence: Confidence


class RiskAssessment(BaseModel):
    node_id: str
    case_id: str
    score: int = Field(..., ge=0, le=100)
    level: RiskLevel
    illicit_ratio: float = Field(..., ge=0.0, le=1.0)
    indicators: list[RiskIndicator]
    engine_version: str = ENGINE_VERSION
    computed_at: str


# ---------------------------------------------------------------------------
# Dilution
# ---------------------------------------------------------------------------

class DilutionStep(BaseModel):
    node_id: str
    prior_balance: float
    incoming_amount: float
    incoming_ratio: float
    dirty_received: float
    total_after: float
    illicit_ratio: float
    flagged: bool = Field(..., description="illicit_ratio >= 0.30")


class DilutionResult(BaseModel):
    case_id: str
    threshold: float = 0.30
    version: str = DILUTION_VERSION
    steps: list[DilutionStep]
    computed_at: str


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

class TimelineEvent(BaseModel):
    event_id: str
    case_id: str
    timestamp: str
    event_type: str
    description: str
    node_id: str | None = None
    edge_id: str | None = None
    delta_seconds_prev: int = 0
    source: Literal["bank", "onchain", "system"]


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

class AuditLog(BaseModel):
    audit_id: str
    case_id: str
    timestamp: str
    user_id: str
    action: AuditAction
    target: str
    target_hash: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Report + health
# ---------------------------------------------------------------------------

class ReportResponse(BaseModel):
    case_id: str
    filename: str
    sha256: str
    generated_at: str
    page_count: int
    download_url: str


class ComponentHealth(BaseModel):
    database: bool
    graph_engine: bool
    report_engine: bool
    llm_configured: bool
    etherscan_configured: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    data_mode: DataMode
    components: ComponentHealth
    version: str = "0.1.0"
