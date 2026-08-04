from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class OwnerDecisionReceipt:
    receipt_id: str
    owner_id: str
    gate: str
    evidence_id: str
    evidence_content_sha256: str
    decision: str
    issued_at: str
    expires_at: str
    provider: str
    locator: str
    provider_class: str
    nonce: str
    receipt_sha256: str = ""

    def unsigned_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("receipt_sha256", None)
        return payload

    def expected_sha256(self) -> str:
        return digest(self.unsigned_payload())

    def with_hash(self) -> "OwnerDecisionReceipt":
        payload = self.unsigned_payload()
        return OwnerDecisionReceipt(**payload, receipt_sha256=digest(payload))


@dataclass(frozen=True)
class OwnerDecisionValidation:
    valid: bool
    reasons: tuple[str, ...]
    receipt_id: str | None
    receipt_sha256: str | None


class OwnerAuthorityValidator:
    """Validate provider-backed owner decisions without accepting a caller-set boolean.

    The validator proves receipt integrity, exact evidence/gate binding, freshness,
    provider authority and one-time decision identity. It does not itself prove the
    external provider or the human identity; those remain provider-native evidence
    requirements represented by the authority register.
    """

    def __init__(
        self,
        receipts: dict[str, OwnerDecisionReceipt] | None = None,
        *,
        expected_owner_id: str = "Kim Kagiso Mosiane",
        authority_domain: str = "owner_decision",
    ) -> None:
        self.receipts = dict(receipts or {})
        self.expected_owner_id = expected_owner_id
        self.authority_domain = authority_domain

    def validate(
        self,
        *,
        receipt_id: str | None,
        gate: str,
        evidence_id: str,
        evidence_content_sha256: str,
        authority: dict[str, dict[str, Any]],
        now: str,
        consumed_by: dict[str, str] | None = None,
    ) -> OwnerDecisionValidation:
        reasons: list[str] = []
        if not receipt_id:
            return OwnerDecisionValidation(
                valid=False,
                reasons=("OWNER_DECISION_RECEIPT_REQUIRED",),
                receipt_id=None,
                receipt_sha256=None,
            )

        receipt = self.receipts.get(receipt_id)
        if receipt is None:
            return OwnerDecisionValidation(
                valid=False,
                reasons=("OWNER_DECISION_RECEIPT_NOT_FOUND",),
                receipt_id=receipt_id,
                receipt_sha256=None,
            )

        authority_state = authority.get(self.authority_domain, {}).get("state")
        if authority_state != "FRESH_VERIFIED":
            reasons.append(f"PROVIDER_AUTHORITY_NOT_VERIFIED:{self.authority_domain}")

        if receipt.owner_id != self.expected_owner_id:
            reasons.append("OWNER_ID_MISMATCH")
        if receipt.gate != gate:
            reasons.append("OWNER_DECISION_GATE_MISMATCH")
        if receipt.evidence_id != evidence_id:
            reasons.append("OWNER_DECISION_EVIDENCE_ID_MISMATCH")
        if receipt.evidence_content_sha256 != evidence_content_sha256:
            reasons.append("OWNER_DECISION_EVIDENCE_HASH_MISMATCH")
        if receipt.decision != "APPROVE":
            reasons.append("OWNER_DECISION_NOT_APPROVED")
        if receipt.provider_class != "OWNER_PROVIDER_NATIVE":
            reasons.append("OWNER_DECISION_NOT_PROVIDER_NATIVE")
        if not receipt.provider.strip() or not receipt.locator.strip():
            reasons.append("OWNER_DECISION_PROVIDER_LOCATOR_MISSING")
        if not receipt.nonce.strip():
            reasons.append("OWNER_DECISION_NONCE_MISSING")
        if receipt.receipt_sha256 != receipt.expected_sha256():
            reasons.append("OWNER_DECISION_RECEIPT_HASH_INVALID")

        try:
            issued = parse_utc(receipt.issued_at)
            expires = parse_utc(receipt.expires_at)
            current = parse_utc(now)
            if expires <= issued:
                reasons.append("OWNER_DECISION_EXPIRY_INVALID")
            if current < issued:
                reasons.append("OWNER_DECISION_FROM_FUTURE")
            if current > expires:
                reasons.append("OWNER_DECISION_EXPIRED")
            if (expires - issued).total_seconds() > 30 * 86400:
                reasons.append("OWNER_DECISION_VALIDITY_TOO_LONG")
        except (TypeError, ValueError):
            reasons.append("OWNER_DECISION_TIMESTAMP_INVALID")

        if consumed_by is not None:
            existing = consumed_by.get(receipt_id)
            if existing is not None and existing != evidence_id:
                reasons.append("OWNER_DECISION_RECEIPT_ALREADY_CONSUMED")

        return OwnerDecisionValidation(
            valid=not reasons,
            reasons=tuple(sorted(set(reasons))),
            receipt_id=receipt_id,
            receipt_sha256=receipt.receipt_sha256,
        )
