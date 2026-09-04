from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class ProcessingLane(str, Enum):
    NATIVE_FAST = "NATIVE_FAST"
    LAYOUT_OCR = "LAYOUT_OCR"
    VISION_ESCALATION = "VISION_ESCALATION"


@dataclass(frozen=True)
class PagePacket:
    page_number: int
    text: str
    block_count: int = 0
    image_count: int = 0
    extraction_ms: float = 0.0
    extractor: str = "unknown"
    extractor_version: str = "unknown"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def text_chars(self) -> int:
        return len(self.text.strip())


@dataclass(frozen=True)
class RoutingDecision:
    page_number: int
    lane: ProcessingLane
    quality_score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SearchHit:
    page_number: int
    score: float
    snippet: str


@dataclass(frozen=True)
class IngestReceipt:
    document_sha256: str
    page_count: int
    processed_pages: int
    cache_hits: int
    escalation_pages: tuple[int, ...]
    elapsed_seconds: float
    pages_per_second: float
    index_seconds: float
    extractor: str
    extractor_version: str
