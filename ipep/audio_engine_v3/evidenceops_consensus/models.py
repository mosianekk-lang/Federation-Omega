from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
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
