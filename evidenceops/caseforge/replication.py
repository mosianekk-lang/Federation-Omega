from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


class ReplicationProofError(ValueError):
    """Raised when claimed independent replication is not evidence-supported."""


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class ReplicationRun:
    run_id: str
    case_id: str
    blind_input_sha256: str
    tested_output_sha256: str
    provider: str
    model: str
    model_version_ref: str
    configuration_sha256: str
    execution_route_id: str
    provider_readback_ref: str
    provider_verified: bool
    external_effect: bool = False

    def validate(self) -> "ReplicationRun":
        required = {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "blind_input_sha256": self.blind_input_sha256,
            "tested_output_sha256": self.tested_output_sha256,
            "provider": self.provider,
            "model": self.model,
            "model_version_ref": self.model_version_ref,
            "configuration_sha256": self.configuration_sha256,
            "execution_route_id": self.execution_route_id,
            "provider_readback_ref": self.provider_readback_ref,
        }
        missing = sorted(key for key, value in required.items() if not str(value).strip())
        if missing:
            raise ReplicationProofError("replication run missing: " + ",".join(missing))
        for name, value in (
            ("blind_input_sha256", self.blind_input_sha256),
            ("tested_output_sha256", self.tested_output_sha256),
            ("configuration_sha256", self.configuration_sha256),
        ):
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value.lower()):
                raise ReplicationProofError(f"{name} must be a SHA-256")
        if not self.provider_verified:
            raise ReplicationProofError("replication requires provider-verified execution")
        if self.external_effect:
            raise ReplicationProofError("replication run must remain A1_INTERNAL/no-external-effect")
        return self


@dataclass(frozen=True)
class ReplicationDecision:
    case_id: str
    blind_input_sha256: str
    primary_run_id: str
    replication_run_id: str
    independent: bool
    independence_dimensions: tuple[str, ...]
    reason_codes: tuple[str, ...]
    replication_pair_sha256: str
    external_effect: bool = False


class IndependentReplicationGate:
    """Prove that two provider-verified blind runs are materially independent.

    Different provider is independently sufficient. Within one provider, both the
    provider-visible model-version reference and execution route must differ. This
    gate proves execution independence only; agreement/correctness remains the
    scorer's job and is not inferred from matching output hashes.
    """

    def evaluate(self, primary: ReplicationRun, replication: ReplicationRun) -> ReplicationDecision:
        primary.validate()
        replication.validate()
        reasons: list[str] = []

        if primary.run_id == replication.run_id:
            reasons.append("RUN_ID_MUST_DIFFER")
        if primary.case_id != replication.case_id:
            reasons.append("CASE_ID_MISMATCH")
        if primary.blind_input_sha256 != replication.blind_input_sha256:
            reasons.append("BLIND_INPUT_MISMATCH")

        dimensions: list[str] = []
        if primary.provider != replication.provider:
            dimensions.append("PROVIDER")
        if (
            primary.model != replication.model
            or primary.model_version_ref != replication.model_version_ref
        ):
            dimensions.append("MODEL_VERSION")
        if primary.execution_route_id != replication.execution_route_id:
            dimensions.append("EXECUTION_ROUTE")

        materially_independent = (
            "PROVIDER" in dimensions
            or {"MODEL_VERSION", "EXECUTION_ROUTE"}.issubset(dimensions)
        )
        if not materially_independent:
            reasons.append("MATERIAL_INDEPENDENCE_NOT_PROVEN")

        independent = not reasons
        pair_payload = {
            "case_id": primary.case_id,
            "blind_input_sha256": primary.blind_input_sha256,
            "primary_run_id": primary.run_id,
            "replication_run_id": replication.run_id,
            "primary_provider": primary.provider,
            "replication_provider": replication.provider,
            "primary_model_version_ref": primary.model_version_ref,
            "replication_model_version_ref": replication.model_version_ref,
            "primary_execution_route_id": primary.execution_route_id,
            "replication_execution_route_id": replication.execution_route_id,
            "independence_dimensions": dimensions,
            "reason_codes": reasons,
        }
        return ReplicationDecision(
            case_id=primary.case_id,
            blind_input_sha256=primary.blind_input_sha256,
            primary_run_id=primary.run_id,
            replication_run_id=replication.run_id,
            independent=independent,
            independence_dimensions=tuple(dimensions),
            reason_codes=tuple(reasons),
            replication_pair_sha256=_digest(pair_payload),
        )


__all__ = [
    "IndependentReplicationGate",
    "ReplicationDecision",
    "ReplicationProofError",
    "ReplicationRun",
]
