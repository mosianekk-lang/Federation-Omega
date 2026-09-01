from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class DistilledEvidence:
    evidence_id: str
    source_ref: str
    evidence_kind: str
    content_sha256: str
    byte_size: int
    excerpt: str | None
    metadata: Mapping[str, Any]
    sensitive: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source_ref": self.source_ref,
            "evidence_kind": self.evidence_kind,
            "content_sha256": self.content_sha256,
            "byte_size": self.byte_size,
            "excerpt": self.excerpt,
            "metadata": dict(self.metadata),
            "sensitive": self.sensitive,
            "raw_content_embedded": False,
        }


class EvidenceDistiller:
    """Projects high-volume evidence into compact, content-addressed receipts.

    Raw evidence remains at its authoritative source or immutable evidence store.
    Chat/control-plane payloads carry only hashes, bounded excerpts, metadata and
    source pointers unless an explicit downstream reader requests the full body.
    """

    def __init__(self, *, max_excerpt_chars: int = 512):
        if max_excerpt_chars < 0 or max_excerpt_chars > 4096:
            raise ValueError("max_excerpt_chars must be between 0 and 4096")
        self.max_excerpt_chars = int(max_excerpt_chars)

    def distill(
        self,
        *,
        evidence_id: str,
        source_ref: str,
        evidence_kind: str,
        raw: str | bytes,
        metadata: Mapping[str, Any] | None = None,
        sensitive: bool = False,
    ) -> DistilledEvidence:
        if not evidence_id.strip() or not source_ref.strip() or not evidence_kind.strip():
            raise ValueError("evidence_id, source_ref and evidence_kind are required")
        raw_bytes = raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)
        if isinstance(raw, str) and not sensitive and self.max_excerpt_chars:
            excerpt = raw[: self.max_excerpt_chars]
        else:
            excerpt = None
        return DistilledEvidence(
            evidence_id=evidence_id,
            source_ref=source_ref,
            evidence_kind=evidence_kind,
            content_sha256=_sha(raw_bytes),
            byte_size=len(raw_bytes),
            excerpt=excerpt,
            metadata=dict(metadata or {}),
            sensitive=bool(sensitive),
        )

    @staticmethod
    def bundle(items: Sequence[DistilledEvidence]) -> dict[str, Any]:
        ordered = sorted((item.to_dict() for item in items), key=lambda item: item["evidence_id"])
        root = _sha(_stable_json(ordered).encode("utf-8"))
        return {
            "schema": "SLOS_DISTILLED_EVIDENCE_BUNDLE_V1",
            "evidence_count": len(ordered),
            "items": ordered,
            "bundle_sha256": root,
            "raw_content_embedded": False,
        }


__all__ = ["DistilledEvidence", "EvidenceDistiller"]
