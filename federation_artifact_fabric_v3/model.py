"""Typed contracts for Federation Artifact Fabric v3.

The module is provider-neutral.  Exact Drive IDs, credentials, signing keys and
private runtime identifiers belong to an authorised private adapter, never the
public source core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class FabricError(RuntimeError):
    """Base class for fail-closed Artifact Fabric failures."""


class InvalidTransition(FabricError):
    """Raised when a transaction attempts an illegal state transition."""


class IdempotencyCollision(FabricError):
    """Raised when one idempotency key is reused for different artifact facts."""


class TemporaryProviderError(FabricError):
    """Retryable storage, projection or signer failure."""


class PermanentProviderError(FabricError):
    """Non-retryable provider failure."""


class ScanViolation(FabricError):
    """Artifact failed a security, format, archive or privacy inspection."""


class TransactionState(StrEnum):
    RECEIVED = "RECEIVED"
    QUARANTINED = "QUARANTINED"
    VALIDATED = "VALIDATED"
    DRIVE_WRITE_PENDING = "DRIVE_WRITE_PENDING"
    DRIVE_WRITTEN = "DRIVE_WRITTEN"
    READBACK_VERIFIED = "READBACK_VERIFIED"
    REGISTRY_COMMITTED = "REGISTRY_COMMITTED"
    RECEIPT_SIGNED = "RECEIPT_SIGNED"
    DELIVERED = "DELIVERED"
    HOLD = "HOLD"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


TERMINAL_STATES = frozenset(
    {TransactionState.DELIVERED, TransactionState.FAILED, TransactionState.DEAD_LETTER}
)


FORWARD_TRANSITIONS: Mapping[TransactionState, frozenset[TransactionState]] = {
    TransactionState.RECEIVED: frozenset(
        {TransactionState.QUARANTINED, TransactionState.HOLD, TransactionState.FAILED}
    ),
    TransactionState.QUARANTINED: frozenset(
        {TransactionState.VALIDATED, TransactionState.HOLD, TransactionState.FAILED}
    ),
    TransactionState.VALIDATED: frozenset(
        {
            TransactionState.DRIVE_WRITE_PENDING,
            TransactionState.HOLD,
            TransactionState.FAILED,
        }
    ),
    TransactionState.DRIVE_WRITE_PENDING: frozenset(
        {TransactionState.DRIVE_WRITTEN, TransactionState.HOLD, TransactionState.FAILED}
    ),
    TransactionState.DRIVE_WRITTEN: frozenset(
        {
            TransactionState.READBACK_VERIFIED,
            TransactionState.HOLD,
            TransactionState.FAILED,
        }
    ),
    TransactionState.READBACK_VERIFIED: frozenset(
        {
            TransactionState.REGISTRY_COMMITTED,
            TransactionState.HOLD,
            TransactionState.FAILED,
        }
    ),
    TransactionState.REGISTRY_COMMITTED: frozenset(
        {TransactionState.RECEIPT_SIGNED, TransactionState.HOLD, TransactionState.FAILED}
    ),
    TransactionState.RECEIPT_SIGNED: frozenset(
        {TransactionState.DELIVERED, TransactionState.HOLD, TransactionState.FAILED}
    ),
    TransactionState.DELIVERED: frozenset(),
    TransactionState.HOLD: frozenset(),
    TransactionState.FAILED: frozenset(),
    TransactionState.DEAD_LETTER: frozenset(),
}


class RetentionClass(StrEnum):
    EVIDENCE_IMMUTABLE = "EVIDENCE_IMMUTABLE"
    CANONICAL = "CANONICAL"
    OPERATIONAL = "OPERATIONAL"
    DRAFT = "DRAFT"
    TEMPORARY = "TEMPORARY"
    QUARANTINED = "QUARANTINED"


class SensitivityClass(StrEnum):
    PUBLIC_SAFE = "PUBLIC_SAFE"
    PRIVATE = "PRIVATE"
    RESTRICTED = "RESTRICTED"
    SECRET_REFERENCE_ONLY = "SECRET_REFERENCE_ONLY"


@dataclass(frozen=True)
class ArtifactRequest:
    artifact_name: str
    content: bytes
    media_type: str
    workstream: str
    version: str
    destination_alias: str
    retention_class: RetentionClass = RetentionClass.CANONICAL
    sensitivity: SensitivityClass = SensitivityClass.PRIVATE
    source_ref: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScanReport:
    passed: bool
    sha256: str
    size_bytes: int
    detected_media_type: str
    findings: tuple[str, ...]
    archive_entries: int = 0
    archive_uncompressed_bytes: int = 0
    scanner_version: str = "FAF3-SCANNER-1"


@dataclass(frozen=True)
class ProviderObject:
    object_id: str
    object_name: str
    parent_ref: str
    media_type: str
    size_bytes: int
    sha256: str
    url: str = ""
    revision: str = ""
    created_new: bool = True


@dataclass(frozen=True)
class ProviderReadback:
    object_id: str
    object_name: str
    parent_ref: str
    media_type: str
    size_bytes: int
    sha256: str
    shared: bool
    revision: str = ""
    trashed: bool = False


@dataclass(frozen=True)
class ProjectionReadback:
    transaction_id: str
    idempotency_key: str
    object_id: str
    sha256: str
    status: str


@dataclass(frozen=True)
class SignatureEnvelope:
    algorithm: str
    signer_id: str
    key_reference: str
    signature: str
    signed_payload_sha256: str


@dataclass(frozen=True)
class DeliveryOutcome:
    transaction_id: str
    idempotency_key: str
    state: TransactionState
    receipt: Mapping[str, Any] | None
    reused_existing: bool = False
    reason: str = ""


@dataclass(frozen=True)
class DriftFinding:
    transaction_id: str
    code: str
    severity: str
    expected: str
    observed: str
    repairable: bool


def ensure_transition_allowed(
    current: TransactionState,
    target: TransactionState,
) -> None:
    if target not in FORWARD_TRANSITIONS[current]:
        raise InvalidTransition(f"illegal Artifact Fabric transition: {current} -> {target}")
