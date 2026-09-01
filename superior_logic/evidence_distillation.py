from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class EvidenceReceipt:
    source_ref: str
    source_digest: str
    evidence_class: str
    verified_claims: tuple[str, ...]
    unresolved: tuple[str, ...]
    excerpt: str
    raw_size: int
    receipt_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "SLOS_EVIDENCE_RECEIPT_V1",
            "source_ref": self.source_ref,
            "source_digest": self.source_digest,
            "evidence_class": self.evidence_class,
            "verified_claims": list(self.verified_claims),
            "unresolved": list(self.unresolved),
            "excerpt": self.excerpt,
            "raw_size": self.raw_size,
            "receipt_digest": self.receipt_digest,
        }


class EvidenceDistiller:
    """Compress raw evidence into a hash-bound bounded control-plane receipt."""

    def distill(
        self,
        *,
        source_ref: str,
        raw: str,
        evidence_class: str,
        verified_claims: tuple[str, ...] = (),
        unresolved: tuple[str, ...] = (),
        excerpt_limit: int = 800,
    ) -> EvidenceReceipt:
        if not source_ref.strip() or not evidence_class.strip():
            raise ValueError("source_ref and evidence_class are required")
        raw_bytes = raw.encode("utf-8")
        source_digest = hashlib.sha256(raw_bytes).hexdigest()
        clean = " ".join(raw.split())
        excerpt = clean[: max(excerpt_limit, 0)]
        payload = {
            "source_ref": source_ref,
            "source_digest": source_digest,
            "evidence_class": evidence_class,
            "verified_claims": sorted(set(verified_claims)),
            "unresolved": sorted(set(unresolved)),
            "excerpt": excerpt,
            "raw_size": len(raw_bytes),
        }
        receipt_digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return EvidenceReceipt(
            source_ref=source_ref,
            source_digest=source_digest,
            evidence_class=evidence_class,
            verified_claims=tuple(payload["verified_claims"]),
            unresolved=tuple(payload["unresolved"]),
            excerpt=excerpt,
            raw_size=len(raw_bytes),
            receipt_digest=receipt_digest,
        )

    @staticmethod
    def verify(receipt: EvidenceReceipt, *, raw: str) -> bool:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest() == receipt.source_digest


__all__ = ["EvidenceDistiller", "EvidenceReceipt"]
