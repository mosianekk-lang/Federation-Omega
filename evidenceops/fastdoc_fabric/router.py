from __future__ import annotations

from dataclasses import dataclass
import string

from .models import PagePacket, ProcessingLane, RoutingDecision


@dataclass(frozen=True)
class RoutingPolicy:
    """Deterministic page-level route selection.

    Native text is always preferred when it is sufficiently populated and sane.
    OCR/layout work is selective. Vision is reserved for pages whose extracted text
    is both sparse and structurally suspicious.
    """

    min_native_chars: int = 80
    vision_garbled_threshold: float = 0.30
    vision_min_images: int = 2

    def text_quality(self, text: str) -> float:
        text = text.strip()
        if not text:
            return 0.0
        replacement = text.count("\ufffd") + text.count("<?>")
        printable = sum(ch in string.printable or ch.isprintable() for ch in text)
        printable_ratio = printable / max(len(text), 1)
        garbled_ratio = replacement / max(len(text), 1)
        return max(0.0, min(1.0, printable_ratio - garbled_ratio * 4.0))

    def route(self, packet: PagePacket) -> RoutingDecision:
        quality = self.text_quality(packet.text)
        reasons: list[str] = []
        if packet.text_chars >= self.min_native_chars and quality >= 0.80:
            reasons.append("SUFFICIENT_NATIVE_TEXT")
            return RoutingDecision(packet.page_number, ProcessingLane.NATIVE_FAST, quality, tuple(reasons))

        reasons.append("NATIVE_TEXT_SPARSE_OR_LOW_QUALITY")
        if packet.image_count >= self.vision_min_images and quality < self.vision_garbled_threshold:
            reasons.append("IMAGE_HEAVY_LOW_TEXT_CONFIDENCE")
            return RoutingDecision(packet.page_number, ProcessingLane.VISION_ESCALATION, quality, tuple(reasons))

        reasons.append("SELECTIVE_LAYOUT_OCR_REQUIRED")
        return RoutingDecision(packet.page_number, ProcessingLane.LAYOUT_OCR, quality, tuple(reasons))
