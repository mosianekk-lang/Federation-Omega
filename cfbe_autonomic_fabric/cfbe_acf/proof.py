from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any, Callable, Mapping

from .models import PROOF_ORDER, ProofStage
from .util import (
    digest_json,
    parse_utc,
    reject_sensitive,
    require_bool,
    require_int,
    require_nonempty,
    utc_now,
)


_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ProofKernel:
    """Verify evidence-bound receipts attested by configured verifier identities."""

    def __init__(
        self,
        *,
        trusted_verifiers: Mapping[str, bytes],
        evidence_resolver: Callable[[str], str],
    ):
        if not trusted_verifiers:
            raise ValueError("at least one trusted verifier required")
        if any(len(key) < 32 for key in trusted_verifiers.values()):
            raise ValueError("verifier keys must contain at least 256 bits")
        self._trusted_verifiers = dict(trusted_verifiers)
        self._evidence_resolver = evidence_resolver

    def create_receipt(
        self,
        *,
        receipt_id: str,
        mission_id: str,
        mission_version: int,
        action_id: str,
        provider_id: str,
        from_stage: str,
        to_stage: str,
        evidence_ref: str,
        evidence_hash: str,
        previous_receipt_hash: str,
        producer: str,
        semantic_passed: bool,
        rollback_tested: bool = False,
        replay_tested: bool = False,
        soak_seconds: int = 0,
        sample_count: int = 0,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        receipt = {
            "schema": "CFBE-ACF-PROOF-RECEIPT-V2",
            "receipt_id": str(require_nonempty(receipt_id, "receipt_id")),
            "mission_id": str(require_nonempty(mission_id, "mission_id")),
            "mission_version": require_int(mission_version, "mission_version", minimum=1),
            "action_id": str(require_nonempty(action_id, "action_id")),
            "provider_id": str(require_nonempty(provider_id, "provider_id")),
            "from_stage": ProofStage(from_stage).value,
            "to_stage": ProofStage(to_stage).value,
            "evidence_ref": str(require_nonempty(evidence_ref, "evidence_ref")),
            "evidence_hash": evidence_hash,
            "previous_receipt_hash": previous_receipt_hash,
            "producer": str(require_nonempty(producer, "producer")),
            "semantic_passed": require_bool(semantic_passed, "semantic_passed"),
            "rollback_tested": require_bool(rollback_tested, "rollback_tested"),
            "replay_tested": require_bool(replay_tested, "replay_tested"),
            "soak_seconds": require_int(soak_seconds, "soak_seconds"),
            "sample_count": require_int(sample_count, "sample_count"),
            "observed_at": observed_at or utc_now(),
        }
        reject_sensitive(receipt)
        for field in ("evidence_hash", "previous_receipt_hash"):
            if not _HEX64.fullmatch(str(receipt[field])):
                raise ValueError(f"{field} must be sha256 hex")
        parse_utc(receipt["observed_at"])
        return receipt

    @staticmethod
    def attest(receipt: Mapping[str, Any], *, verifier: str, verifier_key: bytes) -> dict[str, Any]:
        if len(verifier_key) < 32:
            raise ValueError("verifier key must contain at least 256 bits")
        value = dict(receipt)
        value["verifier"] = str(require_nonempty(verifier, "verifier"))
        body_hash = digest_json(value)
        value["body_hash"] = body_hash
        value["attestation"] = hmac.new(
            verifier_key, body_hash.encode("ascii"), hashlib.sha256
        ).hexdigest()
        return value

    def verify(self, receipt: dict[str, Any]) -> None:
        reject_sensitive(receipt)
        if receipt.get("schema") != "CFBE-ACF-PROOF-RECEIPT-V2":
            raise ValueError("unsupported receipt schema")
        verifier = str(receipt.get("verifier", ""))
        verifier_key = self._trusted_verifiers.get(verifier)
        if verifier_key is None:
            raise ValueError("untrusted verifier identity")
        if receipt.get("producer") == verifier:
            raise ValueError("independent verifier required")
        body = {
            key: value
            for key, value in receipt.items()
            if key not in {"body_hash", "attestation"}
        }
        body_hash = digest_json(body)
        if not hmac.compare_digest(str(receipt.get("body_hash", "")), body_hash):
            raise ValueError("receipt hash invalid")
        expected = hmac.new(verifier_key, body_hash.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(receipt.get("attestation", "")), expected):
            raise ValueError("receipt attestation invalid")
        for field in ("evidence_hash", "previous_receipt_hash"):
            if not _HEX64.fullmatch(str(receipt.get(field, ""))):
                raise ValueError(f"{field} must be sha256 hex")
        resolved = self._evidence_resolver(str(receipt.get("evidence_ref", "")))
        if resolved != receipt["evidence_hash"]:
            raise ValueError("evidence readback hash mismatch")
        parse_utc(str(receipt.get("observed_at", "")))
        require_int(receipt.get("mission_version"), "mission_version", minimum=1)
        for field in ("semantic_passed", "rollback_tested", "replay_tested"):
            require_bool(receipt.get(field), field)
        require_int(receipt.get("soak_seconds"), "soak_seconds")
        require_int(receipt.get("sample_count"), "sample_count")

    def promote(self, current_stage: str, receipt: dict[str, Any]) -> str:
        self.verify(receipt)
        current = ProofStage(current_stage)
        if ProofStage(receipt["from_stage"]) != current:
            raise ValueError("receipt from_stage mismatch")
        index = PROOF_ORDER.index(current)
        if index + 1 >= len(PROOF_ORDER) or ProofStage(receipt["to_stage"]) != PROOF_ORDER[index + 1]:
            raise ValueError("proof stages cannot be skipped")
        target = ProofStage(receipt["to_stage"])
        if target.value in {
            "TRANSPORT_PROVEN",
            "SEMANTICALLY_VERIFIED",
            "RECOVERY_VERIFIED",
            "SOAK_VERIFIED",
        } and not receipt["semantic_passed"]:
            raise ValueError("semantic proof required")
        if target == ProofStage.RECOVERY_VERIFIED and not (
            receipt["rollback_tested"] and receipt["replay_tested"]
        ):
            raise ValueError("rollback and replay proof required")
        if target == ProofStage.SOAK_VERIFIED and (
            receipt["soak_seconds"] < 3600 or receipt["sample_count"] < 10
        ):
            raise ValueError("sustained soak evidence insufficient")
        return target.value
