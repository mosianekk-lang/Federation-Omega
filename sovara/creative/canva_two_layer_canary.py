"""Pure, fail-closed contracts for one SOVARA Canva saved-design canary.

The module never calls Canva.  It keeps candidate-neutral invariants separate
from selection-bound provider effects and validates externally supplied receipt
bindings without treating test fixtures as provider proof.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OWNER = "OWNER"
_PROVIDER = "CANVA"
_SCHEMA = "SOVARA_CANVA_TWO_LAYER_CANARY_CONTRACT_V1"
_CANDIDATE_SPECIFIC_KEYS = {
    "candidate_id",
    "candidate_ids",
    "selected_candidate",
    "selected_candidate_id",
    "job_id",
}
_REQUIRED_READBACKS = {
    "CREATE_REQUEST_BINDING",
    "DESIGN_METADATA",
    "DRAFT_TRANSACTION",
    "OWNER_PREVIEW",
    "COMMIT_RESULT",
    "POST_COMMIT_DESIGN_METADATA",
}
_REQUIRED_CONNECTOR_TOOLS: dict[str, tuple[str, tuple[str, ...]]] = {
    "cancel_editing_transaction": ("DRAFT_WRITE_CANCEL", ("transaction_id",)),
    "commit_editing_transaction": (
        "PROVIDER_WRITE_COMMIT",
        ("transaction_id", "explicit_user_approval_after_preview"),
    ),
    "create_design_from_candidate": ("PROVIDER_WRITE_CREATE", ("job_id", "candidate_id")),
    "get_design": ("READ_ONLY", ("design_id",)),
    "get_design_pages": ("READ_ONLY", ("design_id",)),
    "get_design_thumbnail": ("READ_ONLY", ("design_id",)),
    "perform_editing_operations": ("DRAFT_WRITE", ("transaction_id", "operations")),
    "start_editing_transaction": ("DRAFT_WRITE_START", ("design_id",)),
}
_CREATE_ROLLBACK_TOOLS = {"delete_design", "archive_design"}
_OPTIONAL_CONNECTOR_TOOLS: dict[str, tuple[str, tuple[str, ...]]] = {
    "delete_design": ("PROVIDER_WRITE_DELETE", ("design_id",)),
    "archive_design": ("PROVIDER_WRITE_ARCHIVE", ("design_id",)),
}
_REQUIRED_SEMANTIC_INVARIANTS = (
    "candidate conversion creates one new editable design",
    "editing operations remain draft-only until commit",
    "commit requires explicit user approval immediately after preview disclosure",
    "cancel discards the editing transaction draft",
    "no callable export download share publish or created-design delete capability is assumed",
)
_PROVENANCE_SURFACE = "codex-apps:canva"
_SAFE_CREDENTIAL_REFERENCE = re.compile(r"^connector:[a-z0-9_-]+:[a-z0-9_-]+$")


class CanvaCanaryState(str, Enum):
    HOLD_SCHEMA_FRESHNESS = "HOLD_SCHEMA_FRESHNESS"
    HOLD_OWNER_SELECTION = "HOLD_OWNER_SELECTION"
    HOLD_SELECTION_RECEIPT = "HOLD_SELECTION_RECEIPT"
    HOLD_CREATE_AUTHORITY = "HOLD_CREATE_AUTHORITY"
    HOLD_CREATE_ROLLBACK = "HOLD_CREATE_ROLLBACK"
    READY_FOR_CANDIDATE_CONVERSION = "READY_FOR_CANDIDATE_CONVERSION"
    HOLD_CREATE_READBACK = "HOLD_CREATE_READBACK"
    HOLD_DRAFT_AUTHORITY = "HOLD_DRAFT_AUTHORITY"
    HOLD_DRAFT_ROLLBACK = "HOLD_DRAFT_ROLLBACK"
    READY_FOR_DRAFT_EDIT = "READY_FOR_DRAFT_EDIT"
    HOLD_DRAFT_PREVIEW = "HOLD_DRAFT_PREVIEW"
    HOLD_COMMIT_APPROVAL = "HOLD_COMMIT_APPROVAL"
    READY_FOR_COMMIT = "READY_FOR_COMMIT"
    HOLD_COMMIT_READBACK = "HOLD_COMMIT_READBACK"
    SAVED_DESIGN_RECEIPT_VALIDATED = "SAVED_DESIGN_RECEIPT_VALIDATED"


@dataclass(frozen=True, slots=True)
class CanvaInvariantContract:
    schema: str
    invariant_id: str
    candidate_set_id: str
    candidate_roster_sha256: str
    expected_candidate_count: int
    owner_selection_required: bool
    age_state_required: str
    consent_state_required: str
    rights_state_required: str
    asset_origin_state_required: str
    raw_sensitive_payload_allowed: bool
    connector_schema_snapshot_id: str
    connector_schema_sha256: str
    connector_schema_provenance_sha256: str
    connector_schema_authenticated: bool
    connector_tools: tuple[str, ...]
    schema_checked_at: str
    schema_expires_at: str
    max_designs: int
    max_draft_operations: int
    create_effect_authorized: bool
    draft_effect_authorized: bool
    commit_effect_authorized: bool
    export_allowed: bool
    download_allowed: bool
    share_allowed: bool
    publish_allowed: bool
    required_readbacks: tuple[str, ...]
    rollback_requirements: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_bool_fields(
            self,
            "owner_selection_required",
            "connector_schema_authenticated",
            "raw_sensitive_payload_allowed",
            "create_effect_authorized",
            "draft_effect_authorized",
            "commit_effect_authorized",
            "export_allowed",
            "download_allowed",
            "share_allowed",
            "publish_allowed",
        )
        if self.schema != _SCHEMA:
            raise ValueError(f"schema must be {_SCHEMA}")
        _require_text(self.invariant_id, "invariant_id")
        _require_text(self.candidate_set_id, "candidate_set_id")
        _require_sha256(self.candidate_roster_sha256, "candidate_roster_sha256")
        _require_int(self.expected_candidate_count, "expected_candidate_count")
        if not 2 <= self.expected_candidate_count <= 12:
            raise ValueError("expected_candidate_count must be in [2, 12]")
        if not self.owner_selection_required:
            raise ValueError("owner_selection_required must be true")
        required_states = {
            "age_state_required": (self.age_state_required, "VERIFIED_ADULT_OR_SYNTHETIC"),
            "consent_state_required": (self.consent_state_required, "AFFIRMATIVE_OR_NOT_APPLICABLE"),
            "rights_state_required": (self.rights_state_required, "VERIFIED"),
            "asset_origin_state_required": (self.asset_origin_state_required, "VERIFIED"),
        }
        invalid_states = sorted(
            name for name, (actual, expected) in required_states.items() if actual != expected
        )
        if invalid_states:
            raise ValueError(f"unsafe eligibility state requirements: {invalid_states}")
        if self.raw_sensitive_payload_allowed:
            raise ValueError("candidate-neutral invariant cannot carry raw sensitive payloads")
        _require_text(self.connector_schema_snapshot_id, "connector_schema_snapshot_id")
        _require_sha256(self.connector_schema_sha256, "connector_schema_sha256")
        _require_sha256(
            self.connector_schema_provenance_sha256, "connector_schema_provenance_sha256"
        )
        if not self.connector_schema_authenticated:
            raise ValueError("connector schema requires an authenticated provenance attestation")
        if not self.connector_tools or len(set(self.connector_tools)) != len(self.connector_tools):
            raise ValueError("connector_tools must be non-empty and unique")
        missing_tools = sorted(set(_REQUIRED_CONNECTOR_TOOLS) - set(self.connector_tools))
        unknown_tools = sorted(
            set(self.connector_tools) - set(_REQUIRED_CONNECTOR_TOOLS) - _CREATE_ROLLBACK_TOOLS
        )
        if missing_tools or unknown_tools:
            raise ValueError(
                f"connector_tools mismatch; missing={missing_tools}, unknown={unknown_tools}"
            )
        checked = _parse_timestamp(self.schema_checked_at, "schema_checked_at")
        expires = _parse_timestamp(self.schema_expires_at, "schema_expires_at")
        if expires <= checked:
            raise ValueError("schema_expires_at must be later than schema_checked_at")
        _require_int(self.max_designs, "max_designs")
        if self.max_designs != 1:
            raise ValueError("max_designs must be exactly one")
        _require_int(self.max_draft_operations, "max_draft_operations")
        if not 1 <= self.max_draft_operations <= 50:
            raise ValueError("max_draft_operations must be in [1, 50]")
        source_effects = {
            "create_effect_authorized": self.create_effect_authorized,
            "draft_effect_authorized": self.draft_effect_authorized,
            "commit_effect_authorized": self.commit_effect_authorized,
            "export_allowed": self.export_allowed,
            "download_allowed": self.download_allowed,
            "share_allowed": self.share_allowed,
            "publish_allowed": self.publish_allowed,
        }
        enabled = sorted(name for name, value in source_effects.items() if value)
        if enabled:
            raise ValueError(f"source invariant cannot authorize effects: {enabled}")
        readbacks = {item.strip() for item in self.required_readbacks if item.strip()}
        missing = sorted(_REQUIRED_READBACKS - readbacks)
        if missing:
            raise ValueError(f"required_readbacks missing: {missing}")
        if len(readbacks) != len(self.required_readbacks):
            raise ValueError("required_readbacks must be non-empty and unique")
        rollback = {item.strip() for item in self.rollback_requirements if item.strip()}
        if not {"CREATE_ROLLBACK", "DRAFT_CANCEL"}.issubset(rollback):
            raise ValueError("CREATE_ROLLBACK and DRAFT_CANCEL are required")

    def schema_is_current(self, at: datetime) -> bool:
        point = _as_utc(at)
        return (
            _parse_timestamp(self.schema_checked_at, "schema_checked_at")
            <= point
            < _parse_timestamp(self.schema_expires_at, "schema_expires_at")
        )


@dataclass(frozen=True, slots=True)
class CanvaEligibilityEvidence:
    evidence_sha256: str
    candidate_set_id: str
    candidate_roster_sha256: str
    candidate_id: str
    age_state: str
    consent_state: str
    rights_state: str
    asset_origin_state: str
    privacy_eligible: bool
    candidate_membership_verified: bool
    trusted_surface_verified: bool
    attestation_sha256: str
    issued_at: str
    expires_at: str

    def __post_init__(self) -> None:
        _require_bool_fields(
            self,
            "privacy_eligible",
            "candidate_membership_verified",
            "trusted_surface_verified",
        )
        for name in ("candidate_set_id", "candidate_id"):
            _require_text(getattr(self, name), name)
        for name in (
            "evidence_sha256",
            "candidate_roster_sha256",
            "attestation_sha256",
        ):
            _require_sha256(getattr(self, name), name)
        _validate_receipt_window(self.issued_at, self.expires_at)

    def is_current(self, at: datetime) -> bool:
        return _receipt_is_current(self.issued_at, self.expires_at, at)


@dataclass(frozen=True, slots=True)
class CanvaOwnerSelectionReceipt:
    selection_id: str
    invariant_id: str
    connector_schema_sha256: str
    candidate_set_id: str
    candidate_roster_sha256: str
    candidate_id: str
    job_id: str
    brand_controls_sha256: str
    eligibility_evidence_sha256: str
    selected_by: str
    owner_authored: bool
    trusted_surface_verified: bool
    explicit_not_inferred: bool
    issued_at: str
    expires_at: str
    single_use: bool
    consumed: bool = False

    def __post_init__(self) -> None:
        _require_bool_fields(
            self,
            "owner_authored",
            "trusted_surface_verified",
            "explicit_not_inferred",
            "single_use",
            "consumed",
        )
        for name in (
            "selection_id",
            "invariant_id",
            "candidate_set_id",
            "candidate_id",
            "job_id",
        ):
            _require_text(getattr(self, name), name)
        for name in (
            "connector_schema_sha256",
            "candidate_roster_sha256",
            "brand_controls_sha256",
            "eligibility_evidence_sha256",
        ):
            _require_sha256(getattr(self, name), name)
        _validate_receipt_window(self.issued_at, self.expires_at)

    def is_current(self, at: datetime) -> bool:
        return _receipt_is_current(self.issued_at, self.expires_at, at)


@dataclass(frozen=True, slots=True)
class CanvaCreateAuthority:
    authority_id: str
    selection_id: str
    invariant_id: str
    provider_name: str
    connector_schema_sha256: str
    brand_controls_sha256: str
    candidate_id: str
    job_id: str
    eligibility_evidence_sha256: str
    exact_request_sha256: str
    expected_owner_fingerprint_sha256: str
    expected_title_sha256: str
    runtime_identity: str
    credential_reference: str
    privacy_eligible: bool
    create_effect_authorized: bool
    max_creations: int
    maximum_cost_microunits: int
    create_rollback_supported: bool
    create_rollback_tool: str
    create_rollback_proof_sha256: str
    issued_at: str
    expires_at: str
    single_use: bool
    consumed: bool = False

    def __post_init__(self) -> None:
        _require_bool_fields(
            self,
            "privacy_eligible",
            "create_effect_authorized",
            "create_rollback_supported",
            "single_use",
            "consumed",
        )
        for name in (
            "authority_id",
            "selection_id",
            "invariant_id",
            "provider_name",
            "candidate_id",
            "job_id",
            "runtime_identity",
            "credential_reference",
        ):
            _require_text(getattr(self, name), name)
        for name in (
            "connector_schema_sha256",
            "brand_controls_sha256",
            "eligibility_evidence_sha256",
            "exact_request_sha256",
            "expected_owner_fingerprint_sha256",
            "expected_title_sha256",
            "create_rollback_proof_sha256",
        ):
            _require_sha256(getattr(self, name), name)
        _require_credential_reference(self.credential_reference)
        _require_int(self.max_creations, "max_creations")
        if self.max_creations != 1:
            raise ValueError("max_creations must be exactly one")
        _require_int(self.maximum_cost_microunits, "maximum_cost_microunits")
        if self.maximum_cost_microunits != 0:
            raise ValueError("source-only Canva canary requires an exact zero-cost ceiling")
        _require_text(self.create_rollback_tool, "create_rollback_tool")
        _validate_receipt_window(self.issued_at, self.expires_at)

    def is_current(self, at: datetime) -> bool:
        return _receipt_is_current(self.issued_at, self.expires_at, at)


@dataclass(frozen=True, slots=True)
class CanvaCreateReadback:
    authority_id: str
    selection_id: str
    exact_request_sha256: str
    job_id: str
    candidate_id: str
    connector_schema_sha256: str
    brand_controls_sha256: str
    eligibility_evidence_sha256: str
    runtime_identity: str
    credential_reference: str
    design_id: str
    owner_fingerprint_sha256: str
    title_sha256: str
    page_count: int
    observed_cost_microunits: int
    created_at: str
    updated_at: str
    provider_native_readback: bool
    authority_consumed: bool
    proof_ref: str
    export_performed: bool = False
    download_performed: bool = False
    share_performed: bool = False
    publish_performed: bool = False

    def __post_init__(self) -> None:
        _require_bool_fields(
            self,
            "provider_native_readback",
            "authority_consumed",
            "export_performed",
            "download_performed",
            "share_performed",
            "publish_performed",
        )
        for name in (
            "authority_id",
            "selection_id",
            "job_id",
            "candidate_id",
            "runtime_identity",
            "credential_reference",
            "design_id",
            "proof_ref",
        ):
            _require_text(getattr(self, name), name)
        for name in (
            "exact_request_sha256",
            "connector_schema_sha256",
            "brand_controls_sha256",
            "eligibility_evidence_sha256",
            "owner_fingerprint_sha256",
            "title_sha256",
        ):
            _require_sha256(getattr(self, name), name)
        _require_int(self.page_count, "page_count")
        if self.page_count < 1:
            raise ValueError("page_count must be positive")
        _require_int(self.observed_cost_microunits, "observed_cost_microunits")
        if self.observed_cost_microunits != 0:
            raise ValueError("create readback exceeds the exact zero-cost ceiling")
        _require_credential_reference(self.credential_reference)
        created = _parse_timestamp(self.created_at, "created_at")
        updated = _parse_timestamp(self.updated_at, "updated_at")
        if updated < created:
            raise ValueError("updated_at cannot precede created_at")


@dataclass(frozen=True, slots=True)
class CanvaDraftAuthority:
    authority_id: str
    create_authority_id: str
    selection_id: str
    design_id: str
    candidate_id: str
    job_id: str
    connector_schema_sha256: str
    brand_controls_sha256: str
    eligibility_evidence_sha256: str
    operations_sha256: str
    runtime_identity: str
    credential_reference: str
    draft_effect_authorized: bool
    max_operations: int
    maximum_cost_microunits: int
    cancel_draft_supported: bool
    cancel_draft_proof_sha256: str
    issued_at: str
    expires_at: str
    single_use: bool
    consumed: bool = False

    def __post_init__(self) -> None:
        _require_bool_fields(
            self,
            "draft_effect_authorized",
            "cancel_draft_supported",
            "single_use",
            "consumed",
        )
        for name in (
            "authority_id",
            "create_authority_id",
            "selection_id",
            "design_id",
            "candidate_id",
            "job_id",
            "runtime_identity",
            "credential_reference",
        ):
            _require_text(getattr(self, name), name)
        for name in (
            "connector_schema_sha256",
            "brand_controls_sha256",
            "eligibility_evidence_sha256",
            "operations_sha256",
            "cancel_draft_proof_sha256",
        ):
            _require_sha256(getattr(self, name), name)
        _require_int(self.max_operations, "max_operations")
        if self.max_operations < 1:
            raise ValueError("max_operations must be positive")
        _require_int(self.maximum_cost_microunits, "maximum_cost_microunits")
        if self.maximum_cost_microunits != 0:
            raise ValueError("draft authority requires an exact zero-cost ceiling")
        _require_credential_reference(self.credential_reference)
        _validate_receipt_window(self.issued_at, self.expires_at)

    def is_current(self, at: datetime) -> bool:
        return _receipt_is_current(self.issued_at, self.expires_at, at)


@dataclass(frozen=True, slots=True)
class CanvaDraftObservation:
    draft_authority_id: str
    selection_id: str
    design_id: str
    candidate_id: str
    job_id: str
    connector_schema_sha256: str
    brand_controls_sha256: str
    eligibility_evidence_sha256: str
    runtime_identity: str
    credential_reference: str
    transaction_id: str
    operations_sha256: str
    operations_applied_count: int
    observed_cost_microunits: int
    draft_only: bool
    provider_native_readback: bool
    authority_consumed: bool
    preview_ref: str
    preview_sha256: str
    previewed_at: str
    proof_ref: str
    committed: bool = False
    export_performed: bool = False
    download_performed: bool = False
    share_performed: bool = False
    publish_performed: bool = False

    def __post_init__(self) -> None:
        _require_bool_fields(
            self,
            "draft_only",
            "provider_native_readback",
            "authority_consumed",
            "committed",
            "export_performed",
            "download_performed",
            "share_performed",
            "publish_performed",
        )
        for name in (
            "draft_authority_id",
            "selection_id",
            "design_id",
            "candidate_id",
            "job_id",
            "runtime_identity",
            "credential_reference",
            "transaction_id",
            "preview_ref",
            "proof_ref",
        ):
            _require_text(getattr(self, name), name)
        for name in (
            "connector_schema_sha256",
            "brand_controls_sha256",
            "eligibility_evidence_sha256",
            "operations_sha256",
            "preview_sha256",
        ):
            _require_sha256(getattr(self, name), name)
        _require_credential_reference(self.credential_reference)
        _require_int(self.operations_applied_count, "operations_applied_count")
        if self.operations_applied_count < 1:
            raise ValueError("operations_applied_count must be positive")
        _require_int(self.observed_cost_microunits, "observed_cost_microunits")
        if self.observed_cost_microunits != 0:
            raise ValueError("draft observation exceeds the exact zero-cost ceiling")
        _parse_timestamp(self.previewed_at, "previewed_at")


@dataclass(frozen=True, slots=True)
class CanvaCommitApproval:
    approval_id: str
    selection_id: str
    design_id: str
    transaction_id: str
    connector_schema_sha256: str
    brand_controls_sha256: str
    eligibility_evidence_sha256: str
    runtime_identity: str
    credential_reference: str
    operations_sha256: str
    preview_sha256: str
    expected_post_commit_design_sha256: str
    approved_by: str
    owner_authored: bool
    trusted_surface_verified: bool
    explicit_after_preview: bool
    commit_effect_authorized: bool
    maximum_cost_microunits: int
    issued_at: str
    expires_at: str
    single_use: bool
    consumed: bool = False

    def __post_init__(self) -> None:
        _require_bool_fields(
            self,
            "owner_authored",
            "trusted_surface_verified",
            "explicit_after_preview",
            "commit_effect_authorized",
            "single_use",
            "consumed",
        )
        for name in (
            "approval_id",
            "selection_id",
            "design_id",
            "transaction_id",
            "runtime_identity",
            "credential_reference",
        ):
            _require_text(getattr(self, name), name)
        for name in (
            "connector_schema_sha256",
            "brand_controls_sha256",
            "eligibility_evidence_sha256",
            "operations_sha256",
            "preview_sha256",
            "expected_post_commit_design_sha256",
        ):
            _require_sha256(getattr(self, name), name)
        _require_credential_reference(self.credential_reference)
        _require_int(self.maximum_cost_microunits, "maximum_cost_microunits")
        if self.maximum_cost_microunits != 0:
            raise ValueError("commit approval requires an exact zero-cost ceiling")
        _validate_receipt_window(self.issued_at, self.expires_at)

    def is_current(self, at: datetime) -> bool:
        return _receipt_is_current(self.issued_at, self.expires_at, at)


@dataclass(frozen=True, slots=True)
class CanvaCommitReadback:
    approval_id: str
    design_id: str
    transaction_id: str
    selection_id: str
    connector_schema_sha256: str
    brand_controls_sha256: str
    eligibility_evidence_sha256: str
    runtime_identity: str
    credential_reference: str
    operations_sha256: str
    committed: bool
    approval_consumed: bool
    provider_native_readback: bool
    post_commit_design_sha256: str
    post_commit_page_count: int
    observed_cost_microunits: int
    post_commit_updated_at: str
    proof_ref: str
    export_performed: bool = False
    download_performed: bool = False
    share_performed: bool = False
    publish_performed: bool = False

    def __post_init__(self) -> None:
        _require_bool_fields(
            self,
            "committed",
            "approval_consumed",
            "provider_native_readback",
            "export_performed",
            "download_performed",
            "share_performed",
            "publish_performed",
        )
        for name in (
            "approval_id",
            "design_id",
            "transaction_id",
            "selection_id",
            "runtime_identity",
            "credential_reference",
            "proof_ref",
        ):
            _require_text(getattr(self, name), name)
        for name in (
            "connector_schema_sha256",
            "brand_controls_sha256",
            "eligibility_evidence_sha256",
            "operations_sha256",
            "post_commit_design_sha256",
        ):
            _require_sha256(getattr(self, name), name)
        _require_credential_reference(self.credential_reference)
        _require_int(self.post_commit_page_count, "post_commit_page_count")
        if self.post_commit_page_count < 1:
            raise ValueError("post_commit_page_count must be positive")
        _require_int(self.observed_cost_microunits, "observed_cost_microunits")
        if self.observed_cost_microunits != 0:
            raise ValueError("commit readback exceeds the exact zero-cost ceiling")
        _parse_timestamp(self.post_commit_updated_at, "post_commit_updated_at")


@dataclass(frozen=True, slots=True)
class CanvaCanaryDecision:
    state: CanvaCanaryState
    ready_for_effect: bool
    contract_preconditions_met: bool
    envelope_consistent: bool
    receipt_validated: bool
    next_gate: str
    reasons: tuple[str, ...]
    truth_boundary: str

    def __post_init__(self) -> None:
        _require_bool_fields(
            self,
            "ready_for_effect",
            "contract_preconditions_met",
            "envelope_consistent",
            "receipt_validated",
        )
        if self.ready_for_effect or self.contract_preconditions_met:
            raise ValueError("pure Canva decisions cannot grant or claim provider authority")
        structural = self.state in {
            CanvaCanaryState.READY_FOR_CANDIDATE_CONVERSION,
            CanvaCanaryState.READY_FOR_DRAFT_EDIT,
            CanvaCanaryState.READY_FOR_COMMIT,
        }
        if self.envelope_consistent is not structural:
            raise ValueError("envelope_consistent must be derived from the decision state")
        _require_text(self.next_gate, "next_gate")
        _require_text(self.truth_boundary, "truth_boundary")
        if not self.reasons or any(not isinstance(reason, str) or not reason.strip() for reason in self.reasons):
            raise ValueError("reasons must be a non-empty tuple of text values")


_TRUTH_BOUNDARY = (
    "This pure evaluator issues no provider authority and performs no Canva operation. Source tests, CI, or "
    "simulated receipts prove only deterministic envelope behavior. READY states are caller-supplied envelope "
    "consistency only; ready_for_effect and contract_preconditions_met remain false. Execution requires separately "
    "authenticated current, exact, single-use "
    "authority at execution time. SAVED_DESIGN_RECEIPT_VALIDATED proves only that a "
    "supplied provider-native receipt set is internally consistent for one saved Canva design; receipt provenance "
    "must be independently authenticated. It does not prove export, download, share, publish, repeated success, "
    "commercial value, deployment, production traffic, or production maturity."
)


def _require_text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")


def _require_bool_fields(record: Any, *names: str) -> None:
    invalid = sorted(name for name in names if type(getattr(record, name)) is not bool)
    if invalid:
        raise ValueError(f"boolean fields must use literal true/false values: {invalid}")


def _require_int(value: int, name: str) -> None:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer, not a coerced value")


def _require_credential_reference(value: str) -> None:
    _require_text(value, "credential_reference")
    if not _SAFE_CREDENTIAL_REFERENCE.fullmatch(value):
        raise ValueError("credential_reference must be an opaque connector handle, never a secret")
    for segment in value.lower().split(":")[1:]:
        if segment.startswith(("sk-", "pk-", "key-", "token-", "secret-")) or any(
            marker in segment for marker in ("api-key", "apikey", "password", "credential")
        ):
            raise ValueError("credential_reference contains secret-shaped material")


def _require_sha256(value: str, name: str) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a 64-character lowercase hex digest")


def _parse_timestamp(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("evaluated_at must include a timezone")
    return value.astimezone(timezone.utc)


def _validate_receipt_window(issued_at: str, expires_at: str) -> None:
    issued = _parse_timestamp(issued_at, "issued_at")
    expires = _parse_timestamp(expires_at, "expires_at")
    if expires <= issued:
        raise ValueError("expires_at must be later than issued_at")


def _receipt_is_current(issued_at: str, expires_at: str, at: datetime) -> bool:
    point = _as_utc(at)
    return _parse_timestamp(issued_at, "issued_at") <= point < _parse_timestamp(
        expires_at, "expires_at"
    )


def _forbidden_effects(record: Any) -> tuple[str, ...]:
    fields = ("export_performed", "download_performed", "share_performed", "publish_performed")
    return tuple(name.upper() for name in fields if getattr(record, name, False))


def _consumption_ledger(values: Iterable[str]) -> tuple[str, ...]:
    ledger = tuple(values)
    if any(not isinstance(item, str) or not item.strip() for item in ledger):
        raise ValueError("consumed_receipt_ids must contain nonblank identifiers")
    if len(set(ledger)) != len(ledger):
        raise ValueError("consumed_receipt_ids cannot contain duplicate transition events")
    return ledger


def _eligibility_matches(
    contract: CanvaInvariantContract,
    selection: CanvaOwnerSelectionReceipt,
    evidence: CanvaEligibilityEvidence,
    evaluated_at: datetime,
) -> bool:
    return (
        evidence.evidence_sha256 == selection.eligibility_evidence_sha256
        and evidence.candidate_set_id == contract.candidate_set_id
        and evidence.candidate_roster_sha256 == contract.candidate_roster_sha256
        and evidence.candidate_roster_sha256 == selection.candidate_roster_sha256
        and evidence.candidate_id == selection.candidate_id
        and evidence.age_state == contract.age_state_required
        and evidence.consent_state == contract.consent_state_required
        and evidence.rights_state == contract.rights_state_required
        and evidence.asset_origin_state == contract.asset_origin_state_required
        and evidence.privacy_eligible
        and evidence.candidate_membership_verified
        and evidence.trusted_surface_verified
        and evidence.is_current(evaluated_at)
        and _parse_timestamp(evidence.issued_at, "issued_at")
        <= _parse_timestamp(selection.issued_at, "issued_at")
    )


def _decision(
    state: CanvaCanaryState,
    *,
    next_gate: str,
    reasons: Sequence[str],
    receipt_validated: bool = False,
) -> CanvaCanaryDecision:
    contract_ready = state in {
        CanvaCanaryState.READY_FOR_CANDIDATE_CONVERSION,
        CanvaCanaryState.READY_FOR_DRAFT_EDIT,
        CanvaCanaryState.READY_FOR_COMMIT,
    }
    return CanvaCanaryDecision(
        state=state,
        ready_for_effect=False,
        contract_preconditions_met=False,
        envelope_consistent=contract_ready,
        receipt_validated=receipt_validated,
        next_gate=next_gate,
        reasons=tuple(reasons),
        truth_boundary=_TRUTH_BOUNDARY,
    )


def _schema_gate(contract: CanvaInvariantContract, evaluated_at: datetime) -> CanvaCanaryDecision | None:
    if not contract.schema_is_current(evaluated_at):
        return _decision(
            CanvaCanaryState.HOLD_SCHEMA_FRESHNESS,
            next_gate="REFRESH_CURRENT_CANVA_CONNECTOR_SCHEMA_SNAPSHOT",
            reasons=("CURRENT_CANVA_SCHEMA_SNAPSHOT_REQUIRED",),
        )
    return None


def source_only_canva_decision(
    contract: CanvaInvariantContract, *, evaluated_at: datetime
) -> CanvaCanaryDecision:
    """Resolve the candidate-neutral layer without accepting a candidate choice."""

    stale = _schema_gate(contract, evaluated_at)
    if stale:
        return stale
    return _decision(
        CanvaCanaryState.HOLD_OWNER_SELECTION,
        next_gate="OWNER_SELECT_ONE_CANDIDATE_ON_A_TRUSTED_SURFACE",
        reasons=(
            "CANDIDATE_NEUTRAL_INVARIANTS_VALID",
            "SOURCE_EFFECT_AUTHORITY_FALSE",
            "OWNER_SELECTION_REQUIRED",
        ),
    )


def evaluate_candidate_conversion_readiness(
    contract: CanvaInvariantContract,
    selection: CanvaOwnerSelectionReceipt | None,
    eligibility: CanvaEligibilityEvidence | None,
    authority: CanvaCreateAuthority | None,
    *,
    evaluated_at: datetime,
    consumed_receipt_ids: Iterable[str] = (),
    _historical: bool = False,
) -> CanvaCanaryDecision:
    """Validate the exact owner selection and one-create authority without executing it."""

    stale = _schema_gate(contract, evaluated_at)
    if stale:
        return stale
    if selection is None:
        return source_only_canva_decision(contract, evaluated_at=evaluated_at)

    ledger = _consumption_ledger(consumed_receipt_ids)
    consumed = set(ledger)
    selection_valid = (
        selection.invariant_id == contract.invariant_id
        and selection.connector_schema_sha256 == contract.connector_schema_sha256
        and selection.candidate_set_id == contract.candidate_set_id
        and selection.candidate_roster_sha256 == contract.candidate_roster_sha256
        and selection.selected_by == _OWNER
        and selection.owner_authored
        and selection.trusted_surface_verified
        and selection.explicit_not_inferred
        and selection.single_use
        and not selection.consumed
        and (_historical or selection.selection_id not in consumed)
        and selection.is_current(evaluated_at)
    )
    if not selection_valid:
        return _decision(
            CanvaCanaryState.HOLD_SELECTION_RECEIPT,
            next_gate="CAPTURE_FRESH_EXPLICIT_OWNER_SELECTION_RECEIPT",
            reasons=("OWNER_SELECTION_RECEIPT_INVALID_STALE_MISMATCHED_OR_REPLAYED",),
        )

    if eligibility is None or not _eligibility_matches(contract, selection, eligibility, evaluated_at):
        return _decision(
            CanvaCanaryState.HOLD_SELECTION_RECEIPT,
            next_gate="CAPTURE_TYPED_AUTHENTICATED_ELIGIBILITY_AND_MEMBERSHIP_ATTESTATION",
            reasons=("ELIGIBILITY_OR_CANDIDATE_MEMBERSHIP_EVIDENCE_INVALID",),
        )

    if authority is None:
        return _decision(
            CanvaCanaryState.HOLD_CREATE_AUTHORITY,
            next_gate="ISSUE_EXACT_SINGLE_USE_CREATE_AUTHORITY_AFTER_OWNER_SELECTION",
            reasons=("SEPARATE_CREATE_EFFECT_AUTHORITY_REQUIRED",),
        )

    authority_valid = (
        authority.selection_id == selection.selection_id
        and authority.invariant_id == contract.invariant_id
        and authority.provider_name.upper() == _PROVIDER
        and authority.connector_schema_sha256 == contract.connector_schema_sha256
        and authority.brand_controls_sha256 == selection.brand_controls_sha256
        and authority.candidate_id == selection.candidate_id
        and authority.job_id == selection.job_id
        and authority.eligibility_evidence_sha256 == eligibility.evidence_sha256
        and authority.privacy_eligible
        and authority.create_effect_authorized
        and authority.max_creations == contract.max_designs
        and authority.single_use
        and not authority.consumed
        and authority.maximum_cost_microunits == 0
        and (_historical or authority.authority_id not in consumed)
        and authority.is_current(evaluated_at)
        and _parse_timestamp(selection.issued_at, "issued_at")
        < _parse_timestamp(authority.issued_at, "issued_at")
    )
    if not authority_valid:
        return _decision(
            CanvaCanaryState.HOLD_CREATE_AUTHORITY,
            next_gate="REISSUE_EXACT_CURRENT_SINGLE_USE_CREATE_AUTHORITY",
            reasons=("CREATE_AUTHORITY_INVALID_STALE_MISMATCHED_OR_REPLAYED",),
        )

    if (
        not authority.create_rollback_supported
        or authority.create_rollback_tool not in _CREATE_ROLLBACK_TOOLS
        or authority.create_rollback_tool not in contract.connector_tools
    ):
        return _decision(
            CanvaCanaryState.HOLD_CREATE_ROLLBACK,
            next_gate="PROVE_PROVIDER_NATIVE_CREATE_ROLLBACK_BEFORE_CONVERSION",
            reasons=("CREATE_ROLLBACK_CAPABILITY_UNPROVEN",),
        )

    return _decision(
        CanvaCanaryState.READY_FOR_CANDIDATE_CONVERSION,
        next_gate="INVOKE_CREATE_DESIGN_FROM_CANDIDATE_ONCE_THEN_READ_BACK_DESIGN_METADATA",
        reasons=(
            "EXPLICIT_OWNER_SELECTION_BOUND",
            "CURRENT_CANVA_SCHEMA_BOUND",
            "EXACT_ONE_CREATE_AUTHORITY_BOUND",
            "CREATE_ROLLBACK_ENVELOPE_BOUND_NOT_AUTHENTICATED",
            "UNAUTHENTICATED_ENVELOPE_ONLY",
            "EXPORT_DOWNLOAD_SHARE_PUBLISH_FORBIDDEN",
        ),
    )


def evaluate_create_readback(
    contract: CanvaInvariantContract,
    selection: CanvaOwnerSelectionReceipt,
    eligibility: CanvaEligibilityEvidence,
    authority: CanvaCreateAuthority,
    readback: CanvaCreateReadback | None,
    *,
    evaluated_at: datetime,
    consumed_receipt_ids: Iterable[str] = (),
) -> CanvaCanaryDecision:
    """Validate one candidate-conversion receipt before any draft edit."""

    ledger = _consumption_ledger(consumed_receipt_ids)
    ready = evaluate_candidate_conversion_readiness(
        contract,
        selection,
        eligibility,
        authority,
        evaluated_at=evaluated_at,
        consumed_receipt_ids=ledger,
        _historical=True,
    )
    if ready.state is not CanvaCanaryState.READY_FOR_CANDIDATE_CONVERSION:
        return ready
    if readback is None:
        return _decision(
            CanvaCanaryState.HOLD_CREATE_READBACK,
            next_gate="READ_BACK_CREATED_DESIGN_WITH_PROVIDER_NATIVE_METADATA",
            reasons=("CREATE_READBACK_REQUIRED",),
        )
    forbidden = _forbidden_effects(readback)
    consumed = set(ledger)
    valid = (
        not forbidden
        and readback.authority_id == authority.authority_id
        and readback.selection_id == selection.selection_id
        and readback.exact_request_sha256 == authority.exact_request_sha256
        and readback.job_id == selection.job_id
        and readback.candidate_id == selection.candidate_id
        and readback.connector_schema_sha256 == contract.connector_schema_sha256
        and readback.brand_controls_sha256 == selection.brand_controls_sha256
        and readback.eligibility_evidence_sha256 == eligibility.evidence_sha256
        and readback.runtime_identity == authority.runtime_identity
        and readback.credential_reference == authority.credential_reference
        and readback.observed_cost_microunits <= authority.maximum_cost_microunits
        and readback.owner_fingerprint_sha256 == authority.expected_owner_fingerprint_sha256
        and readback.title_sha256 == authority.expected_title_sha256
        and readback.provider_native_readback
        and readback.authority_consumed
        and {selection.selection_id, authority.authority_id}.issubset(consumed)
        and _parse_timestamp(authority.issued_at, "issued_at")
        < _parse_timestamp(readback.created_at, "created_at")
        and _parse_timestamp(readback.updated_at, "updated_at") <= _as_utc(evaluated_at)
    )
    if not valid:
        reasons = forbidden or ("CREATE_READBACK_MISSING_MISMATCHED_OR_FORBIDDEN_EFFECT",)
        return _decision(
            CanvaCanaryState.HOLD_CREATE_READBACK,
            next_gate="QUARANTINE_DESIGN_AND_RECONCILE_EXACT_CREATE_READBACK",
            reasons=reasons,
        )
    return _decision(
        CanvaCanaryState.HOLD_DRAFT_AUTHORITY,
        next_gate="ISSUE_SEPARATE_EXACT_DRAFT_AUTHORITY_FOR_CREATED_DESIGN",
        reasons=("CREATE_RECEIPT_VALIDATED", "DRAFT_EFFECT_NOT_YET_AUTHORIZED"),
        receipt_validated=True,
    )


def evaluate_draft_readiness(
    contract: CanvaInvariantContract,
    selection: CanvaOwnerSelectionReceipt,
    eligibility: CanvaEligibilityEvidence,
    authority: CanvaCreateAuthority,
    readback: CanvaCreateReadback,
    draft_authority: CanvaDraftAuthority | None,
    *,
    evaluated_at: datetime,
    consumed_receipt_ids: Iterable[str] = (),
    _historical: bool = False,
) -> CanvaCanaryDecision:
    """Validate a separate cancelable draft authority after create readback."""

    ledger = _consumption_ledger(consumed_receipt_ids)
    created = evaluate_create_readback(
        contract,
        selection,
        eligibility,
        authority,
        readback,
        evaluated_at=evaluated_at,
        consumed_receipt_ids=ledger,
    )
    if created.state is not CanvaCanaryState.HOLD_DRAFT_AUTHORITY:
        return created
    if draft_authority is None:
        return created

    consumed = set(ledger)
    valid = (
        draft_authority.create_authority_id == authority.authority_id
        and draft_authority.selection_id == selection.selection_id
        and draft_authority.design_id == readback.design_id
        and draft_authority.candidate_id == selection.candidate_id
        and draft_authority.job_id == selection.job_id
        and draft_authority.connector_schema_sha256 == contract.connector_schema_sha256
        and draft_authority.brand_controls_sha256 == selection.brand_controls_sha256
        and draft_authority.eligibility_evidence_sha256 == eligibility.evidence_sha256
        and draft_authority.runtime_identity == authority.runtime_identity
        and draft_authority.credential_reference == authority.credential_reference
        and draft_authority.maximum_cost_microunits == authority.maximum_cost_microunits
        and draft_authority.draft_effect_authorized
        and 1 <= draft_authority.max_operations <= contract.max_draft_operations
        and draft_authority.single_use
        and not draft_authority.consumed
        and (_historical or draft_authority.authority_id not in consumed)
        and draft_authority.is_current(evaluated_at)
        and _parse_timestamp(readback.updated_at, "updated_at")
        < _parse_timestamp(draft_authority.issued_at, "issued_at")
    )
    if not valid:
        return _decision(
            CanvaCanaryState.HOLD_DRAFT_AUTHORITY,
            next_gate="REISSUE_EXACT_CURRENT_SINGLE_USE_DRAFT_AUTHORITY",
            reasons=("DRAFT_AUTHORITY_INVALID_STALE_MISMATCHED_OR_REPLAYED",),
        )
    if (
        not draft_authority.cancel_draft_supported
        or "cancel_editing_transaction" not in contract.connector_tools
    ):
        return _decision(
            CanvaCanaryState.HOLD_DRAFT_ROLLBACK,
            next_gate="PROVE_CANCEL_EDITING_TRANSACTION_BEFORE_DRAFT_EDIT",
            reasons=("DRAFT_CANCEL_CAPABILITY_UNPROVEN",),
        )
    return _decision(
        CanvaCanaryState.READY_FOR_DRAFT_EDIT,
        next_gate="START_ONE_EDITING_TRANSACTION_APPLY_BOUND_OPERATIONS_AND_CAPTURE_OWNER_PREVIEW",
        reasons=(
            "CREATE_RECEIPT_VALIDATED",
            "EXACT_DRAFT_AUTHORITY_BOUND",
            "DRAFT_CANCEL_ENVELOPE_BOUND_NOT_AUTHENTICATED",
            "UNAUTHENTICATED_ENVELOPE_ONLY",
            "COMMIT_AUTHORITY_FALSE",
        ),
        receipt_validated=True,
    )


def evaluate_commit_readiness(
    contract: CanvaInvariantContract,
    selection: CanvaOwnerSelectionReceipt,
    eligibility: CanvaEligibilityEvidence,
    authority: CanvaCreateAuthority,
    readback: CanvaCreateReadback,
    draft_authority: CanvaDraftAuthority,
    draft: CanvaDraftObservation | None,
    approval: CanvaCommitApproval | None,
    *,
    evaluated_at: datetime,
    consumed_receipt_ids: Iterable[str] = (),
    _historical: bool = False,
) -> CanvaCanaryDecision:
    """Require owner preview and a new exact approval immediately before commit."""

    ledger = _consumption_ledger(consumed_receipt_ids)
    draft_ready = evaluate_draft_readiness(
        contract,
        selection,
        eligibility,
        authority,
        readback,
        draft_authority,
        evaluated_at=evaluated_at,
        consumed_receipt_ids=ledger,
        _historical=True,
    )
    if draft_ready.state is not CanvaCanaryState.READY_FOR_DRAFT_EDIT:
        return draft_ready
    if draft is None:
        return _decision(
            CanvaCanaryState.HOLD_DRAFT_PREVIEW,
            next_gate="CAPTURE_PROVIDER_NATIVE_DRAFT_AND_OWNER_VISIBLE_PREVIEW",
            reasons=("DRAFT_PREVIEW_REQUIRED_BEFORE_COMMIT_APPROVAL",),
        )

    forbidden = _forbidden_effects(draft)
    consumed = set(ledger)
    draft_valid = (
        not forbidden
        and draft.draft_authority_id == draft_authority.authority_id
        and draft.design_id == readback.design_id
        and draft.selection_id == selection.selection_id
        and draft.candidate_id == selection.candidate_id
        and draft.job_id == selection.job_id
        and draft.connector_schema_sha256 == contract.connector_schema_sha256
        and draft.brand_controls_sha256 == selection.brand_controls_sha256
        and draft.eligibility_evidence_sha256 == eligibility.evidence_sha256
        and draft.runtime_identity == authority.runtime_identity
        and draft.credential_reference == authority.credential_reference
        and draft.observed_cost_microunits <= draft_authority.maximum_cost_microunits
        and draft.operations_sha256 == draft_authority.operations_sha256
        and draft.operations_applied_count <= draft_authority.max_operations
        and draft.draft_only
        and not draft.committed
        and draft.provider_native_readback
        and draft.authority_consumed
        and draft_authority.authority_id in consumed
        and _parse_timestamp(draft_authority.issued_at, "issued_at")
        < _parse_timestamp(draft.previewed_at, "previewed_at")
        and _parse_timestamp(draft.previewed_at, "previewed_at") <= _as_utc(evaluated_at)
    )
    if not draft_valid:
        reasons = forbidden or ("DRAFT_READBACK_OR_PREVIEW_INVALID_OR_ALREADY_COMMITTED",)
        return _decision(
            CanvaCanaryState.HOLD_DRAFT_PREVIEW,
            next_gate="CANCEL_OR_QUARANTINE_DRAFT_AND_RECONCILE_PREVIEW",
            reasons=reasons,
        )
    if approval is None:
        return _decision(
            CanvaCanaryState.HOLD_COMMIT_APPROVAL,
            next_gate="OWNER_REVIEW_PREVIEW_THEN_ISSUE_EXACT_SINGLE_USE_COMMIT_APPROVAL",
            reasons=("SEPARATE_POST_PREVIEW_COMMIT_APPROVAL_REQUIRED",),
            receipt_validated=True,
        )

    previewed_at = _parse_timestamp(draft.previewed_at, "previewed_at")
    approved_at = _parse_timestamp(approval.issued_at, "issued_at")
    approval_valid = (
        approval.selection_id == selection.selection_id
        and approval.design_id == readback.design_id
        and approval.transaction_id == draft.transaction_id
        and approval.connector_schema_sha256 == contract.connector_schema_sha256
        and approval.brand_controls_sha256 == selection.brand_controls_sha256
        and approval.eligibility_evidence_sha256 == eligibility.evidence_sha256
        and approval.runtime_identity == authority.runtime_identity
        and approval.credential_reference == authority.credential_reference
        and approval.maximum_cost_microunits == draft_authority.maximum_cost_microunits
        and approval.operations_sha256 == draft.operations_sha256
        and approval.preview_sha256 == draft.preview_sha256
        and approval.approved_by == _OWNER
        and approval.owner_authored
        and approval.trusted_surface_verified
        and approval.explicit_after_preview
        and approval.commit_effect_authorized
        and approved_at > previewed_at
        and approval.single_use
        and not approval.consumed
        and (_historical or approval.approval_id not in consumed)
        and approval.is_current(evaluated_at)
    )
    if not approval_valid:
        return _decision(
            CanvaCanaryState.HOLD_COMMIT_APPROVAL,
            next_gate="CAPTURE_FRESH_EXACT_OWNER_COMMIT_APPROVAL_AFTER_PREVIEW",
            reasons=("COMMIT_APPROVAL_INVALID_STALE_PREVIEW_MISMATCHED_OR_REPLAYED",),
            receipt_validated=True,
        )
    return _decision(
        CanvaCanaryState.READY_FOR_COMMIT,
        next_gate="COMMIT_BOUND_TRANSACTION_ONCE_THEN_READ_BACK_SAVED_DESIGN_METADATA",
        reasons=(
            "DRAFT_PREVIEW_RECEIPT_VALIDATED",
            "EXPLICIT_OWNER_APPROVAL_ISSUED_AFTER_PREVIEW",
            "EXACT_ONE_COMMIT_AUTHORITY_BOUND",
            "UNAUTHENTICATED_ENVELOPE_ONLY",
            "EXPORT_DOWNLOAD_SHARE_PUBLISH_FORBIDDEN",
        ),
        receipt_validated=True,
    )


def evaluate_saved_design_readback(
    contract: CanvaInvariantContract,
    selection: CanvaOwnerSelectionReceipt,
    eligibility: CanvaEligibilityEvidence,
    authority: CanvaCreateAuthority,
    readback: CanvaCreateReadback,
    draft_authority: CanvaDraftAuthority,
    draft: CanvaDraftObservation,
    approval: CanvaCommitApproval,
    commit: CanvaCommitReadback | None,
    *,
    evaluated_at: datetime,
    consumed_receipt_ids: Iterable[str] = (),
) -> CanvaCanaryDecision:
    """Validate post-commit receipt bindings without claiming provider provenance."""

    ledger = _consumption_ledger(consumed_receipt_ids)
    ready = evaluate_commit_readiness(
        contract,
        selection,
        eligibility,
        authority,
        readback,
        draft_authority,
        draft,
        approval,
        evaluated_at=evaluated_at,
        consumed_receipt_ids=ledger,
        _historical=True,
    )
    if ready.state is not CanvaCanaryState.READY_FOR_COMMIT:
        return ready
    if commit is None:
        return _decision(
            CanvaCanaryState.HOLD_COMMIT_READBACK,
            next_gate="READ_BACK_COMMIT_RESULT_AND_POST_COMMIT_DESIGN_METADATA",
            reasons=("POST_COMMIT_PROVIDER_READBACK_REQUIRED",),
            receipt_validated=True,
        )

    forbidden = _forbidden_effects(commit)
    consumed = set(ledger)
    committed_at = _parse_timestamp(commit.post_commit_updated_at, "post_commit_updated_at")
    approved_at = _parse_timestamp(approval.issued_at, "issued_at")
    valid = (
        not forbidden
        and commit.approval_id == approval.approval_id
        and commit.design_id == readback.design_id
        and commit.transaction_id == draft.transaction_id
        and commit.selection_id == selection.selection_id
        and commit.connector_schema_sha256 == contract.connector_schema_sha256
        and commit.brand_controls_sha256 == selection.brand_controls_sha256
        and commit.eligibility_evidence_sha256 == eligibility.evidence_sha256
        and commit.runtime_identity == authority.runtime_identity
        and commit.credential_reference == authority.credential_reference
        and commit.observed_cost_microunits <= approval.maximum_cost_microunits
        and commit.operations_sha256 == draft.operations_sha256
        and commit.post_commit_design_sha256 == approval.expected_post_commit_design_sha256
        and commit.committed
        and commit.approval_consumed
        and approval.approval_id in consumed
        and commit.provider_native_readback
        and commit.post_commit_page_count == readback.page_count
        and committed_at > approved_at
        and committed_at <= _as_utc(evaluated_at)
    )
    if not valid:
        reasons = forbidden or ("COMMIT_OR_POST_COMMIT_READBACK_INVALID_MISMATCHED_OR_FORBIDDEN",)
        return _decision(
            CanvaCanaryState.HOLD_COMMIT_READBACK,
            next_gate="QUARANTINE_RESULT_AND_RECONCILE_PROVIDER_NATIVE_COMMIT_READBACK",
            reasons=reasons,
            receipt_validated=True,
        )
    return _decision(
        CanvaCanaryState.SAVED_DESIGN_RECEIPT_VALIDATED,
        next_gate="AUTHENTICATE_RECEIPT_PROVENANCE_THEN_RUN_SEPARATE_EXPORT_CAPABILITY_GATE",
        reasons=(
            "ONE_SAVED_DESIGN_RECEIPT_SET_INTERNALLY_CONSISTENT",
            "CREATE_DRAFT_COMMIT_AUTHORITIES_SEPARATED",
            "OWNER_SELECTION_AND_POST_PREVIEW_APPROVAL_BOUND",
            "NO_EXPORT_DOWNLOAD_SHARE_OR_PUBLISH_RECEIPT",
        ),
        receipt_validated=True,
    )


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(payload).hexdigest()


def load_canva_invariant_contract(path: str | Path) -> CanvaInvariantContract:
    """Load a candidate-neutral contract and validate its schema hash domain."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("contract root must be an object")
    allowed_keys = {
        "schema",
        "invariant_id",
        "candidate_set_id",
        "candidate_roster_sha256",
        "expected_candidate_count",
        "owner_selection_required",
        "age_state_required",
        "consent_state_required",
        "rights_state_required",
        "asset_origin_state_required",
        "raw_sensitive_payload_allowed",
        "connector_schema_snapshot_id",
        "connector_schema_sha256",
        "connector_schema_provenance_sha256",
        "connector_schema_authenticated",
        "connector_schema_snapshot",
        "schema_checked_at",
        "schema_expires_at",
        "max_designs",
        "max_draft_operations",
        "create_effect_authorized",
        "draft_effect_authorized",
        "commit_effect_authorized",
        "export_allowed",
        "download_allowed",
        "share_allowed",
        "publish_allowed",
        "required_readbacks",
        "rollback_requirements",
        "execution_gate",
        "truth_boundary",
    }
    leaked = sorted(_CANDIDATE_SPECIFIC_KEYS & set(data))
    if leaked:
        raise ValueError(f"candidate-neutral contract contains selection fields: {leaked}")
    unknown = sorted(set(data) - allowed_keys)
    if unknown:
        raise ValueError(f"contract contains unknown fields: {unknown}")
    snapshot = data.get("connector_schema_snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("connector_schema_snapshot is required")
    if set(snapshot) != {"provider", "retrieved_at", "tools", "semantic_invariants"}:
        raise ValueError("connector_schema_snapshot has an unexpected shape")
    if snapshot.get("provider") != "Canva":
        raise ValueError("connector schema provider must be Canva")
    if snapshot.get("retrieved_at") != data.get("schema_checked_at"):
        raise ValueError("connector schema retrieval and checked timestamps must match")
    declared_hash = str(data.get("connector_schema_sha256") or "")
    if declared_hash != _canonical_sha256(snapshot):
        raise ValueError("connector_schema_sha256 does not match canonical snapshot")
    tools = snapshot.get("tools")
    if not isinstance(tools, dict):
        raise ValueError("connector_schema_snapshot.tools must be an object")
    expected_specs = _REQUIRED_CONNECTOR_TOOLS
    missing_tools = sorted(set(_REQUIRED_CONNECTOR_TOOLS) - set(tools))
    unknown_tools = sorted(set(tools) - set(_REQUIRED_CONNECTOR_TOOLS))
    if missing_tools or unknown_tools:
        raise ValueError(
            f"connector schema capability mismatch; missing={missing_tools}, unknown={unknown_tools}"
        )
    for name, raw_spec in tools.items():
        if not isinstance(raw_spec, dict) or set(raw_spec) != {"effect", "required_bindings"}:
            raise ValueError(f"connector schema tool {name} has an unexpected shape")
        effect, bindings = expected_specs[name]
        if raw_spec.get("effect") != effect or raw_spec.get("required_bindings") != list(bindings):
            raise ValueError(f"connector schema tool {name} semantic contract mismatch")
    if snapshot.get("semantic_invariants") != list(_REQUIRED_SEMANTIC_INVARIANTS):
        raise ValueError("connector schema semantic invariants mismatch")
    expected_provenance = _canonical_sha256(
        {
            "connector_schema_snapshot_id": data.get("connector_schema_snapshot_id"),
            "connector_schema_sha256": declared_hash,
            "retrieved_at": snapshot.get("retrieved_at"),
            "surface": _PROVENANCE_SURFACE,
        }
    )
    if data.get("connector_schema_provenance_sha256") != expected_provenance:
        raise ValueError("connector schema provenance commitment mismatch")
    for name in ("expected_candidate_count", "max_designs", "max_draft_operations"):
        if type(data.get(name)) is not int:
            raise ValueError(f"{name} must be a literal JSON integer")
    for name in (
        "owner_selection_required",
        "raw_sensitive_payload_allowed",
        "connector_schema_authenticated",
        "create_effect_authorized",
        "draft_effect_authorized",
        "commit_effect_authorized",
        "export_allowed",
        "download_allowed",
        "share_allowed",
        "publish_allowed",
    ):
        if type(data.get(name)) is not bool:
            raise ValueError(f"{name} must be a literal JSON boolean")
    for name in (
        "schema",
        "invariant_id",
        "candidate_set_id",
        "candidate_roster_sha256",
        "age_state_required",
        "consent_state_required",
        "rights_state_required",
        "asset_origin_state_required",
        "connector_schema_snapshot_id",
        "connector_schema_sha256",
        "connector_schema_provenance_sha256",
        "schema_checked_at",
        "schema_expires_at",
    ):
        if not isinstance(data.get(name), str):
            raise ValueError(f"{name} must be a JSON string")
    for name in ("required_readbacks", "rollback_requirements"):
        raw_items = data.get(name)
        if not isinstance(raw_items, list) or any(not isinstance(item, str) for item in raw_items):
            raise ValueError(f"{name} must be an array of strings")
    return CanvaInvariantContract(
        schema=str(data.get("schema") or ""),
        invariant_id=str(data.get("invariant_id") or ""),
        candidate_set_id=str(data.get("candidate_set_id") or ""),
        candidate_roster_sha256=str(data.get("candidate_roster_sha256") or ""),
        expected_candidate_count=data["expected_candidate_count"],
        owner_selection_required=data.get("owner_selection_required") is True,
        age_state_required=str(data.get("age_state_required") or ""),
        consent_state_required=str(data.get("consent_state_required") or ""),
        rights_state_required=str(data.get("rights_state_required") or ""),
        asset_origin_state_required=str(data.get("asset_origin_state_required") or ""),
        raw_sensitive_payload_allowed=data.get("raw_sensitive_payload_allowed") is True,
        connector_schema_snapshot_id=str(data.get("connector_schema_snapshot_id") or ""),
        connector_schema_sha256=declared_hash,
        connector_schema_provenance_sha256=str(
            data.get("connector_schema_provenance_sha256") or ""
        ),
        connector_schema_authenticated=data.get("connector_schema_authenticated") is True,
        connector_tools=tuple(sorted(str(item) for item in tools)),
        schema_checked_at=str(data.get("schema_checked_at") or ""),
        schema_expires_at=str(data.get("schema_expires_at") or ""),
        max_designs=data["max_designs"],
        max_draft_operations=data["max_draft_operations"],
        create_effect_authorized=data.get("create_effect_authorized") is True,
        draft_effect_authorized=data.get("draft_effect_authorized") is True,
        commit_effect_authorized=data.get("commit_effect_authorized") is True,
        export_allowed=data.get("export_allowed") is True,
        download_allowed=data.get("download_allowed") is True,
        share_allowed=data.get("share_allowed") is True,
        publish_allowed=data.get("publish_allowed") is True,
        required_readbacks=tuple(str(item) for item in data.get("required_readbacks") or ()),
        rollback_requirements=tuple(str(item) for item in data.get("rollback_requirements") or ()),
    )
