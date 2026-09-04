from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ProofType(StrEnum):
    MISSION_SCOPE = "MISSION_SCOPE"
    SOURCE_READ = "SOURCE_READ"
    SOURCE_COMPLETENESS = "SOURCE_COMPLETENESS"
    EVIDENCE_HASH = "EVIDENCE_HASH"
    INVENTORY_RECONCILIATION = "INVENTORY_RECONCILIATION"
    FACT_CLASSIFICATION = "FACT_CLASSIFICATION"
    CONTRARY_SEARCH = "CONTRARY_SEARCH"
    LAW_CHECK = "LAW_CHECK"
    AUTHORITY_TREATMENT = "AUTHORITY_TREATMENT"
    FORUM_POWER = "FORUM_POWER"
    DEADLINE_CHARACTERISATION = "DEADLINE_CHARACTERISATION"
    PRIVACY_CLASSIFICATION = "PRIVACY_CLASSIFICATION"
    PROMPT_INJECTION_SCAN = "PROMPT_INJECTION_SCAN"
    COUNCIL_REVIEW = "COUNCIL_REVIEW"
    APPROVAL = "APPROVAL"
    ACTION_EXECUTION = "ACTION_EXECUTION"
    ACTION_READBACK = "ACTION_READBACK"
    WRITE_READBACK = "WRITE_READBACK"
    RELEASE_DECISION = "RELEASE_DECISION"
    RESTORE_CANARY = "RESTORE_CANARY"
    COGNITIVE_BINDING = "COGNITIVE_BINDING"


class ProofState(StrEnum):
    FACT_NATIVE_VERIFIED = "FACT_NATIVE_VERIFIED"
    FACT_PLATFORM_VERIFIED = "FACT_PLATFORM_VERIFIED"
    FACT_CROSS_VERIFIED = "FACT_CROSS_VERIFIED"
    FACT_CORROBORATED = "FACT_CORROBORATED"
    ALLEGATION_USER = "ALLEGATION_USER"
    ALLEGATION_OTHER = "ALLEGATION_OTHER"
    INFERENCE_STRONG = "INFERENCE_STRONG"
    INFERENCE_TENTATIVE = "INFERENCE_TENTATIVE"
    DISPUTED = "DISPUTED"
    UNKNOWN = "UNKNOWN"
    UNVERIFIED_INCOMPLETE_SOURCE = "UNVERIFIED_INCOMPLETE_SOURCE"
    LEGAL_PROPOSITION_CURRENT = "LEGAL_PROPOSITION_CURRENT"
    LEGAL_PROPOSITION_UNVERIFIED = "LEGAL_PROPOSITION_UNVERIFIED"
    SUPERSEDED = "SUPERSEDED"


class ClaimKind(StrEnum):
    FACT = "FACT"
    LEGAL = "LEGAL"
    PROCEDURAL = "PROCEDURAL"
    DEADLINE = "DEADLINE"
    REMEDY = "REMEDY"
    CAUSATION = "CAUSATION"
    PRIVILEGE = "PRIVILEGE"
    COMPLETION = "COMPLETION"


class LinkType(StrEnum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    QUALIFIES = "QUALIFIES"
    AUTHORITY_SUPPORTS = "AUTHORITY_SUPPORTS"
    SATISFIES_ELEMENT = "SATISFIES_ELEMENT"


class ReleaseDecision(StrEnum):
    RELEASE = "RELEASE"
    RELEASE_WITH_BOUNDED_CAVEAT = "RELEASE_WITH_BOUNDED_CAVEAT"
    HOLD_FOR_EVIDENCE = "HOLD_FOR_EVIDENCE"
    HOLD_FOR_APPROVAL = "HOLD_FOR_APPROVAL"
    HOLD_FOR_COUNCIL = "HOLD_FOR_COUNCIL"
    REJECT_FALSE_CERTAINTY = "REJECT_FALSE_CERTAINTY"


class ExternalActionType(StrEnum):
    EMAIL_SEND = "EMAIL_SEND"
    FILE_SHARE = "FILE_SHARE"
    LEGAL_FILING = "LEGAL_FILING"
    SETTLEMENT_ACCEPTANCE = "SETTLEMENT_ACCEPTANCE"
    EVIDENCE_DELETE = "EVIDENCE_DELETE"
    CREDENTIAL_CHANGE = "CREDENTIAL_CHANGE"
    FINANCIAL_COMMITMENT = "FINANCIAL_COMMITMENT"
    PRODUCTION_DEPLOYMENT = "PRODUCTION_DEPLOYMENT"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXECUTING = "EXECUTING"
    EXECUTION_UNCERTAIN = "EXECUTION_UNCERTAIN"
    CONSUMED = "CONSUMED"


class WorkflowStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    DEAD_LETTER = "DEAD_LETTER"
    QUARANTINED = "QUARANTINED"


class CouncilRole(StrEnum):
    APPLICANT = "APPLICANT"
    RESPONDENT = "RESPONDENT"
    NEUTRAL_ADJUDICATOR = "NEUTRAL_ADJUDICATOR"
    EVIDENCE_EXAMINER = "EVIDENCE_EXAMINER"
    AUTHORITY_VERIFIER = "AUTHORITY_VERIFIER"
    PROCEDURAL_AUDITOR = "PROCEDURAL_AUDITOR"
    INSPECTOR_GENERAL = "INSPECTOR_GENERAL"


class ProofRecord(BaseModel):
    proof_id: str
    matter_id: str
    mission_id: str
    proof_type: ProofType
    subject_id: str
    actor_id: str
    source_ids: list[str] = Field(default_factory=list)
    payload: dict[str, Any]
    payload_hash: str
    chain_index: int
    previous_hash: str
    chain_hash: str
    signature: str
    created_at: datetime


class ProofAppendRequest(BaseModel):
    matter_id: str
    mission_id: str
    proof_type: ProofType
    subject_id: str
    actor_id: str
    source_ids: list[str] = Field(default_factory=list)
    payload: dict[str, Any]


class ChainVerificationResult(BaseModel):
    valid: bool
    matter_id: str
    checked_count: int
    head_hash: str | None = None
    failed_proof_id: str | None = None
    reason: str | None = None


class EvidenceObject(BaseModel):
    evidence_id: str
    matter_id: str
    sha256: str
    byte_size: int
    media_type: str
    original_name: str
    storage_path: str
    encrypted: bool
    parent_evidence_id: str | None = None
    nested_depth: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    tainted_untrusted_content: bool = False
    created_at: datetime


class EvidenceIngestRequest(BaseModel):
    matter_id: str
    mission_id: str
    path: str
    parent_evidence_id: str | None = None
    nested_depth: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimCreateRequest(BaseModel):
    matter_id: str
    mission_id: str
    kind: ClaimKind
    proposition: str = Field(min_length=3)
    proof_state: ProofState = ProofState.UNKNOWN
    materiality: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"


class ClaimRecord(BaseModel):
    claim_id: str
    matter_id: str
    mission_id: str
    kind: ClaimKind
    proposition: str
    proof_state: ProofState
    materiality: str
    status: str
    created_at: datetime


class ClaimLinkRequest(BaseModel):
    claim_id: str
    object_id: str
    object_type: Literal["EVIDENCE", "AUTHORITY", "CLAIM", "PROOF", "ELEMENT"]
    link_type: LinkType
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: str | None = None


class AuthorityRegisterRequest(BaseModel):
    matter_id: str
    mission_id: str
    citation: str
    title: str
    authority_type: Literal["STATUTE", "REGULATION", "RULE", "JUDGMENT", "POLICY", "DIRECTIVE"]
    jurisdiction: str = "South Africa"
    source_url: str
    proposition: str
    binding_level: Literal["BINDING", "PERSUASIVE", "INTERNAL"]
    effective_from: str | None = None
    effective_to: str | None = None
    content_hash: str
    superseded_by: str | None = None


class AuthorityRecord(BaseModel):
    authority_id: str
    matter_id: str
    citation: str
    title: str
    authority_type: str
    jurisdiction: str
    source_url: str
    source_domain: str
    proposition: str
    binding_level: str
    effective_from: str | None
    effective_to: str | None
    content_hash: str
    superseded_by: str | None
    created_at: datetime


class ReleaseRequirements(BaseModel):
    legal_analysis: bool = True
    current_law_required: bool = True
    forum_power_required: bool = True
    deadline_analysis_required: bool = False
    recursive_inventory_required: bool = False
    privacy_review_required: bool = True
    write_performed: bool = False
    external_action_id: str | None = None
    council_required: bool = True


class ReleaseRequest(BaseModel):
    matter_id: str
    mission_id: str
    risk_level: RiskLevel = RiskLevel.HIGH
    claim_ids: list[str] = Field(default_factory=list)
    proof_ids: list[str] = Field(default_factory=list)
    requirements: ReleaseRequirements = Field(default_factory=ReleaseRequirements)
    noncritical_unknowns: list[str] = Field(default_factory=list)


class ReleaseResult(BaseModel):
    decision: ReleaseDecision
    release_receipt_id: str | None = None
    verified_proof_ids: list[str] = Field(default_factory=list)
    failed_requirements: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    proof_chain_head: str | None = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovalCreateRequest(BaseModel):
    matter_id: str
    mission_id: str
    action_type: ExternalActionType
    exact_parameters: dict[str, Any]
    requested_by: str
    expires_at: datetime | None = None


class ApprovalRecord(BaseModel):
    approval_id: str
    matter_id: str
    mission_id: str
    action_type: ExternalActionType
    action_digest: str
    exact_parameters: dict[str, Any]
    status: ApprovalStatus
    requested_by: str
    decided_by: str | None = None
    decision_reason: str | None = None
    expires_at: datetime | None = None
    created_at: datetime
    decided_at: datetime | None = None


class ApprovalDecisionRequest(BaseModel):
    approve: bool
    decided_by: str
    reason: str


class ActionExecuteRequest(BaseModel):
    approval_id: str
    action_type: ExternalActionType
    exact_parameters: dict[str, Any]
    executor_id: str


class ActionReceipt(BaseModel):
    action_receipt_id: str
    approval_id: str
    matter_id: str
    mission_id: str
    action_type: ExternalActionType
    action_digest: str
    provider_action_id: str
    provider_status: str
    readback_status: str
    execution_proof_id: str
    readback_proof_id: str
    created_at: datetime


class WorkflowCreateRequest(BaseModel):
    matter_id: str
    mission_id: str
    workflow_type: str
    input_payload: dict[str, Any]
    max_attempts: int = Field(default=3, ge=1, le=20)


class WorkflowRecord(BaseModel):
    workflow_id: str
    matter_id: str
    mission_id: str
    workflow_type: str
    status: WorkflowStatus
    input_payload: dict[str, Any]
    state_payload: dict[str, Any]
    attempts: int
    max_attempts: int
    lease_owner: str | None
    lease_expires_at: datetime | None
    lease_generation: int = 0
    state_version: int = 0
    next_run_at: datetime
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class CouncilOpinion(BaseModel):
    opinion_id: str
    matter_id: str
    mission_id: str
    role: CouncilRole
    disposition: Literal["SUPPORT", "OPPOSE", "QUALIFY", "HOLD"]
    conclusion: str
    supported_claim_ids: list[str] = Field(default_factory=list)
    challenged_claim_ids: list[str] = Field(default_factory=list)
    proof_ids: list[str] = Field(default_factory=list)
    material_risks: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CouncilDecisionRequest(BaseModel):
    matter_id: str
    mission_id: str
    risk_level: RiskLevel
    opinions: list[CouncilOpinion]


class CouncilDecision(BaseModel):
    complete: bool
    disposition: Literal["SUPPORT", "OPPOSE", "QUALIFY", "HOLD"]
    missing_roles: list[CouncilRole] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    proof_ids: list[str] = Field(default_factory=list)
    summary: str


class MissionRequest(BaseModel):
    mission: str = Field(min_length=3)
    matter_id: str = "MAT-KIM-V-TUT"
    session_id: str
    jurisdiction: str = "South Africa"
    forum: str = "UNKNOWN"
    risk_level: RiskLevel = RiskLevel.HIGH
    source_paths: list[str] = Field(default_factory=list)
    requested_work_product: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MissionResponse(BaseModel):
    status: Literal["completed", "approval_required", "blocked", "error"]
    mission_id: str
    output: dict[str, Any] | None = None
    approval_ids: list[str] = Field(default_factory=list)
    trace_id: str | None = None
    reason: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    sdk_installed: bool
    api_key_present: bool
    database_ready: bool
    proof_ledger_ready: bool
    evidence_encryption_ready: bool
    authentication_ready: bool
    webhook_auth_configured: bool
    webhook_secret_resolver_kind: str
    webhook_secret_provider_proven: bool
    webhook_nonce_store_kind: Literal["sqlite", "redis", "injected"]
    webhook_replay_scope: Literal["node_local_sqlite", "shared_redis"]
    webhook_nonce_backend_configured: bool
    webhook_nonce_backend_proven: bool
    webhook_nonce_backend_status: Literal["unconfigured", "unproven", "ready", "unavailable"]
    external_actions_enabled: bool
    durable_workflow_ready: bool
    primary_model: str
    limitations: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InventoryItem(BaseModel):
    occurrence_id: str
    parent_id: str | None = None
    depth: int
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    disposition: str | None = None
    content_id: str | None = None
    top_level: bool = False
    inline: bool = False


class InventoryResult(BaseModel):
    carrier_path: str
    carrier_type: str
    top_level_count: int
    recursive_instance_count: int
    native_attachment_instance_count: int
    native_inline_instance_count: int
    application_visible_count: int | None = None
    application_attachment_count: int | None = None
    application_inline_count: int | None = None
    unique_content_count: int
    duplicate_instance_count: int
    items: list[InventoryItem]
    count_reconciliation: str
    completeness_state: Literal["VERIFIED", "VERIFIED_WITH_CATEGORY_DIFFERENCE", "UNVERIFIED"]
    limits_applied: dict[str, Any] = Field(default_factory=dict)


class AuthPrincipal(BaseModel):
    subject: str
    roles: list[str]
    matter_ids: list[str]
    scopes: list[str]


class CompletionClaim(BaseModel):
    external_action_taken: bool
    action_receipt_id: str | None = None

    @model_validator(mode="after")
    def action_requires_receipt(self) -> CompletionClaim:
        if self.external_action_taken and not self.action_receipt_id:
            raise ValueError("external_action_taken=true requires an action receipt")
        return self


class CouncilDraft(BaseModel):
    disposition: Literal["SUPPORT", "OPPOSE", "QUALIFY", "HOLD"]
    conclusion: str
    supported_claim_ids: list[str] = Field(default_factory=list)
    challenged_claim_ids: list[str] = Field(default_factory=list)
    proof_ids: list[str] = Field(default_factory=list)
    material_risks: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class ChiefSynthesis(BaseModel):
    conclusion: str
    verified_claim_ids: list[str] = Field(default_factory=list)
    disputed_claim_ids: list[str] = Field(default_factory=list)
    material_unknowns: list[str] = Field(default_factory=list)
    recommended_action: str
    approval_required: bool = False
    requested_release_requirements: ReleaseRequirements = Field(default_factory=ReleaseRequirements)


class InventoryRequest(BaseModel):
    matter_id: str
    mission_id: str
    subject_id: str
    path: str
    source_ids: list[str] = Field(default_factory=list)
    application_visible_count: int | None = None
    application_attachment_count: int | None = None
    application_inline_count: int | None = None


class WorkflowLeaseRequest(BaseModel):
    worker_id: str
    lease_seconds: int = Field(default=120, ge=30, le=3600)


class WorkflowStateRequest(BaseModel):
    worker_id: str
    lease_generation: int = Field(ge=1)
    state: dict[str, Any]


class WorkflowFailureRequest(BaseModel):
    worker_id: str
    lease_generation: int = Field(ge=1)
    error: str
    retry_delay_seconds: int = Field(default=60, ge=0, le=86400)


class BackupCreateRequest(BaseModel):
    matter_id: str
    mission_id: str
    destination: str


class RestoreCanaryRequest(BaseModel):
    matter_id: str
    mission_id: str
    snapshot_dir: str


class KnowledgeIngestRequest(BaseModel):
    authority_id: str
    matter_id: str
    mission_id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchRequest(BaseModel):
    matter_id: str
    query: str
    top_k: int = Field(default=8, ge=1, le=50)
