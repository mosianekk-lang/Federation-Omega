from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ao_harmonic_v3.science_and_routes import FormationEngine, Route

from .full_fidelity_ledger import (
    ArtifactReference,
    ConversationEvent,
    ConversationEventType,
    ConversationIdentityConflict,
    ConversationNotBound,
    ConversationRole,
    EventExecutionState,
    FullFidelityConversationLedger,
    IncompleteTranscript,
    PayloadAvailability,
    TerminalExecutionClaimError,
    TranscriptIntegrityState,
)


class AlphaOmegaCaptureError(RuntimeError):
    """Base error for Alpha→Omega multi-path/multi-stream capture."""


class CapturePathNotRegistered(AlphaOmegaCaptureError):
    pass


class CapturePathConflict(AlphaOmegaCaptureError):
    pass


class ObservationConflict(AlphaOmegaCaptureError):
    pass


class StreamManifestError(AlphaOmegaCaptureError):
    pass


class CapturePathKind(str, Enum):
    PROVIDER_API = "PROVIDER_API"
    NATIVE_EXPORT = "NATIVE_EXPORT"
    RENDERED_DOM = "RENDERED_DOM"
    BROWSER_ARCHIVE = "BROWSER_ARCHIVE"
    SHARED_TRANSCRIPT = "SHARED_TRANSCRIPT"
    CONNECTOR_READBACK = "CONNECTOR_READBACK"
    ATTACHMENT_STORE = "ATTACHMENT_STORE"
    CHECKPOINT_CAPSULE = "CHECKPOINT_CAPSULE"
    MANUAL_PRIMARY_SOURCE = "MANUAL_PRIMARY_SOURCE"
    OTHER = "OTHER"


class CapturePathState(str, Enum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    QUARANTINED = "QUARANTINED"
    UNVERIFIED = "UNVERIFIED"


class ConversationStream(str, Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"
    DEVELOPER = "DEVELOPER"
    TOOL_CALL = "TOOL_CALL"
    TOOL_RESULT = "TOOL_RESULT"
    CONNECTOR = "CONNECTOR"
    ATTACHMENT = "ATTACHMENT"
    DECISION = "DECISION"
    CORRECTION = "CORRECTION"
    CHECKPOINT = "CHECKPOINT"
    TERMINAL = "TERMINAL"
    OTHER = "OTHER"


class OrderingAuthority(str, Enum):
    EXPLICIT_GLOBAL_SEQUENCE = "EXPLICIT_GLOBAL_SEQUENCE"
    DERIVED_DETERMINISTIC_ORDER = "DERIVED_DETERMINISTIC_ORDER"


class ReconciliationState(str, Enum):
    STAGED = "STAGED"
    RECONCILED = "RECONCILED"
    CORROBORATED = "CORROBORATED"
    GAP_PENDING = "GAP_PENDING"
    CONFLICTED = "CONFLICTED"
    QUARANTINED = "QUARANTINED"


class AlphaOmegaRestoreMode(str, Enum):
    EXACT_MULTIPATH_MULTISTREAM_RESTORE = "EXACT_MULTIPATH_MULTISTREAM_RESTORE"
    EXACT_SINGLE_PATH_TRANSCRIPT_RESTORE = "EXACT_SINGLE_PATH_TRANSCRIPT_RESTORE"
    BOUNDED_MULTIPATH_MULTISTREAM_RESTORE = "BOUNDED_MULTIPATH_MULTISTREAM_RESTORE"
    REJECT_CONFLICTED = "REJECT_CONFLICTED"
    NO_ALPHA_OMEGA_CAPTURE = "NO_ALPHA_OMEGA_CAPTURE"


@dataclass(frozen=True)
class CapturePath:
    conversation_key: str
    path_id: str
    kind: CapturePathKind
    source_provider: str
    state: CapturePathState = CapturePathState.AVAILABLE
    priority: int = 50
    proof_strength: float = 0.8
    completeness: float = 0.8
    freshness: float = 0.8
    speed: float = 0.8
    reversibility: float = 1.0
    owner_burden: float = 0.0
    privacy_cost: float = 0.0
    maintenance_cost: float = 0.0
    independent_group: str = ""
    authoritative: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def normalized_group(self) -> str:
        return self.independent_group.strip() or f"{self.source_provider}:{self.kind.value}"

    @staticmethod
    def _unit(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def route(self) -> Route:
        state_factor = {
            CapturePathState.AVAILABLE: 1.0,
            CapturePathState.DEGRADED: 0.55,
            CapturePathState.UNVERIFIED: 0.35,
            CapturePathState.FAILED: 0.0,
            CapturePathState.QUARANTINED: 0.0,
        }[self.state]
        feasibility = self._unit(
            state_factor
            * (0.45 * self._unit(self.completeness) + 0.35 * self._unit(self.freshness) + 0.20)
        )
        strategic_value = self._unit(
            0.55 * self._unit(self.proof_strength)
            + 0.30 * self._unit(self.completeness)
            + 0.15 * (max(0, min(100, int(self.priority))) / 100.0)
        )
        return Route(
            route_id=self.path_id,
            route_type=self.kind.value,
            feasibility=feasibility,
            proof_strength=self._unit(self.proof_strength),
            reversibility=self._unit(self.reversibility),
            speed=self._unit(self.speed),
            strategic_value=strategic_value,
            owner_burden=self._unit(self.owner_burden),
            privacy_cost=self._unit(self.privacy_cost),
            maintenance_cost=self._unit(self.maintenance_cost),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_key": self.conversation_key.strip(),
            "path_id": self.path_id.strip(),
            "kind": self.kind.value,
            "source_provider": self.source_provider,
            "state": self.state.value,
            "priority": int(self.priority),
            "proof_strength": float(self.proof_strength),
            "completeness": float(self.completeness),
            "freshness": float(self.freshness),
            "speed": float(self.speed),
            "reversibility": float(self.reversibility),
            "owner_burden": float(self.owner_burden),
            "privacy_cost": float(self.privacy_cost),
            "maintenance_cost": float(self.maintenance_cost),
            "independent_group": self.normalized_group(),
            "authoritative": bool(self.authoritative),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CapturePath":
        return cls(
            conversation_key=str(payload["conversation_key"]),
            path_id=str(payload["path_id"]),
            kind=CapturePathKind(payload.get("kind", CapturePathKind.OTHER.value)),
            source_provider=str(payload.get("source_provider", "UNKNOWN")),
            state=CapturePathState(payload.get("state", CapturePathState.UNVERIFIED.value)),
            priority=int(payload.get("priority", 50) or 50),
            proof_strength=float(payload.get("proof_strength", 0.5) or 0.0),
            completeness=float(payload.get("completeness", 0.5) or 0.0),
            freshness=float(payload.get("freshness", 0.5) or 0.0),
            speed=float(payload.get("speed", 0.5) or 0.0),
            reversibility=float(payload.get("reversibility", 1.0) or 0.0),
            owner_burden=float(payload.get("owner_burden", 0.0) or 0.0),
            privacy_cost=float(payload.get("privacy_cost", 0.0) or 0.0),
            maintenance_cost=float(payload.get("maintenance_cost", 0.0) or 0.0),
            independent_group=str(payload.get("independent_group", "")),
            authoritative=bool(payload.get("authoritative", False)),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(frozen=True)
class CaptureObservation:
    conversation_key: str
    namespace_key: str
    path_id: str
    stream: ConversationStream
    role: ConversationRole
    event_type: ConversationEventType
    content: Any
    occurred_at: str
    global_sequence: Optional[int] = None
    stream_sequence: Optional[int] = None
    source_event_id: str = ""
    source_turn_id: str = ""
    provider_event_id: str = ""
    idempotency_key: str = ""
    execution_state: EventExecutionState = EventExecutionState.OBSERVED
    payload_availability: PayloadAvailability = PayloadAvailability.RAW_GOVERNED
    sensitivity: str = "GOVERNED_LOCAL"
    artifacts: Tuple[ArtifactReference, ...] = field(default_factory=tuple)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def identity_key(self) -> str:
        explicit = (
            self.source_event_id.strip()
            or self.provider_event_id.strip()
            or self.source_turn_id.strip()
        )
        if explicit:
            return f"source:{explicit}"
        return "implicit:" + _digest(
            {
                "conversation_key": self.conversation_key.strip(),
                "stream": self.stream.value,
                "role": self.role.value,
                "event_type": self.event_type.value,
                "content": self.content,
                "occurred_at": self.occurred_at,
            }
        )

    def payload_hash(self) -> str:
        return _digest(
            {
                "conversation_key": self.conversation_key.strip(),
                "stream": self.stream.value,
                "role": self.role.value,
                "event_type": self.event_type.value,
                "content": self.content,
                "source_event_id": self.source_event_id,
                "source_turn_id": self.source_turn_id,
                "provider_event_id": self.provider_event_id,
                "execution_state": self.execution_state.value,
                "payload_availability": self.payload_availability.value,
                "sensitivity": self.sensitivity,
                "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_key": self.conversation_key.strip(),
            "namespace_key": self.namespace_key.strip().casefold(),
            "path_id": self.path_id.strip(),
            "stream": self.stream.value,
            "role": self.role.value,
            "event_type": self.event_type.value,
            "content": self.content,
            "occurred_at": self.occurred_at,
            "global_sequence": self.global_sequence,
            "stream_sequence": self.stream_sequence,
            "source_event_id": self.source_event_id,
            "source_turn_id": self.source_turn_id,
            "provider_event_id": self.provider_event_id,
            "idempotency_key": self.idempotency_key,
            "execution_state": self.execution_state.value,
            "payload_availability": self.payload_availability.value,
            "sensitivity": self.sensitivity,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CaptureObservation":
        return cls(
            conversation_key=str(payload["conversation_key"]),
            namespace_key=str(payload["namespace_key"]),
            path_id=str(payload["path_id"]),
            stream=ConversationStream(payload.get("stream", ConversationStream.OTHER.value)),
            role=ConversationRole(payload.get("role", ConversationRole.UNKNOWN.value)),
            event_type=ConversationEventType(
                payload.get("event_type", ConversationEventType.OTHER.value)
            ),
            content=payload.get("content"),
            occurred_at=str(payload.get("occurred_at", "")),
            global_sequence=(
                int(payload["global_sequence"])
                if payload.get("global_sequence") is not None
                else None
            ),
            stream_sequence=(
                int(payload["stream_sequence"])
                if payload.get("stream_sequence") is not None
                else None
            ),
            source_event_id=str(payload.get("source_event_id", "")),
            source_turn_id=str(payload.get("source_turn_id", "")),
            provider_event_id=str(payload.get("provider_event_id", "")),
            idempotency_key=str(payload.get("idempotency_key", "")),
            execution_state=EventExecutionState(
                payload.get("execution_state", EventExecutionState.UNVERIFIED.value)
            ),
            payload_availability=PayloadAvailability(
                payload.get("payload_availability", PayloadAvailability.POINTER_ONLY.value)
            ),
            sensitivity=str(payload.get("sensitivity", "GOVERNED_LOCAL")),
            artifacts=tuple(
                ArtifactReference.from_dict(item) for item in payload.get("artifacts", [])
            ),
            metadata=dict(payload.get("metadata", {})),
        )

    def to_event(
        self,
        sequence: int,
        *,
        supporting_paths: Sequence[str],
        supporting_groups: Sequence[str],
        ordering_authority: OrderingAuthority,
    ) -> ConversationEvent:
        # Path-specific metadata and corroboration lists remain in the Alpha→Omega
        # tables. Keeping them out of the FFCL event makes the canonical event stable
        # when a second path corroborates the same source event after the first append.
        metadata = {
            "alpha_omega_capture": True,
            "conversation_stream": self.stream.value,
            "source_global_sequence": self.global_sequence,
            "source_stream_sequence": self.stream_sequence,
            "ordering_authority": ordering_authority.value,
            "observation_identity_key": self.identity_key(),
            "observation_payload_hash": self.payload_hash(),
            "provenance_location": "AO_CAPTURE_CANDIDATES_AND_CANONICAL_TABLES",
        }
        return ConversationEvent(
            conversation_key=self.conversation_key.strip(),
            sequence=int(sequence),
            role=self.role,
            event_type=self.event_type,
            content=self.content,
            occurred_at=self.occurred_at,
            source_turn_id=self.source_turn_id,
            provider_event_id=self.provider_event_id,
            idempotency_key=f"ao:{self.conversation_key.strip()}:{self.identity_key()}",
            execution_state=self.execution_state,
            payload_availability=self.payload_availability,
            sensitivity=self.sensitivity,
            artifacts=self.artifacts,
            metadata=metadata,
        )


@dataclass(frozen=True)
class StreamExpectation:
    stream: ConversationStream
    expected_first_sequence: int
    expected_last_sequence: int
    required: bool = True
    allow_empty: bool = False

    def __post_init__(self) -> None:
        if self.expected_first_sequence < 1:
            raise ValueError("expected_first_sequence must be >= 1")
        if self.expected_last_sequence < self.expected_first_sequence:
            raise ValueError("expected_last_sequence cannot precede expected_first_sequence")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stream": self.stream.value,
            "expected_first_sequence": int(self.expected_first_sequence),
            "expected_last_sequence": int(self.expected_last_sequence),
            "required": bool(self.required),
            "allow_empty": bool(self.allow_empty),
        }


@dataclass(frozen=True)
class ReplayChunk:
    chunk_id: str
    first_sequence: int
    last_sequence: int
    estimated_tokens: int
    payload: Tuple[Dict[str, Any], ...]
    chunk_sha256: str
    continues_event: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
            "estimated_tokens": self.estimated_tokens,
            "payload": [dict(item) for item in self.payload],
            "chunk_sha256": self.chunk_sha256,
            "continues_event": self.continues_event,
        }


def _now() -> float:
    return time.time()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _key(value: str, label: str) -> str:
    result = value.strip()
    if not result:
        raise ValueError(f"{label} cannot be blank")
    return result


def _namespace(value: str) -> str:
    return _key(value, "namespace_key").casefold()


def _missing_ranges(
    sequences: Sequence[int],
    expected_first: int,
    expected_last: int,
) -> List[Dict[str, int]]:
    present = set(int(item) for item in sequences)
    missing: List[Dict[str, int]] = []
    start: Optional[int] = None
    for number in range(expected_first, expected_last + 1):
        if number not in present and start is None:
            start = number
        elif number in present and start is not None:
            missing.append({"start": start, "end": number - 1})
            start = None
    if start is not None:
        missing.append({"start": start, "end": expected_last})
    return missing

