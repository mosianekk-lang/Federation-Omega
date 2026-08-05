from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

EvidenceClass = Literal["PRIMARY_SOURCE", "PRESERVATION_COPY", "DERIVATIVE", "OUTPUT", "RECEIPT"]
UnitState = Literal["EMITTED_SEGMENTS", "ZERO_SEGMENT", "FAILED"]
ReviewState = Literal[
    "UNREVIEWED",
    "HUMAN_LISTENED",
    "HUMAN_VERIFIED_SOURCE_TEXT",
    "HUMAN_VERIFIED_TRANSLATION",
    "REJECTED",
]


@dataclass(frozen=True)
class EvidenceItem:
    item_id: str
    evidence_class: EvidenceClass
    path: str
    sha256: str
    size_bytes: int
    created_at: str
    parent_item_ids: tuple[str, ...] = ()
    transformation: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CustodyEvent:
    event_id: str
    occurred_at: str
    actor: str
    action: str
    item_ids: tuple[str, ...]
    details: dict[str, Any]
    previous_event_hash: str | None
    event_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UnitReceipt:
    unit_id: str
    source_item_id: str
    source_sha256: str
    provider: str
    architecture_family: str
    start_seconds: float
    end_seconds: float
    state: UnitState
    segment_count: int
    raw_response_sha256: str | None
    command_receipt_sha256: str | None
    provider_exit_code: int | None
    created_at: str
    language: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TranscriptSegment:
    segment_id: str
    unit_id: str
    source_item_id: str
    start_seconds: float
    end_seconds: float
    original_text: str
    source_language: str
    provider: str
    architecture_family: str
    confidence: float | None = None
    speaker_label: str | None = None
    speaker_role: str | None = None
    word_timestamps_present: bool = False
    raw_response_sha256: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TranslationRecord:
    translation_id: str
    segment_id: str
    source_language: str
    target_language: str
    source_text_sha256: str
    translated_text: str
    provider: str
    model: str | None
    raw_response_sha256: str | None
    created_at: str
    review_state: ReviewState = "UNREVIEWED"
    reviewer: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HumanReview:
    review_id: str
    segment_id: str
    reviewer: str
    reviewed_at: str
    state: ReviewState
    verified_source_text: str | None
    verified_translation_text: str | None
    speaker_role_verified: bool
    legal_entities_verified: bool
    audio_window_item_id: str | None
    audio_window_sha256: str | None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QuoteRequest:
    segment_id: str
    quote_language: str
    supporting_architecture_families: tuple[str, ...]
    word_timestamps_present: bool
    speaker_role_supported: bool
    legal_entities_verified: bool
    human_listened: bool
    source_text_human_verified: bool
    translation_human_verified: bool
    audio_window_sha256: str | None
    certification_attestation_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
