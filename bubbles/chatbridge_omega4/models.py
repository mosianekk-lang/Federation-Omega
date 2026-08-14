from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Tuple


class ContinuationMode(str, Enum):
    NONE = "NONE"
    CLIENT_SESSION = "CLIENT_SESSION"
    OPENAI_CONVERSATION = "OPENAI_CONVERSATION"
    OPENAI_PREVIOUS_RESPONSE = "OPENAI_PREVIOUS_RESPONSE"


class ApprovalState(str, Enum):
    OPEN = "OPEN"
    WAIT_FOR_USER = "WAIT_FOR_USER"
    SCREEN_FIRST = "SCREEN_FIRST"
    REVIEW_FIRST = "REVIEW_FIRST"
    SIGNATURE_REQUIRED = "SIGNATURE_REQUIRED"
    SEND_APPROVAL = "SEND_APPROVAL"


class RestorePreviewReason(str, Enum):
    HISTORICAL_GENERATION = "HISTORICAL_GENERATION"
    RELEASED_NAMESPACE = "RELEASED_NAMESPACE"
    BRANCHED_NAMESPACE = "BRANCHED_NAMESPACE"
    MATERIAL_DELTA = "MATERIAL_DELTA"
    GOVERNANCE_DEGRADED = "GOVERNANCE_DEGRADED"


@dataclass(frozen=True)
class ProviderContinuationRef:
    """Exactly one provider continuation strategy may be active at a time."""

    mode: ContinuationMode = ContinuationMode.NONE
    provider: str = ""
    session_id: str = ""
    conversation_id: str = ""
    previous_response_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        fields = {
            ContinuationMode.CLIENT_SESSION: bool(self.session_id),
            ContinuationMode.OPENAI_CONVERSATION: bool(self.conversation_id),
            ContinuationMode.OPENAI_PREVIOUS_RESPONSE: bool(self.previous_response_id),
        }
        supplied = [name for name, value in (
            ("session_id", self.session_id),
            ("conversation_id", self.conversation_id),
            ("previous_response_id", self.previous_response_id),
        ) if value]
        if self.mode is ContinuationMode.NONE:
            if supplied:
                raise ValueError("continuation identifiers require an explicit continuation mode")
            return
        if not fields[self.mode]:
            raise ValueError(f"{self.mode.value} requires its matching identifier")
        if len(supplied) != 1:
            raise ValueError("continuation modes are mutually exclusive; supply exactly one identifier")

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["mode"] = self.mode.value
        return payload


@dataclass(frozen=True)
class GovernanceCapsule:
    owner: str
    project: str
    workstream: str
    adapter: str
    objective: str
    exact_next_action: str
    source_precedence: Tuple[str, ...] = (
        "AUTHENTICATED_PRIMARY",
        "CURRENT_PROVIDER_READBACK",
        "SIGNED_FINAL_ARTEFACT",
        "PROJECT_HEARTBEAT",
        "CANONICAL_CONTROL",
        "VERIFIED_HANDOFF",
        "PRIOR_CHAT_SUMMARY",
        "INFERENCE",
    )
    proof_classes: Tuple[str, ...] = (
        "VERIFIED",
        "USER_SUPPLIED",
        "INFERENCE",
        "UNVERIFIED",
        "DISPUTED",
        "CONTRADICTED",
        "UNKNOWN",
    )
    approval_gates: Tuple[ApprovalState, ...] = tuple()
    confidentiality_level: str = "NORMAL"
    matter_walls: Tuple[str, ...] = tuple()
    data_walls: Tuple[str, ...] = tuple()
    connector_permissions: Tuple[str, ...] = tuple()
    connector_exclusions: Tuple[str, ...] = tuple()
    active_specialists: Tuple[str, ...] = tuple()
    settled_decisions: Tuple[str, ...] = tuple()
    pending_external_actions: Tuple[str, ...] = tuple()
    user_stop: bool = False
    wait_for_user: bool = False
    external_effects_allowed: bool = False
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["approval_gates"] = [gate.value for gate in self.approval_gates]
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "GovernanceCapsule":
        data = dict(payload)
        data["approval_gates"] = tuple(ApprovalState(v) for v in data.get("approval_gates", []))
        tuple_fields = (
            "source_precedence",
            "proof_classes",
            "matter_walls",
            "data_walls",
            "connector_permissions",
            "connector_exclusions",
            "active_specialists",
            "settled_decisions",
            "pending_external_actions",
        )
        for name in tuple_fields:
            if name in data and not isinstance(data[name], tuple):
                data[name] = tuple(data[name])
        return cls(**data)

    def consequentially_locked(self) -> bool:
        return bool(
            self.user_stop
            or self.wait_for_user
            or self.approval_gates
            or not self.external_effects_allowed
        )


@dataclass(frozen=True)
class RestoreEnvelope:
    namespace_id: str
    namespace_display: str
    namespace_key: str
    generation_id: str
    generation_number: int
    handoff_id: str
    checkpoint_fingerprint: str
    governance: GovernanceCapsule
    hot_state: Dict[str, Any]
    warm_pointers: List[str]
    cold_pointers: List[str]
    provider_ref: ProviderContinuationRef
    preview_required: bool
    preview_reasons: Tuple[RestorePreviewReason, ...]
    lease_id: str
    lease_reused: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "namespace_id": self.namespace_id,
            "namespace_display": self.namespace_display,
            "namespace_key": self.namespace_key,
            "generation_id": self.generation_id,
            "generation_number": self.generation_number,
            "handoff_id": self.handoff_id,
            "checkpoint_fingerprint": self.checkpoint_fingerprint,
            "governance": self.governance.to_dict(),
            "hot_state": self.hot_state,
            "warm_pointers": self.warm_pointers,
            "cold_pointers": self.cold_pointers,
            "provider_ref": self.provider_ref.to_dict(),
            "preview_required": self.preview_required,
            "preview_reasons": [reason.value for reason in self.preview_reasons],
            "lease_id": self.lease_id,
            "lease_reused": self.lease_reused,
        }
