from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


def infer_architecture_family(model: str, metadata: dict[str, Any] | None = None) -> str:
    """Return a conservative ASR architecture family.

    Different checkpoints or implementations from the same underlying model
    family must not be counted as independent recognisers. Unknown models all
    map to ``unknown`` until explicitly classified.
    """
    metadata = metadata or {}
    explicit = str(metadata.get("architecture_family", "")).strip()
    if explicit:
        return explicit
    value = model.lower()
    if "parakeet" in value or "nemo" in value:
        return "nvidia_parakeet_tdt"
    if "gpt-4o" in value or "openai" in value:
        return "openai_gpt4o_asr"
    if "chirp" in value or "google_speech" in value or "speech_v2" in value:
        return "google_chirp"
    if "gemini" in value:
        return "gemini_audio"
    if "whisper" in value:
        return "whisper_encoder_decoder"
    return "unknown"


@dataclass(frozen=True)
class WordHypothesis:
    text: str
    start: float | None = None
    end: float | None = None
    confidence: float = 1.0
    speaker: str | None = None
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TranscriptHypothesis:
    model: str
    words: tuple[WordHypothesis, ...]
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def architecture_family(self) -> str:
        return infer_architecture_family(self.model, self.metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "architecture_family": self.architecture_family,
            "weight": self.weight,
            "metadata": self.metadata,
            "words": [word.to_dict() for word in self.words],
        }


@dataclass(frozen=True)
class ConsensusWord:
    text: str
    start: float | None
    end: float | None
    speaker: str | None
    agreement: float
    alternatives: tuple[tuple[str, float], ...]
    sources: tuple[str, ...]
    architecture_families: tuple[str, ...]
    needs_review: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Correction:
    kind: str
    before: str
    after: str
    reason: str
    index: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
