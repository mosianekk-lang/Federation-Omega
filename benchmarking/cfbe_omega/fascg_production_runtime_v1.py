from __future__ import annotations

"""FASCG production-closure primitives.

This module extends the existing FASCG control plane with production-grade state,
checkpoint, evaluation, promotion, and self-evolution contracts.  It deliberately
contains no provider client, no repository writer, no authority minting, no model
trainer, and no direct production mutation path.
"""

from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from hashlib import sha256
import json
import math
from typing import Any, Iterable, Mapping, Sequence

from benchmarking.cfbe_omega.autopilot_sentinel_cognitive_genome_v1 import GeneDomain

SCHEMA = "FASCG-PRODUCTION-RUNTIME-V1"
PROVIDER_EFFECT_AUTHORIZED = False
AUTHORITY_MINTING_AUTHORIZED = False
MODEL_TRAINING_AUTHORIZED = False
PRODUCTION_SELF_MUTATION_AUTHORIZED = False
TEN_X_VERIFIED = False


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _hash(value: Any) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(v).strip() for v in values if str(v).strip()}))


def _unit(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{label}_NOT_FINITE")
    value = float(value)
    if not 0 <= value <= 1:
        raise ValueError(f"{label}_OUT_OF_RANGE")
    return value


class ProductionStage(StrEnum):
    SOURCE_READY = "SOURCE_READY"
    SOURCE_ADMITTED = "SOURCE_ADMITTED"
    HOSTED_SHADOW = "HOSTED_SHADOW"
    PROVIDER_BOUND = "PROVIDER_BOUND"
    CANARY = "CANARY"
    OPERATIONAL = "OPERATIONAL"
    SUSTAINED_VALUE = "SUSTAINED_VALUE"


_STAGE_ORDER = {stage: idx for idx, stage in enumerate(ProductionStage)}


class ProviderSurface(StrEnum):
    GITHUB_HOSTED = "GITHUB_HOSTED"
    GOOGLE_CLOUD = "GOOGLE_CLOUD"
    GOOGLE_APPS_SCRIPT = "GOOGLE_APPS_SCRIPT"
    GOOGLE_AI_STUDIO = "GOOGLE_AI_STUDIO"
    OPENAI_RUNTIME = "OPENAI_RUNTIME"
    FEDERATION_INTERNAL = "FEDERATION_INTERNAL"


@dataclass(frozen=True, slots=True)
class ProviderPassport:
    passport_id: str
    surface: ProviderSurface
    capability_set: tuple[str, ...]
    source_workflow: str
    identity_fingerprint: str
    authority_ceiling: str
    proof_refs: tuple[str, ...]
    provider_readback_required: bool = True
    provider_effect_authorized: bool = False
    mutation_capable: bool = False

    def validate(self) -> "ProviderPassport":
        if not self.passport_id.strip() or not self.source_workflow.strip() or not self.identity_fingerprint.strip():
            raise ValueError("FASCG_PROVIDER_PASSPORT_IDENTITY_REQUIRED")
        if not self.capability_set or not self.proof_refs:
            raise ValueError("FASCG_PROVIDER_PASSPORT_CAPABILITY_PROOF_REQUIRED")
        if self.provider_effect_authorized or self.mutation_capable:
            raise ValueError("FASCG_PRODUCTION_KERNEL_PROVIDER_EFFECT_FORBIDDEN")
        return self


@dataclass(frozen=True, slots=True)
class StateVersion:
    version_id: str
    mission_id: str
    state_kind: str
    source_sha: str
    payload_sha256: str
    previous_version_id: str | None
    previous_chain_sha256: str | None
    proof_refs: tuple[str, ...]
    chain_sha256: str

    def validate(self) -> "StateVersion":
        for value, label in ((self.version_id, "VERSION_ID"), (self.mission_id, "MISSION_ID"),
                             (self.state_kind, "STATE_KIND"), (self.source_sha, "SOURCE_SHA"),
                             (self.payload_sha256, "PAYLOAD_SHA"), (self.chain_sha256, "CHAIN_SHA")):
            if not str(value).strip():
                raise ValueError(f"FASCG_STATE_{label}_REQUIRED")
        if not self.proof_refs:
            raise ValueError("FASCG_STATE_PROOF_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class CognitiveStateVersionGraph:
    versions: tuple[StateVersion, ...] = ()

    def append(self, *, mission_id: str, state_kind: str, source_sha: str,
               payload: Mapping[str, Any], proof_refs: Iterable[str]) -> "CognitiveStateVersionGraph":
        refs = _clean(proof_refs)
        if not refs:
            raise ValueError("FASCG_STATE_PROOF_REQUIRED")
        previous = self.versions[-1] if self.versions else None
        payload_sha = _hash(payload)
        body = {
            "schema": SCHEMA,
            "mission_id": mission_id,
            "state_kind": state_kind,
            "source_sha": source_sha,
            "payload_sha256": payload_sha,
            "previous_version_id": previous.version_id if previous else None,
            "previous_chain_sha256": previous.chain_sha256 if previous else None,
            "proof_refs": refs,
        }
        chain_sha = _hash(body)
        version = StateVersion(
            version_id=f"FASCG-STATE-{chain_sha[:16].upper()}", mission_id=mission_id,
            state_kind=state_kind, source_sha=source_sha, payload_sha256=payload_sha,
            previous_version_id=body["previous_version_id"],
            previous_chain_sha256=body["previous_chain_sha256"], proof_refs=refs,
            chain_sha256=chain_sha,
        ).validate()
        return CognitiveStateVersionGraph(self.versions + (version,))

    def validate_chain(self) -> bool:
        previous: StateVersion | None = None
        for version in self.versions:
            version.validate()
            if previous is None:
                if version.previous_version_id is not None or version.previous_chain_sha256 is not None:
                    return False
            else:
                if version.previous_version_id != previous.version_id or version.previous_chain_sha256 != previous.chain_sha256:
                    return False
            previous = version
        return True


@dataclass(frozen=True, slots=True)
class RuntimeCheckpoint:
    checkpoint_id: str
    mission_id: str
    source_sha: str
    topology_sha256: str
    state_version_id: str
    completed_nodes: tuple[str, ...]
    pending_nodes: tuple[str, ...]
    proof_refs: tuple[str, ...]
    external_effect_pending: bool = False

    def validate(self) -> "RuntimeCheckpoint":
        if not all((self.checkpoint_id.strip(), self.mission_id.strip(), self.source_sha.strip(),
                    self.topology_sha256.strip(), self.state_version_id.strip())):
            raise ValueError("FASCG_CHECKPOINT_IDENTITY_REQUIRED")
        if not self.proof_refs:
            raise ValueError("FASCG_CHECKPOINT_PROOF_REQUIRED")
        if self.external_effect_pending:
            raise ValueError("FASCG_CHECKPOINT_EXTERNAL_EFFECT_PENDING_FORBIDDEN")
        return self


@dataclass(frozen=True, slots=True)
class ResumeReceipt:
    status: str
    checkpoint_id: str
    blockers: tuple[str, ...]
    receipt_sha256: str


class RuntimeResumeCourt:
    @staticmethod
    def evaluate(checkpoint: RuntimeCheckpoint, *, current_source_sha: str,
                 current_topology_sha256: str, state_graph: CognitiveStateVersionGraph) -> ResumeReceipt:
        checkpoint.validate()
        blockers: list[str] = []
        if current_source_sha != checkpoint.source_sha:
            blockers.append("SOURCE_DRIFT")
        if current_topology_sha256 != checkpoint.topology_sha256:
            blockers.append("TOPOLOGY_DRIFT")
        if not state_graph.validate_chain():
            blockers.append("STATE_VERSION_CHAIN_INVALID")
        if not any(v.version_id == checkpoint.state_version_id for v in state_graph.versions):
            blockers.append("STATE_VERSION_MISSING")
        body = {"checkpoint": checkpoint.checkpoint_id, "blockers": sorted(set(blockers))}
        return ResumeReceipt("RESUME_ALLOWED" if not blockers else "RESUME_HELD",
                             checkpoint.checkpoint_id, tuple(body["blockers"]), _hash(body))


@dataclass(frozen=True, slots=True)
class FailureObservation:
    failure_id: str
    family: str
    failure_fingerprint: str
    input_summary_sha256: str
    expected_behavior: str
    observed_behavior: str
    proof_refs: tuple[str, ...]
    severity: float

    def validate(self) -> "FailureObservation":
        if not all((self.failure_id.strip(), self.family.strip(), self.failure_fingerprint.strip(),
                    self.input_summary_sha256.strip(), self.expected_behavior.strip(), self.observed_behavior.strip())):
            raise ValueError("FASCG_FAILURE_OBSERVATION_REQUIRED")
        _unit(self.severity, "FAILURE_SEVERITY")
        if not self.proof_refs:
            raise ValueError("FASCG_FAILURE_PROOF_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class GeneratedEvalCase:
    eval_id: str
    family: str
    source_failure_ids: tuple[str, ...]
    behavior_assertion: str
    held_out: bool
    forbidden_leak_refs: tuple[str, ...]
    eval_sha256: str


class FailureEvalFactory:
    """Deterministically turns real failure clusters into held-out regression cases."""
    @staticmethod
    def synthesize(failures: Sequence[FailureObservation], *, held_out: bool = True) -> tuple[GeneratedEvalCase, ...]:
        if not failures:
            raise ValueError("FASCG_FAILURE_CLUSTER_REQUIRED")
        groups: dict[tuple[str, str], list[FailureObservation]] = {}
        for failure in failures:
            failure.validate()
            groups.setdefault((failure.family, failure.failure_fingerprint), []).append(failure)
        out: list[GeneratedEvalCase] = []
        for (family, fingerprint), rows in sorted(groups.items()):
            source_ids = tuple(sorted(r.failure_id for r in rows))
            assertion = " AND ".join(sorted({r.expected_behavior for r in rows}))
            body = {"family": family, "fingerprint": fingerprint, "source_ids": source_ids,
                    "assertion": assertion, "held_out": bool(held_out)}
            digest = _hash(body)
            out.append(GeneratedEvalCase(
                eval_id=f"FASCG-EVAL-{digest[:16].upper()}", family=family,
                source_failure_ids=source_ids, behavior_assertion=assertion,
                held_out=bool(held_out), forbidden_leak_refs=source_ids if held_out else (),
                eval_sha256=digest,
            ))
        return tuple(out)


@dataclass(frozen=True, slots=True)
class EvolutionCandidate:
    candidate_id: str
    parent_genome_sha256: str
    candidate_genome_sha256: str
    mutation_operator: str
    mutation_proof_refs: tuple[str, ...]
    eval_proof_refs: tuple[str, ...]
    independent_verifier_refs: tuple[str, ...]
    transfer_scores: Mapping[str, float]
    retention_scores: Mapping[str, float]
    rollback_ref: str
    held_out_hidden: bool
    benchmark_access: bool = False
    direct_production_mutation: bool = False

    def validate(self) -> "EvolutionCandidate":
        if not all((self.candidate_id.strip(), self.parent_genome_sha256.strip(),
                    self.candidate_genome_sha256.strip(), self.mutation_operator.strip(), self.rollback_ref.strip())):
            raise ValueError("FASCG_EVOLUTION_CANDIDATE_IDENTITY_REQUIRED")
        if not self.mutation_proof_refs or not self.eval_proof_refs or len(set(self.independent_verifier_refs)) < 2:
            raise ValueError("FASCG_EVOLUTION_INDEPENDENT_PROOF_REQUIRED")
        for mapping, label in ((self.transfer_scores, "TRANSFER"), (self.retention_scores, "RETENTION")):
            if not mapping:
                raise ValueError(f"FASCG_EVOLUTION_{label}_REQUIRED")
            for value in mapping.values(): _unit(float(value), f"EVOLUTION_{label}")
        if not self.held_out_hidden or self.benchmark_access or self.direct_production_mutation:
            raise ValueError("FASCG_EVOLUTION_SANDBOX_BOUNDARY_FAILED")
        return self


@dataclass(frozen=True, slots=True)
class EvolutionPromotionReceipt:
    status: str
    blockers: tuple[str, ...]
    receipt_sha256: str


class EvolutionPromotionCourt:
    def evaluate(self, candidate: EvolutionCandidate, *, transfer_floor: float = .80,
                 retention_floor: float = .95) -> EvolutionPromotionReceipt:
        candidate.validate()
        blockers: list[str] = []
        if min(candidate.transfer_scores.values()) < transfer_floor:
            blockers.append("TRANSFER_FLOOR_FAILED")
        if min(candidate.retention_scores.values()) < retention_floor:
            blockers.append("CATASTROPHIC_FORGETTING_RISK")
        # Source/hosted shadow is the maximum promotion this kernel can grant.
        body = {"candidate": candidate.candidate_id, "blockers": sorted(set(blockers)),
                "maximum_stage": "HOSTED_SHADOW"}
        status = "SHADOW_ELIGIBLE" if not blockers else "SANDBOX_REJECTED"
        return EvolutionPromotionReceipt(status, tuple(body["blockers"]), _hash(body))


@dataclass(frozen=True, slots=True)
class PromotionEvidence:
    stage: ProductionStage
    source_sha: str
    proof_refs: tuple[str, ...]
    independent_verifier_refs: tuple[str, ...]
    provider_native_readback: bool
    rollback_available: bool
    safety_score: float
    reliability_score: float
    owner_value_score: float
    sustained_windows: int = 0

    def validate(self) -> "PromotionEvidence":
        if not self.source_sha.strip() or not self.proof_refs or len(set(self.independent_verifier_refs)) < 1:
            raise ValueError("FASCG_PROMOTION_PROOF_REQUIRED")
        for value, label in ((self.safety_score, "SAFETY"), (self.reliability_score, "RELIABILITY"),
                             (self.owner_value_score, "OWNER_VALUE")):
            _unit(value, f"PROMOTION_{label}")
        if not self.rollback_available:
            raise ValueError("FASCG_PROMOTION_ROLLBACK_REQUIRED")
        if self.sustained_windows < 0:
            raise ValueError("FASCG_PROMOTION_WINDOWS_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class ProductionPromotionReceipt:
    achieved_stage: ProductionStage
    blockers: tuple[str, ...]
    receipt_sha256: str


class ProductionPromotionCourt:
    """Truth-bound stage promotion; never infers provider/operational maturity."""
    def evaluate(self, rows: Sequence[PromotionEvidence], *, safety_floor: float = .95,
                 reliability_floor: float = .95, owner_value_floor: float = .70,
                 sustained_window_floor: int = 3) -> ProductionPromotionReceipt:
        if not rows:
            raise ValueError("FASCG_PROMOTION_EVIDENCE_REQUIRED")
        validated = sorted((r.validate() for r in rows), key=lambda r: _STAGE_ORDER[r.stage])
        achieved = ProductionStage.SOURCE_READY
        blockers: list[str] = []
        for row in validated:
            if row.safety_score < safety_floor:
                blockers.append(f"SAFETY_FLOOR_FAILED:{row.stage.value}"); break
            if row.reliability_score < reliability_floor:
                blockers.append(f"RELIABILITY_FLOOR_FAILED:{row.stage.value}"); break
            if row.stage in {ProductionStage.PROVIDER_BOUND, ProductionStage.CANARY,
                             ProductionStage.OPERATIONAL, ProductionStage.SUSTAINED_VALUE} and not row.provider_native_readback:
                blockers.append(f"PROVIDER_READBACK_REQUIRED:{row.stage.value}"); break
            if row.stage is ProductionStage.SUSTAINED_VALUE:
                if row.owner_value_score < owner_value_floor:
                    blockers.append("OWNER_VALUE_FLOOR_FAILED"); break
                if row.sustained_windows < sustained_window_floor:
                    blockers.append("SUSTAINED_WINDOWS_REQUIRED"); break
            achieved = row.stage
        body = {"achieved_stage": achieved.value, "blockers": sorted(set(blockers))}
        return ProductionPromotionReceipt(achieved, tuple(body["blockers"]), _hash(body))


@dataclass(frozen=True, slots=True)
class ColdSlateDeploymentSpec:
    deployment_id: str
    mission_id: str
    required_domains: tuple[GeneDomain, ...]
    required_capabilities: tuple[str, ...]
    preferred_surfaces: tuple[ProviderSurface, ...]
    authority_ceiling: str
    safety_floor: float = .95
    reliability_floor: float = .95

    def validate(self) -> "ColdSlateDeploymentSpec":
        if not self.deployment_id.strip() or not self.mission_id.strip() or not self.required_domains:
            raise ValueError("FASCG_DEPLOYMENT_SPEC_REQUIRED")
        _unit(self.safety_floor, "DEPLOYMENT_SAFETY"); _unit(self.reliability_floor, "DEPLOYMENT_RELIABILITY")
        return self


@dataclass(frozen=True, slots=True)
class CompiledDeploymentProfile:
    profile_id: str
    mission_id: str
    selected_passport_ids: tuple[str, ...]
    required_domains: tuple[str, ...]
    uncovered_capabilities: tuple[str, ...]
    external_effect_authorized: bool
    profile_sha256: str


class ColdSlateDeploymentCompiler:
    def compile(self, spec: ColdSlateDeploymentSpec, passports: Sequence[ProviderPassport]) -> CompiledDeploymentProfile:
        spec.validate()
        valid = [p.validate() for p in passports if p.surface in set(spec.preferred_surfaces)]
        selected: list[ProviderPassport] = []
        uncovered = set(spec.required_capabilities)
        for passport in sorted(valid, key=lambda p: (len(set(p.capability_set) & uncovered), p.passport_id), reverse=True):
            covers = set(passport.capability_set) & uncovered
            if covers:
                selected.append(passport); uncovered -= covers
        body = {
            "mission_id": spec.mission_id,
            "selected_passport_ids": sorted(p.passport_id for p in selected),
            "required_domains": sorted(d.value for d in spec.required_domains),
            "uncovered_capabilities": sorted(uncovered),
            "external_effect_authorized": False,
        }
        digest = _hash(body)
        return CompiledDeploymentProfile(
            profile_id=f"FASCG-DEPLOY-{digest[:16].upper()}", mission_id=spec.mission_id,
            selected_passport_ids=tuple(body["selected_passport_ids"]),
            required_domains=tuple(body["required_domains"]),
            uncovered_capabilities=tuple(body["uncovered_capabilities"]),
            external_effect_authorized=False, profile_sha256=digest,
        )


__all__ = [
    "SCHEMA", "PROVIDER_EFFECT_AUTHORIZED", "AUTHORITY_MINTING_AUTHORIZED", "MODEL_TRAINING_AUTHORIZED",
    "PRODUCTION_SELF_MUTATION_AUTHORIZED", "TEN_X_VERIFIED", "ProductionStage", "ProviderSurface",
    "ProviderPassport", "StateVersion", "CognitiveStateVersionGraph", "RuntimeCheckpoint", "ResumeReceipt",
    "RuntimeResumeCourt", "FailureObservation", "GeneratedEvalCase", "FailureEvalFactory", "EvolutionCandidate",
    "EvolutionPromotionReceipt", "EvolutionPromotionCourt", "PromotionEvidence", "ProductionPromotionReceipt",
    "ProductionPromotionCourt", "ColdSlateDeploymentSpec", "CompiledDeploymentProfile", "ColdSlateDeploymentCompiler",
]
