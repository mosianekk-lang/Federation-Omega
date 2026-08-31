from __future__ import annotations

"""Fail-closed owner-value and provider-deployment proof court.

The court evaluates receipts only. It never deploys, invokes providers, grants
authority, merges a branch, or enables stable promotion.
"""

from argparse import ArgumentParser
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "SLOS-OWNER-VALUE-DEPLOYMENT-COURT-V1"
OWNER_VALUE_MODE = "OBSERVED_OWNER_VALUE"
INTERNAL_RUNTIME_MODE = "INTERNAL_RUNTIME_QUALIFICATION"
LIVE_DEPLOYMENT_MODE = "LIVE_PROVIDER_DEPLOYMENT"
MINIMUM_OWNER_VALUE_PAIRS = 5


def canonical_hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode()).hexdigest()


def _is_sha(value: str) -> bool:
    return len(value) == 40 and all(character in "0123456789abcdef" for character in value.lower())


def _is_digest(value: str) -> bool:
    prefix, separator, digest = value.partition(":")
    return separator == ":" and prefix == "sha256" and len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest.lower()
    )


@dataclass(frozen=True)
class OwnerValueObservation:
    pair_id: str
    mission_class: str
    source_head_sha: str
    evidence_mode: str
    baseline_owner_minutes: float
    candidate_owner_minutes: float
    baseline_owner_interventions: int
    candidate_owner_interventions: int
    baseline_verified_output_ratio: float
    candidate_verified_output_ratio: float
    baseline_elapsed_seconds: float
    candidate_elapsed_seconds: float
    independent_readback: bool
    proof_refs: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "OwnerValueObservation":
        return cls(
            pair_id=str(value.get("pair_id") or ""), mission_class=str(value.get("mission_class") or ""),
            source_head_sha=str(value.get("source_head_sha") or ""), evidence_mode=str(value.get("evidence_mode") or ""),
            baseline_owner_minutes=float(value.get("baseline_owner_minutes") or 0), candidate_owner_minutes=float(value.get("candidate_owner_minutes") or 0),
            baseline_owner_interventions=int(value.get("baseline_owner_interventions") or 0), candidate_owner_interventions=int(value.get("candidate_owner_interventions") or 0),
            baseline_verified_output_ratio=float(value.get("baseline_verified_output_ratio") or 0), candidate_verified_output_ratio=float(value.get("candidate_verified_output_ratio") or 0),
            baseline_elapsed_seconds=float(value.get("baseline_elapsed_seconds") or 0), candidate_elapsed_seconds=float(value.get("candidate_elapsed_seconds") or 0),
            independent_readback=value.get("independent_readback") is True,
            proof_refs=tuple(str(item) for item in value.get("proof_refs") or ()),
        )

    def failures(self, source_head_sha: str) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.pair_id or not self.mission_class: failures.append("OWNER_VALUE_IDENTITY_REQUIRED")
        if self.source_head_sha != source_head_sha: failures.append("OWNER_VALUE_SOURCE_HEAD_MISMATCH")
        if self.evidence_mode != OWNER_VALUE_MODE: failures.append("OWNER_VALUE_EVIDENCE_MODE_INVALID")
        if self.baseline_owner_minutes <= 0 or self.candidate_owner_minutes < 0: failures.append("OWNER_VALUE_MINUTES_INVALID")
        if self.baseline_elapsed_seconds <= 0 or self.candidate_elapsed_seconds <= 0: failures.append("OWNER_VALUE_ELAPSED_INVALID")
        if not 0 < self.baseline_verified_output_ratio <= 1: failures.append("OWNER_VALUE_BASELINE_RATIO_INVALID")
        if not 0 < self.candidate_verified_output_ratio <= 1: failures.append("OWNER_VALUE_CANDIDATE_RATIO_INVALID")
        if self.candidate_verified_output_ratio < self.baseline_verified_output_ratio: failures.append("OWNER_VALUE_OUTPUT_RATIO_REGRESSION")
        if self.candidate_owner_minutes >= self.baseline_owner_minutes: failures.append("OWNER_VALUE_MINUTES_NOT_IMPROVED")
        if self.candidate_owner_interventions > self.baseline_owner_interventions: failures.append("OWNER_VALUE_INTERVENTION_REGRESSION")
        if self.candidate_elapsed_seconds > self.baseline_elapsed_seconds: failures.append("OWNER_VALUE_LATENCY_REGRESSION")
        if not self.independent_readback: failures.append("OWNER_VALUE_INDEPENDENT_READBACK_REQUIRED")
        if len(self.proof_refs) < 2: failures.append("OWNER_VALUE_PROOF_REFS_INCOMPLETE")
        return tuple(failures)


@dataclass(frozen=True)
class RuntimeOrDeploymentEvidence:
    evidence_id: str
    source_head_sha: str
    evidence_mode: str
    environment: str
    image_digest: str
    revision_id: str
    provider_registration_verified: bool
    workload_identity_verified: bool
    health_readback_verified: bool
    rollback_verified: bool
    deployment_observed: bool
    independent_readback: bool
    provider_effect_authorized: bool
    proof_refs: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeOrDeploymentEvidence":
        return cls(
            evidence_id=str(value.get("evidence_id") or ""), source_head_sha=str(value.get("source_head_sha") or ""),
            evidence_mode=str(value.get("evidence_mode") or ""), environment=str(value.get("environment") or ""),
            image_digest=str(value.get("image_digest") or ""), revision_id=str(value.get("revision_id") or ""),
            provider_registration_verified=value.get("provider_registration_verified") is True,
            workload_identity_verified=value.get("workload_identity_verified") is True,
            health_readback_verified=value.get("health_readback_verified") is True,
            rollback_verified=value.get("rollback_verified") is True,
            deployment_observed=value.get("deployment_observed") is True,
            independent_readback=value.get("independent_readback") is True,
            provider_effect_authorized=value.get("provider_effect_authorized") is True,
            proof_refs=tuple(str(item) for item in value.get("proof_refs") or ()),
        )

    def internal_failures(self, source_head_sha: str) -> tuple[str, ...]:
        failures: list[str] = []
        if self.evidence_mode != INTERNAL_RUNTIME_MODE: return ("INTERNAL_RUNTIME_EVIDENCE_MODE_INVALID",)
        if self.source_head_sha != source_head_sha: failures.append("INTERNAL_RUNTIME_SOURCE_HEAD_MISMATCH")
        if not self.evidence_id or not _is_digest(self.image_digest): failures.append("INTERNAL_RUNTIME_IDENTITY_OR_IMAGE_DIGEST_INVALID")
        if not self.health_readback_verified: failures.append("INTERNAL_RUNTIME_HEALTH_UNPROVEN")
        if not self.rollback_verified: failures.append("INTERNAL_RUNTIME_ROLLBACK_UNPROVEN")
        if not self.independent_readback or len(self.proof_refs) < 2: failures.append("INTERNAL_RUNTIME_READBACK_OR_PROOF_INCOMPLETE")
        if self.provider_effect_authorized: failures.append("INTERNAL_RUNTIME_PROVIDER_EFFECT_MUST_BE_FALSE")
        return tuple(failures)

    def deployment_failures(self, source_head_sha: str) -> tuple[str, ...]:
        failures: list[str] = []
        if self.evidence_mode != LIVE_DEPLOYMENT_MODE: return ("LIVE_DEPLOYMENT_EVIDENCE_MODE_INVALID",)
        if self.source_head_sha != source_head_sha: failures.append("LIVE_DEPLOYMENT_SOURCE_HEAD_MISMATCH")
        if not self.evidence_id or not self.environment or not self.revision_id or not _is_digest(self.image_digest): failures.append("LIVE_DEPLOYMENT_IDENTITY_INCOMPLETE")
        if not self.provider_registration_verified: failures.append("PROVIDER_REGISTRATION_UNPROVEN")
        if not self.workload_identity_verified: failures.append("WORKLOAD_IDENTITY_UNPROVEN")
        if not self.health_readback_verified: failures.append("LIVE_HEALTH_READBACK_UNPROVEN")
        if not self.rollback_verified: failures.append("LIVE_ROLLBACK_UNPROVEN")
        if not self.deployment_observed: failures.append("LIVE_DEPLOYMENT_OBSERVATION_UNPROVEN")
        if not self.independent_readback or len(self.proof_refs) < 3: failures.append("LIVE_DEPLOYMENT_READBACK_OR_PROOF_INCOMPLETE")
        if not self.provider_effect_authorized: failures.append("LIVE_DEPLOYMENT_AUTHORITY_RECEIPT_UNPROVEN")
        return tuple(failures)


@dataclass(frozen=True)
class ProofCourtReceipt:
    schema: str
    source_head_sha: str
    candidate_id: str
    observed_empirical_pair_count: int
    owner_value_pair_count: int
    owner_value_proven: bool
    internal_runtime_qualified: bool
    provider_deployment_proven: bool
    decision: str
    blockers: tuple[str, ...]
    stable_promotion_authorized: bool
    effect_authorized: bool
    external_effect: bool
    next_gate: str
    truth_boundary: tuple[str, ...]
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]: return asdict(self)


def evaluate_proof_court(*, candidate_receipt: Mapping[str, Any], source_head_sha: str,
                         owner_value_observations: Sequence[Mapping[str, Any]] = (),
                         runtime_or_deployment_evidence: Sequence[Mapping[str, Any]] = ()) -> ProofCourtReceipt:
    if not _is_sha(source_head_sha): raise ValueError("COURT_SOURCE_HEAD_SHA_REQUIRED")
    manifest = candidate_receipt.get("candidate_manifest") or {}
    assurance = candidate_receipt.get("assurance") or {}
    if candidate_receipt.get("status") != "CANDIDATE_EMPIRICAL_GATE_ASSURED_NO_PROMOTION": raise ValueError("CANDIDATE_STATUS_REJECTED")
    if candidate_receipt.get("provider_disabled") is not True or candidate_receipt.get("external_effect") is not False: raise ValueError("CANDIDATE_PROVIDER_OR_EFFECT_BOUNDARY_REJECTED")
    if manifest.get("source_head_sha") != source_head_sha: raise ValueError("CANDIDATE_SOURCE_HEAD_MISMATCH")
    if manifest.get("empirical_gate_satisfied") is not True or int(manifest.get("observed_pair_count") or 0) != 30: raise ValueError("CANDIDATE_EMPIRICAL_GATE_UNPROVEN")
    if manifest.get("stable_promotion_authorized") is not False: raise ValueError("CANDIDATE_STABLE_PROMOTION_MUST_BE_FALSE")
    if assurance.get("decision") != "EMPIRICAL_GATE_SATISFIED_NO_PROMOTION": raise ValueError("CANDIDATE_ASSURANCE_DECISION_REJECTED")

    blockers: set[str] = set()
    owner_items = tuple(OwnerValueObservation.from_mapping(item) for item in owner_value_observations)
    if len(owner_items) < MINIMUM_OWNER_VALUE_PAIRS: blockers.add("OWNER_VALUE_MINIMUM_FIVE_OBSERVED_PAIRS_REQUIRED")
    if len({item.pair_id for item in owner_items}) != len(owner_items): blockers.add("OWNER_VALUE_PAIR_IDS_MUST_BE_UNIQUE")
    for item in owner_items: blockers.update(item.failures(source_head_sha))
    owner_value_proven = len(owner_items) >= MINIMUM_OWNER_VALUE_PAIRS and not any(code.startswith("OWNER_VALUE_") for code in blockers)

    evidence = tuple(RuntimeOrDeploymentEvidence.from_mapping(item) for item in runtime_or_deployment_evidence)
    internal_items = tuple(item for item in evidence if item.evidence_mode == INTERNAL_RUNTIME_MODE)
    live_items = tuple(item for item in evidence if item.evidence_mode == LIVE_DEPLOYMENT_MODE)
    internal_runtime_qualified = False
    for item in internal_items:
        failures = item.internal_failures(source_head_sha); blockers.update(failures)
        internal_runtime_qualified = internal_runtime_qualified or not failures
    if not internal_items: blockers.add("EXACT_HEAD_INTERNAL_RUNTIME_QUALIFICATION_REQUIRED")
    provider_deployment_proven = False
    for item in live_items:
        failures = item.deployment_failures(source_head_sha); blockers.update(failures)
        provider_deployment_proven = provider_deployment_proven or not failures
    if not live_items: blockers.add("LIVE_PROVIDER_DEPLOYMENT_EVIDENCE_REQUIRED")

    ready = owner_value_proven and internal_runtime_qualified and provider_deployment_proven
    payload = {
        "schema": SCHEMA, "source_head_sha": source_head_sha, "candidate_id": str(manifest.get("candidate_id") or ""),
        "observed_empirical_pair_count": 30, "owner_value_pair_count": len(owner_items), "owner_value_proven": owner_value_proven,
        "internal_runtime_qualified": internal_runtime_qualified, "provider_deployment_proven": provider_deployment_proven,
        "decision": "OWNER_VALUE_AND_DEPLOYMENT_PROOF_SATISFIED_PROMOTION_REVIEW_REQUIRED" if ready else "HOLD_NO_PROMOTION",
        "blockers": tuple(sorted(blockers)), "stable_promotion_authorized": False, "effect_authorized": False, "external_effect": False,
        "next_gate": "SEPARATE_OWNER_PROMOTION_REVIEW" if ready else "COLLECT_TYPED_OWNER_VALUE_AND_LIVE_DEPLOYMENT_EVIDENCE",
        "truth_boundary": (
            "Thirty OBSERVED empirical pairs do not prove measured owner value.",
            "Internal container/runtime qualification does not prove provider deployment.",
            "This court evaluates supplied receipts and grants no deployment, provider, merge, or promotion authority.",
        ),
    }
    return ProofCourtReceipt(**payload, receipt_sha256=canonical_hash(payload))


def main() -> int:
    parser = ArgumentParser()
    parser.add_argument("--candidate-receipt", type=Path, required=True); parser.add_argument("--source-head-sha", required=True)
    parser.add_argument("--owner-value-receipt", type=Path); parser.add_argument("--deployment-receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    candidate = json.loads(args.candidate_receipt.read_text(encoding="utf-8"))
    owner = json.loads(args.owner_value_receipt.read_text(encoding="utf-8")) if args.owner_value_receipt else []
    deployment = json.loads(args.deployment_receipt.read_text(encoding="utf-8")) if args.deployment_receipt else []
    receipt = evaluate_proof_court(candidate_receipt=candidate, source_head_sha=args.source_head_sha,
                                   owner_value_observations=owner, runtime_or_deployment_evidence=deployment).to_dict()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
