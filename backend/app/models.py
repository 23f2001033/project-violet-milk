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
    TRON = "tron"
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
    TRX = "TRX"
    USDT = "USDT"
    INR = "INR"
    # A token whose contract is NOT on the verified registry. On Tron anyone
    # can deploy a contract calling itself "USDT", so an unrecognised contract
    # is reported as an unverified token rather than as the coin it claims to
    # be - otherwise a scammer can poison an investigation with fake inflows.
    TOKEN = "TOKEN"


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
    EVIDENCE_ANCHORED = "EVIDENCE_ANCHORED"


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
    ingestion: dict[str, Any] | None = Field(
        None,
        description="How many transfers were parsed out of this file, how many "
                    "rows were skipped and why. A partial import must be "
                    "visible, not silent.",
    )


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
    ingested_edges: int = Field(
        0,
        description="Transfers merged in from uploaded evidence. Non-zero "
                    "means the graph is no longer the pristine bundled case, "
                    "so scores may differ from the reference figures.",
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
    model: Literal["haircut", "propagation"] = "haircut"
    caveat: str = ""
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
    prev_hash: str = ""
    entry_hash: str = Field(
        "", description="SHA-256 over this entry plus the previous entry_hash."
    )


class AuditVerification(BaseModel):
    """Result of re-walking the custody chain."""
    case_id: str
    entries: int
    intact: bool
    broken_at: str | None = Field(
        None, description="audit_id of the first entry whose link fails."
    )
    head_hash: str = ""


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
    anchor: AnchorRecord | None = None


class AnomalyFinding(BaseModel):
    node_id: str
    score: float = Field(..., description="Isolation Forest decision function; "
                                          "lower is more anomalous.")
    cluster: int = Field(..., description="DBSCAN label; -1 means unclustered.")
    explanation: str


class AnomalyResponse(BaseModel):
    """Secondary lead signal. NEVER a risk score.

    Deliberately a separate endpoint and a separate shape from RiskAssessment,
    so a consumer cannot mistake a model output for a statutory finding.
    """
    case_id: str
    version: str
    trained: bool
    reason: str = ""
    method: str = "IsolationForest + DBSCAN over behavioural graph features"
    advisory: str = (
        "Unsupervised lead generation only. These findings do not contribute "
        "to any risk score and carry no evidentiary weight. An entity may be "
        "anomalous for entirely lawful reasons - the complainant is usually "
        "an outlier because they moved the largest single amount."
    )
    findings: list[AnomalyFinding] = Field(default_factory=list)
    cluster_sizes: dict[str, int] = Field(default_factory=dict)


class STRResponse(BaseModel):
    """FIU-IND Suspicious Transaction Report - DRAFT.

    `filed` is permanently false and there is no endpoint that can set it.
    Filing an STR requires the organisation to be a registered Reporting
    Entity with FINnet credentials; there is no public API and no way for
    software to do it on the user's behalf.
    """
    case_id: str
    str_reference: str
    generated_at: str
    status: Literal["DRAFT"] = "DRAFT"
    filed: Literal[False] = False
    filing_instruction: str = (
        "This is a draft for review by an authorised Reporting Entity. It "
        "must be verified by the Principal Officer and submitted through the "
        "FIU-IND FINnet portal. This software cannot and does not file it."
    )
    filename: str
    sha256: str
    download_url: str
    fields: dict[str, Any]


class AnchorRecord(BaseModel):
    """On-chain existence proof for a digest.

    Deliberately explicit about its limits: an anchor proves a digest existed
    at or before a block and cannot be revised afterwards. It does not prove
    authorship, and it does not make a document tamper-proof - it makes
    substitution detectable.
    """
    digest: str
    anchored: bool
    tx_hash: str | None = None
    block_number: int | None = None
    block_time: int | None = None
    anchored_by: str | None = None
    explorer_url: str | None = None
    chain_id: int | None = None
    contract: str | None = None
    mode: str = "unavailable"
    source: str | None = None
    reason: str | None = None
    note: str | None = None
    proves: str = (
        "The digest existed at or before this block and the record cannot be "
        "revised. It does not establish who created the document."
    )


class LoginRequest(BaseModel):
    user_id: str
    password: str


class AuthUser(BaseModel):
    user_id: str
    display_name: str
    rank: str = ""


class LoginResponse(BaseModel):
    token: str
    expires_at: str
    user: AuthUser
    warning: str | None = Field(
        None,
        description="Set when this instance is still on the documented demo "
                    "password, so a default install cannot look secured.",
    )


class ComponentHealth(BaseModel):
    database: bool
    graph_engine: bool
    report_engine: bool
    llm_configured: bool
    etherscan_configured: bool
    anchoring_configured: bool = False
    auth_enabled: bool = True
    using_default_password: bool = False


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    data_mode: DataMode
    components: ComponentHealth
    version: str = "0.1.0"


# ---------------------------------------------------------------------------
# Asset ledger  ·  Phase 8 (additive)
#
# Which currency moved, at which layer of the trace, and what that is worth in
# rupees. An Indian investigating officer works in rupees and writes rupees
# into a chargesheet, but the chain reports native units - so every figure here
# carries its own conversion status rather than a silently assumed rate.
# ---------------------------------------------------------------------------

class AssetAmount(BaseModel):
    asset: Asset
    transfer_count: int
    total_amount: float = Field(..., description="Sum in the asset's own units")
    inr_equivalent: float | None = Field(
        None, description="None when no rate exists for this asset")
    inr_formatted: str | None = Field(
        None, description="Indian digit grouping, e.g. '4,70,000'")
    convertible: bool = Field(
        ..., description="False for assets with no rate in this build")


class LayerAssets(BaseModel):
    """One hop-depth band of the trace.

    `depth` is the hop distance of the receiving node, so a layer answers
    'what arrived here'. Layer 0 is the seed itself.
    """
    depth: int
    node_count: int
    transfer_count: int
    assets: list[AssetAmount]


class NodeAssets(BaseModel):
    node_id: str
    depth: int
    node_type: NodeType
    label: str | None = None
    received: list[AssetAmount] = []
    sent: list[AssetAmount] = []


class AssetBreakdown(BaseModel):
    case_id: str
    computed_at: str
    inr_per_usdt: float
    convertible_assets: list[Asset]
    caveat: str
    totals: list[AssetAmount]
    layers: list[LayerAssets]
    nodes: list[NodeAssets]


class NoticeResponse(BaseModel):
    """Section 94 BNSS 2023 production order - DRAFT.

    `signed` is permanently false and no endpoint can set it. A production
    order takes its force from the signature of an officer competent to issue
    it; software can assemble the recitals but cannot confer the authority,
    and a button claiming otherwise would be a lie about a legal instrument.
    """
    case_id: str
    notice_reference: str
    generated_at: str
    status: Literal["DRAFT"] = "DRAFT"
    signed: Literal[False] = False
    addressee_identified: bool
    issue_instruction: str = (
        "This is an unsigned draft. It must be reviewed with a legal advisor, "
        "completed by the issuing officer, and served under signature. This "
        "software does not issue or serve it."
    )
    filename: str
    sha256: str
    download_url: str
    fields: dict[str, Any]


# ---------------------------------------------------------------------------
# Conversion trail  ·  Phase 9 (additive)
#
# "Which platform did the money go to, and what did it become?" is the first
# question an officer asks after seeing the graph, and the graph alone does not
# answer it. These shapes name the points where value changed FORM (one
# currency into another) and the points where it changed HANDS (a service that
# holds customer records), which are the two things a production order has to
# recite.
# ---------------------------------------------------------------------------

class ConversionPoint(BaseModel):
    """An entity where the asset going in is not the asset coming out."""
    node_id: str
    label: str | None = None
    node_type: NodeType
    chain: Chain
    from_asset: Asset
    to_asset: Asset
    amount_in: float
    amount_out: float
    implied_rate: str | None = Field(
        None,
        description="Rate implied by the two legs, not a sourced market price",
    )
    at: str = Field(..., description="Timestamp of the outbound leg, IST")
    basis: Literal["CONFIRMED", "INFERRED"] = Field(
        ..., description="The weaker of the two legs, never the stronger",
    )


class VenueUse(BaseModel):
    """A service the money passed through, and whether it can be named."""
    node_id: str
    label: str | None = None
    kind: NodeType
    chain: Chain
    assets_handled: list[Asset]
    transfers: int
    identified: bool = Field(
        ..., description="False when no curated label backs the address",
    )
    can_be_compelled: bool = Field(
        ...,
        description="True for services that hold customer records - an "
                    "exchange or a bank. False for a mixer or a bridge, which "
                    "hold nothing to produce.",
    )
    note: str


class TerminalAddress(BaseModel):
    """An address where the traced money stops, and what to do about it.

    A Section 94 order compels a PERSON to produce records. Serving one on a
    smart contract or an unhosted wallet asks nobody for nothing, and burns an
    officer's week finding that out. So the three ways a trail can stop are
    reported separately, each with the route that actually applies.
    """
    node_id: str
    label: str | None = None
    node_type: NodeType
    chain: Chain
    amount_received: float
    assets: list[Asset]
    disposition: Literal["unhosted", "pass_through_contract", "bounds_reached"]
    serve_production_order: Literal[False] = Field(
        False,
        description="Always false. None of these is a person who can produce "
                    "records; that is what makes them terminal.",
    )
    recommended_action: str


class ConversionTrail(BaseModel):
    case_id: str
    computed_at: str
    rails_used: list[str] = Field(
        ..., description="Networks the value travelled on, in order of first use",
    )
    conversions: list[ConversionPoint]
    venues: list[VenueUse]
    terminal_addresses: list[TerminalAddress] = []
    caveat: str
