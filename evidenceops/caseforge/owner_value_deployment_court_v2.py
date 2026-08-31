from __future__ import annotations

"""Bubbles owner-value and deployment proof court v2.

This is a current-main successor to the owner-value/deployment court explored in
historical draft PR #876. It absorbs the useful matched-cohort controls from the
later Bubbles autonomy-value experiment rather than creating a second value
court.

The court evaluates supplied observations only. It never deploys, invokes a
provider, grants authority, merges source, ingests private owner data, or enables
stable promotion. Source presence and deterministic tests cannot manufacture an
owner-value observation.
"""

from argparse import ArgumentParser
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence


SCHEMA = "BUBBLES-OWNER-VALUE-DEPLOYMENT-COURT-V2"
OWNER_VALUE_MODE = "OBSERVED_OWNER_VALUE"
INTERNAL_RUNTIME_MODE = "INTERNAL_RUNTIME_QUALIFICATION"
LIVE_DEPLOYMENT_MODE = "LIVE_PROVIDER_DEPLOYMENT"
DEFAULT_MINIMUM_OWNER_VALUE_PAIRS = 10


def canonical_hash(value: Any) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        ).encode()
    ).hexdigest()


def _is_sha(value: str) -> bool:
    return len(value) == 40 and all(character in "0123456789abcdef" for character in value.lower())


def _is_digest(value: str) -> bool:
    prefix, separator, digest = value.partition(":")
    return (
        separator == ":"
        and prefix == "sha256"
        and len(digest) == 64
        and all(character in "0123456789abcdef" for character in digest.lower())
    )


def _nonnegative(value: float, code: str) -> None:
    if float(value) < 0:
        raise ValueError(code)


@dataclass(frozen=True, slots=True)
class OwnerValueObservation:
    pair_id: str
    mission_class: str
    task_signature: str
    oracle_id: str
    source_head_sha: str
    evidence_mode: str
    baseline_owner_minutes: float
    candidate_owner_minutes: float
    baseline_owner_interventions: int
    candidate_owner_interventions: int
    baseline_clarification_count: int
    candidate_clarification_count: int
    baseline_correction_count: int
    candidate_correction_count: int
    baseline_verified_output_ratio: float
    candidate_verified_output_ratio: float
    baseline_elapsed_seconds: float
    candidate_elapsed_seconds: float
    independent_readback: bool
    proof_refs: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "OwnerValueObservation":
        return cls(
            pair_id=str(value.get("pair_id") or ""),
            mission_class=str(value.get("mission_class") or ""),
            task_signature=str(value.get("task_signature") or ""),
            oracle_id=str(value.get("oracle_id") or ""),
            source_head_sha=str(value.get("source_head_sha") or ""),
            evidence_mode=str(value.get("evidence_mode") or ""),
            baseline_owner_minutes=float(value.get("baseline_owner_minutes", 0)),
            candidate_owner_minutes=float(value.get("candidate_owner_minutes", 0)),
            baseline_owner_interventions=int(value.get("baseline_owner_interventions", 0)),
            candidate_owner_interventions=int(value.get("candidate_owner_interventions", 0)),
            baseline_clarification_count=int(value.get("baseline_clarification_count", 0)),
            candidate_clarification_count=int(value.get("candidate_clarification_count", 0)),
            baseline_correction_count=int(value.get("baseline_correction_count", 0)),
            candidate_correction_count=int(value.get("candidate_correction_count", 0)),
            baseline_verified_output_ratio=float(value.get("baseline_verified_output_ratio", 0)),
            candidate_verified_output_ratio=float(value.get("candidate_verified_output_ratio", 0)),
            baseline_elapsed_seconds=float(value.get("baseline_elapsed_seconds", 0)),
            candidate_elapsed_seconds=float(value.get("candidate_elapsed_seconds", 0)),
            independent_readback=value.get("independent_readback") is True,
            proof_refs=tuple(str(item).strip() for item in value.get("proof_refs") or () if str(item).strip()),
        )

    @property
    def creator_time_recovered_minutes(self) -> float:
        return float(self.baseline_owner_minutes) - float(self.candidate_owner_minutes)

    @property
    def owner_intervention_delta(self) -> int:
        return int(self.baseline_owner_interventions) - int(self.candidate_owner_interventions)

    @property
    def clarification_delta(self) -> int:
        return int(self.baseline_clarification_count) - int(self.candidate_clarification_count)

    @property
    def correction_delta(self) -> int:
        return int(self.baseline_correction_count) - int(self.candidate_correction_count)

    @property
    def elapsed_delta_seconds(self) -> float:
        return float(self.baseline_elapsed_seconds) - float(self.candidate_elapsed_seconds)

    def failures(self, source_head_sha: str) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.pair_id or not self.mission_class:
            failures.append("OWNER_VALUE_IDENTITY_REQUIRED")
        if not self.task_signature or not self.oracle_id:
            failures.append("OWNER_VALUE_TASK_ORACLE_IDENTITY_REQUIRED")
        if self.source_head_sha != source_head_sha:
            failures.append("OWNER_VALUE_SOURCE_HEAD_MISMATCH")
        if self.evidence_mode != OWNER_VALUE_MODE:
            failures.append("OWNER_VALUE_EVIDENCE_MODE_INVALID")

        numeric_values = (
            self.baseline_owner_minutes,
            self.candidate_owner_minutes,
            self.baseline_elapsed_seconds,
            self.candidate_elapsed_seconds,
        )
        if any(float(value) < 0 for value in numeric_values):
            failures.append("OWNER_VALUE_NEGATIVE_MEASUREMENT_INVALID")
        if self.baseline_owner_minutes <= 0:
            failures.append("OWNER_VALUE_BASELINE_MINUTES_POSITIVE_REQUIRED")
        if self.baseline_elapsed_seconds <= 0 or self.candidate_elapsed_seconds <= 0:
            failures.append("OWNER_VALUE_ELAPSED_POSITIVE_REQUIRED")

        counts = (
            self.baseline_owner_interventions,
            self.candidate_owner_interventions,
            self.baseline_clarification_count,
            self.candidate_clarification_count,
            self.baseline_correction_count,
            self.candidate_correction_count,
        )
        if any(int(value) < 0 for value in counts):
            failures.append("OWNER_VALUE_COUNTS_NONNEGATIVE_REQUIRED")

        if not 0 < self.baseline_verified_output_ratio <= 1:
            failures.append("OWNER_VALUE_BASELINE_RATIO_INVALID")
        if not 0 < self.candidate_verified_output_ratio <= 1:
            failures.append("OWNER_VALUE_CANDIDATE_RATIO_INVALID")
        if self.candidate_verified_output_ratio < self.baseline_verified_output_ratio:
            failures.append("OWNER_VALUE_OUTPUT_RATIO_REGRESSION")

        if self.candidate_owner_minutes >= self.baseline_owner_minutes:
            failures.append("OWNER_VALUE_CREATOR_TIME_NOT_RECOVERED")
        if self.candidate_owner_interventions > self.baseline_owner_interventions:
            failures.append("OWNER_VALUE_INTERVENTION_REGRESSION")
        if self.candidate_clarification_count > self.baseline_clarification_count:
            failures.append("OWNER_VALUE_CLARIFICATION_REGRESSION")
        if self.candidate_correction_count > self.baseline_correction_count:
            failures.append("OWNER_VALUE_CORRECTION_REGRESSION")
        if self.candidate_elapsed_seconds > self.baseline_elapsed_seconds:
            failures.append("OWNER_VALUE_LATENCY_REGRESSION")

        if not self.independent_readback:
            failures.append("OWNER_VALUE_INDEPENDENT_READBACK_REQUIRED")
        if len(set(self.proof_refs)) < 2:
            failures.append("OWNER_VALUE_PROOF_REFS_INCOMPLETE")
        return tuple(failures)


@dataclass(frozen=True, slots=True)
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
            evidence_id=str(value.get("evidence_id") or ""),
            source_head_sha=str(value.get("source_head_sha") or ""),
            evidence_mode=str(value.get("evidence_mode") or ""),
            environment=str(value.get("environment") or ""),
            image_digest=str(value.get("image_digest") or ""),
            revision_id=str(value.get("revision_id") or ""),
            provider_registration_verified=value.get("provider_registration_verified") is True,
            workload_identity_verified=value.get("workload_identity_verified") is True,
            health_readback_verified=value.get("health_readback_verified") is True,
            rollback_verified=value.get("rollback_verified") is True,
            deployment_observed=value.get("deployment_observed") is True,
            independent_readback=value.get("independent_readback") is True,
            provider_effect_authorized=value.get("provider_effect_authorized") is True,
            proof_refs=tuple(str(item).strip() for item in value.get("proof_refs") or () if str(item).strip()),
        )

    def internal_failures(self, source_head_sha: str) -> tuple[str, ...]:
        failures: list[str] = []
        if self.evidence_mode != INTERNAL_RUNTIME_MODE:
            return ("INTERNAL_RUNTIME_EVIDENCE_MODE_INVALID",)
        if self.source_head_sha != source_head_sha:
            failures.append("INTERNAL_RUNTIME_SOURCE_HEAD_MISMATCH")
        if not self.evidence_id or not _is_digest(self.image_digest):
            failures.append("INTERNAL_RUNTIME_IDENTITY_OR_IMAGE_DIGEST_INVALID")
        if not self.health_readback_verified:
            failures.append("INTERNAL_RUNTIME_HEALTH_UNPROVEN")
        if not self.rollback_verified:
            failures.append("INTERNAL_RUNTIME_ROLLBACK_UNPROVEN")
        if not self.independent_readback or len(set(self.proof_refs)) < 2:
            failures.append("INTERNAL_RUNTIME_READBACK_OR_PROOF_INCOMPLETE")
        if self.provider_effect_authorized:
            failures.append("INTERNAL_RUNTIME_PROVIDER_EFFECT_MUST_BE_FALSE")
        return tuple(failures)

    def deployment_failures(self, source_head_sha: str) -> tuple[str, ...]:
        failures: list[str] = []
        if self.evidence_mode != LIVE_DEPLOYMENT_MODE:
            return ("LIVE_DEPLOYMENT_EVIDENCE_MODE_INVALID",)
        if self.source_head_sha != source_head_sha:
            failures.append("LIVE_DEPLOYMENT_SOURCE_HEAD_MISMATCH")
        if (
            not self.evidence_id
            or not self.environment
            or not self.revision_id
            or not _is_digest(self.image_digest)
        ):
            failures.append("LIVE_DEPLOYMENT_IDENTITY_INCOMPLETE")
        if not self.provider_registration_verified:
            failures.append("PROVIDER_REGISTRATION_UNPROVEN")
        if not self.workload_identity_verified:
            failures.append("WORKLOAD_IDENTITY_UNPROVEN")
        if not self.health_readback_verified:
            failures.append("LIVE_HEALTH_READBACK_UNPROVEN")
        if not self.rollback_verified:
            failures.append("LIVE_ROLLBACK_UNPROVEN")
        if not self.deployment_observed:
            failures.append("LIVE_DEPLOYMENT_OBSERVATION_UNPROVEN")
        if not self.independent_readback or len(set(self.proof_refs)) < 3:
            failures.append("LIVE_DEPLOYMENT_READBACK_OR_PROOF_INCOMPLETE")
        if not self.provider_effect_authorized:
            failures.append("LIVE_DEPLOYMENT_AUTHORITY_RECEIPT_UNPROVEN")
        return tuple(failures)


@dataclass(frozen=True, slots=True)
class ProofCourtReceipt:
    schema: str
    source_head_sha: str
    candidate_id: str
    owner_value_pair_count: int
    owner_value_proven: bool
    creator_time_recovered_minutes: float
    median_creator_time_recovered_minutes: float
    median_intervention_delta: float
    median_clarification_delta: float
    median_correction_delta: float
    median_elapsed_delta_seconds: float
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_proof_court(
    *,
    candidate_id: str,
    source_head_sha: str,
    owner_value_observations: Sequence[Mapping[str, Any]] = (),
    runtime_or_deployment_evidence: Sequence[Mapping[str, Any]] = (),
    minimum_owner_value_pairs: int = DEFAULT_MINIMUM_OWNER_VALUE_PAIRS,
) -> ProofCourtReceipt:
    if not candidate_id.strip():
        raise ValueError("COURT_CANDIDATE_ID_REQUIRED")
    if not _is_sha(source_head_sha):
        raise ValueError("COURT_SOURCE_HEAD_SHA_REQUIRED")
    if int(minimum_owner_value_pairs) <= 0:
        raise ValueError("COURT_MINIMUM_OWNER_VALUE_PAIRS_INVALID")

    blockers: set[str] = set()
    owner_items = tuple(OwnerValueObservation.from_mapping(item) for item in owner_value_observations)
    pair_ids = [item.pair_id for item in owner_items]
    if len(owner_items) < int(minimum_owner_value_pairs):
        blockers.add("OWNER_VALUE_MINIMUM_OBSERVED_PAIRS_REQUIRED")
    if len(set(pair_ids)) != len(pair_ids):
        blockers.add("OWNER_VALUE_PAIR_IDS_MUST_BE_UNIQUE")

    for item in owner_items:
        blockers.update(item.failures(source_head_sha))

    owner_blockers = {item for item in blockers if item.startswith("OWNER_VALUE_")}
    owner_value_proven = (
        len(owner_items) >= int(minimum_owner_value_pairs)
        and not owner_blockers
    )

    if owner_items:
        recovered = [item.creator_time_recovered_minutes for item in owner_items]
        interventions = [item.owner_intervention_delta for item in owner_items]
        clarifications = [item.clarification_delta for item in owner_items]
        corrections = [item.correction_delta for item in owner_items]
        elapsed = [item.elapsed_delta_seconds for item in owner_items]
        total_recovered = sum(recovered)
        median_recovered = median(recovered)
        median_intervention = median(interventions)
        median_clarification = median(clarifications)
        median_correction = median(corrections)
        median_elapsed = median(elapsed)
    else:
        total_recovered = median_recovered = 0.0
        median_intervention = median_clarification = median_correction = 0.0
        median_elapsed = 0.0

    evidence = tuple(
        RuntimeOrDeploymentEvidence.from_mapping(item)
        for item in runtime_or_deployment_evidence
    )
    internal_items = tuple(item for item in evidence if item.evidence_mode == INTERNAL_RUNTIME_MODE)
    live_items = tuple(item for item in evidence if item.evidence_mode == LIVE_DEPLOYMENT_MODE)

    internal_runtime_qualified = False
    for item in internal_items:
        failures = item.internal_failures(source_head_sha)
        blockers.update(failures)
        internal_runtime_qualified = internal_runtime_qualified or not failures
    if not internal_items:
        blockers.add("EXACT_HEAD_INTERNAL_RUNTIME_QUALIFICATION_REQUIRED")

    provider_deployment_proven = False
    for item in live_items:
        failures = item.deployment_failures(source_head_sha)
        blockers.update(failures)
        provider_deployment_proven = provider_deployment_proven or not failures
    if not live_items:
        blockers.add("LIVE_PROVIDER_DEPLOYMENT_EVIDENCE_REQUIRED")

    ready_for_owner_review = (
        owner_value_proven
        and internal_runtime_qualified
        and provider_deployment_proven
    )
    if ready_for_owner_review:
        decision = "OWNER_VALUE_AND_DEPLOYMENT_PROOF_SATISFIED_PROMOTION_REVIEW_REQUIRED"
        next_gate = "SEPARATE_OWNER_PROMOTION_REVIEW"
    elif owner_value_proven:
        decision = "OWNER_VALUE_PROVEN_DEPLOYMENT_GATES_OPEN"
        next_gate = "CLOSE_RUNTIME_AND_PROVIDER_DEPLOYMENT_GATES"
    else:
        decision = "HOLD_NO_PROMOTION"
        next_gate = "COLLECT_MATCHED_OWNER_VALUE_AND_RUNTIME_EVIDENCE"

    payload = {
        "schema": SCHEMA,
        "source_head_sha": source_head_sha,
        "candidate_id": candidate_id,
        "owner_value_pair_count": len(owner_items),
        "owner_value_proven": owner_value_proven,
        "creator_time_recovered_minutes": round(float(total_recovered), 6),
        "median_creator_time_recovered_minutes": round(float(median_recovered), 6),
        "median_intervention_delta": round(float(median_intervention), 6),
        "median_clarification_delta": round(float(median_clarification), 6),
        "median_correction_delta": round(float(median_correction), 6),
        "median_elapsed_delta_seconds": round(float(median_elapsed), 6),
        "internal_runtime_qualified": internal_runtime_qualified,
        "provider_deployment_proven": provider_deployment_proven,
        "decision": decision,
        "blockers": tuple(sorted(blockers)),
        "stable_promotion_authorized": False,
        "effect_authorized": False,
        "external_effect": False,
        "next_gate": next_gate,
        "truth_boundary": (
            "Owner-value proof requires matched real observations with exact source identity and independent readback; source/tests cannot create it.",
            "The court requires positive creator-time recovery and forbids output-quality, intervention, clarification, correction, or latency regression in every admitted pair.",
            "Internal runtime qualification does not prove provider deployment.",
            "Provider deployment proof does not grant this court merge, effect, authority, or stable-promotion power.",
            "No AGI, hidden background execution, private-memory ingestion, or universal provider authority is inferred.",
        ),
    }
    return ProofCourtReceipt(**payload, receipt_sha256=canonical_hash(payload))


def main() -> int:
    parser = ArgumentParser()
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--source-head-sha", required=True)
    parser.add_argument("--owner-value-receipt", type=Path)
    parser.add_argument("--deployment-receipt", type=Path)
    parser.add_argument("--minimum-owner-value-pairs", type=int, default=DEFAULT_MINIMUM_OWNER_VALUE_PAIRS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    owner = (
        json.loads(args.owner_value_receipt.read_text(encoding="utf-8"))
        if args.owner_value_receipt
        else []
    )
    deployment = (
        json.loads(args.deployment_receipt.read_text(encoding="utf-8"))
        if args.deployment_receipt
        else []
    )
    receipt = evaluate_proof_court(
        candidate_id=args.candidate_id,
        source_head_sha=args.source_head_sha,
        owner_value_observations=owner,
        runtime_or_deployment_evidence=deployment,
        minimum_owner_value_pairs=args.minimum_owner_value_pairs,
    ).to_dict()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
