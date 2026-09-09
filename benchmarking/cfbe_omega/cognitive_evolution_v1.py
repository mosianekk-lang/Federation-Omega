from __future__ import annotations

"""CFBE Ω / Alpha→Omega cognitive-evolution Phase-1 contract.

Receiver-local extension of the existing CFBE scientific capability compiler.
It source-admits only the residual semantics identified by the AO-CEF equivalence
court: Cognitive Evolution Genome IR, quality-diversity retention, bounded
verifier/transfer extensions, reuse-first cold-slate planning, and a truth-bound
10x court.

This module is not a scheduler, provider executor, memory root, proof root,
authority plane, model trainer, or production self-mutation mechanism.
"""

from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Sequence

from benchmarking.cfbe_omega.omega_harvest_max_v2 import (
    CapabilityMechanism,
    capability_equivalence,
    capability_superset,
)

SCHEMA = "CFBE_AO_COGNITIVE_EVOLUTION_PHASE1_V1"
PROVIDER_EFFECT_AUTHORIZED = False
MODEL_TRAINING_AUTHORIZED = False
PRODUCTION_SELF_MUTATION_AUTHORIZED = False
STABLE_PROMOTION_AUTHORIZED = False


def _hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("utf-8")).hexdigest()


def _norm(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(v).strip() for v in values if str(v).strip()}))


class EvolutionSubstrate(str, Enum):
    CONTEXT = "CONTEXT"
    MEMORY = "MEMORY"
    ROUTING = "ROUTING"
    SKILL = "SKILL"
    TOPOLOGY = "TOPOLOGY"
    CODE = "CODE"
    ALGORITHM = "ALGORITHM"
    EVALUATOR = "EVALUATOR"
    ADAPTER = "ADAPTER"
    WEIGHT = "WEIGHT"
    WORLD_MODEL = "WORLD_MODEL"
    ARCHITECTURE = "ARCHITECTURE"


@dataclass(frozen=True, slots=True)
class OuterEnvelope:
    objective: str
    allowed_substrates: tuple[EvolutionSubstrate, ...]
    authority_ceiling: str
    data_boundary: str
    owner_intent_hash: str
    compute_budget: float
    safety_floor: float = 0.95
    reliability_floor: float = 0.95
    no_production_self_mutation: bool = True

    def validate(self) -> "OuterEnvelope":
        if not self.objective.strip() or not self.allowed_substrates:
            raise ValueError("COGEVO_OBJECTIVE_AND_SUBSTRATES_REQUIRED")
        if len(set(self.allowed_substrates)) != len(self.allowed_substrates):
            raise ValueError("COGEVO_DUPLICATE_SUBSTRATE")
        if not self.authority_ceiling.strip() or not self.data_boundary.strip():
            raise ValueError("COGEVO_AUTHORITY_DATA_BOUNDARY_REQUIRED")
        if len(self.owner_intent_hash) != 64:
            raise ValueError("COGEVO_OWNER_INTENT_HASH_REQUIRED")
        if self.compute_budget < 0:
            raise ValueError("COGEVO_COMPUTE_BUDGET_NEGATIVE")
        if not 0 <= self.safety_floor <= 1 or not 0 <= self.reliability_floor <= 1:
            raise ValueError("COGEVO_FLOOR_OUT_OF_RANGE")
        if not self.no_production_self_mutation:
            raise ValueError("COGEVO_PRODUCTION_SELF_MUTATION_FORBIDDEN")
        return self

    @property
    def fingerprint(self) -> str:
        self.validate()
        return _hash({
            "objective": self.objective.strip(),
            "allowed_substrates": sorted(x.value for x in self.allowed_substrates),
            "authority_ceiling": self.authority_ceiling.strip(),
            "data_boundary": self.data_boundary.strip(),
            "owner_intent_hash": self.owner_intent_hash,
            "compute_budget": float(self.compute_budget),
            "safety_floor": float(self.safety_floor),
            "reliability_floor": float(self.reliability_floor),
            "no_production_self_mutation": True,
        })


@dataclass(frozen=True, slots=True)
class CognitiveGene:
    gene_id: str
    substrate: EvolutionSubstrate
    objective: str
    primitives: tuple[str, ...]
    invariants: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    proof_refs: tuple[str, ...] = ()

    def validate(self) -> "CognitiveGene":
        if not self.gene_id.strip() or not self.objective.strip() or not self.primitives:
            raise ValueError("COGEVO_GENE_ID_OBJECTIVE_PRIMITIVES_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class CognitiveEvolutionGenome:
    genome_id: str
    generation: int
    envelope_fingerprint: str
    genes: tuple[CognitiveGene, ...]
    parent_genomes: tuple[str, ...]
    lineage_proof_refs: tuple[str, ...]
    fingerprint_sha256: str

    def validate(self) -> "CognitiveEvolutionGenome":
        if not self.genome_id or self.generation < 0 or len(self.envelope_fingerprint) != 64:
            raise ValueError("COGEVO_GENOME_ID_GENERATION_ENVELOPE_REQUIRED")
        ids = [g.validate().gene_id for g in self.genes]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("COGEVO_GENOME_GENES_INVALID")
        if len(self.fingerprint_sha256) != 64:
            raise ValueError("COGEVO_GENOME_FINGERPRINT_REQUIRED")
        return self


def compile_genome(envelope: OuterEnvelope, genes: Sequence[CognitiveGene], *, parent_genomes: Iterable[str] = (), lineage_proof_refs: Iterable[str] = ()) -> CognitiveEvolutionGenome:
    envelope.validate()
    ordered = tuple(sorted((g.validate() for g in genes), key=lambda g: g.gene_id))
    if not ordered or len({g.gene_id for g in ordered}) != len(ordered):
        raise ValueError("COGEVO_GENOME_GENES_INVALID")
    allowed = set(envelope.allowed_substrates)
    forbidden = sorted(g.substrate.value for g in ordered if g.substrate not in allowed)
    if forbidden:
        raise ValueError(f"COGEVO_SUBSTRATE_OUTSIDE_ENVELOPE:{','.join(forbidden)}")
    parents = _norm(parent_genomes)
    proof_refs = _norm(lineage_proof_refs)
    payload = {
        "schema": SCHEMA,
        "envelope": envelope.fingerprint,
        "generation": 0 if not parents else 1,
        "parents": parents,
        "genes": [{
            "gene_id": g.gene_id,
            "substrate": g.substrate.value,
            "objective": g.objective,
            "primitives": _norm(g.primitives),
            "invariants": _norm(g.invariants),
            "dependencies": _norm(g.dependencies),
            "proof_refs": _norm(g.proof_refs),
        } for g in ordered],
        "lineage_proof_refs": proof_refs,
    }
    digest = _hash(payload)
    return CognitiveEvolutionGenome(
        genome_id=f"CEG-{digest[:16].upper()}",
        generation=payload["generation"],
        envelope_fingerprint=envelope.fingerprint,
        genes=ordered,
        parent_genomes=parents,
        lineage_proof_refs=proof_refs,
        fingerprint_sha256=digest,
    ).validate()


@dataclass(frozen=True, slots=True)
class FitnessVector:
    held_out_quality: float
    safety: float
    reliability: float
    transfer: float
    novelty: float
    cost: float
    wall_time: float
    owner_actions: float
    complexity: float

    def validate(self) -> "FitnessVector":
        if any(not 0 <= float(v) <= 1 for v in (self.held_out_quality, self.safety, self.reliability, self.transfer, self.novelty)):
            raise ValueError("COGEVO_FITNESS_UNIT_RANGE_INVALID")
        if any(float(v) < 0 for v in (self.cost, self.wall_time, self.owner_actions, self.complexity)):
            raise ValueError("COGEVO_FITNESS_NEGATIVE_COST")
        return self

    def objective_score(self) -> float:
        self.validate()
        quality = 0.40*self.held_out_quality + 0.22*self.safety + 0.22*self.reliability + 0.14*self.transfer + 0.02*self.novelty
        burden = 1.0 / (1.0 + 0.02*self.cost + 0.02*self.wall_time + 0.12*self.owner_actions + 0.02*self.complexity)
        return round(quality * burden, 8)


@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_id: str
    genome: CognitiveEvolutionGenome
    behavior_niche: str
    fitness: FitnessVector
    proof_refs: tuple[str, ...]
    rollback_available: bool
    provenance_available: bool
    held_out_hidden: bool
    benchmark_access: bool
    score_tampering: bool
    self_granted_authority: bool
    direct_production_self_mutation: bool
    independent_verifier_domains: tuple[str, ...]
    evaluator_families: tuple[str, ...]
    transfer_scores: Mapping[str, float]
    replications: int = 0
    ancestor_ids: tuple[str, ...] = ()

    def validate(self) -> "Candidate":
        if not self.candidate_id.strip() or not self.behavior_niche.strip() or self.replications < 0:
            raise ValueError("COGEVO_CANDIDATE_FIELDS_INVALID")
        self.genome.validate(); self.fitness.validate()
        if any(not 0 <= float(v) <= 1 for v in self.transfer_scores.values()):
            raise ValueError("COGEVO_TRANSFER_SCORE_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class VerifierEcologyConfig:
    minimum_independent_domains: int = 2
    minimum_evaluator_families: int = 2
    minimum_replications: int = 2
    required_transfer_axes: tuple[str, ...] = ("alternate_model", "alternate_harness", "adjacent_task")
    transfer_floor: float = 0.80

    def validate(self) -> "VerifierEcologyConfig":
        if min(self.minimum_independent_domains, self.minimum_evaluator_families, self.minimum_replications) < 1:
            raise ValueError("COGEVO_VERIFIER_QUORUM_INVALID")
        if not self.required_transfer_axes or not 0 <= self.transfer_floor <= 1:
            raise ValueError("COGEVO_TRANSFER_CONFIG_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class VerificationReceipt:
    candidate_id: str
    status: str
    blockers: tuple[str, ...]
    envelope_fingerprint: str
    verification_fingerprint: str

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


def verify_candidate(candidate: Candidate, envelope: OuterEnvelope, *, config: VerifierEcologyConfig | None = None) -> VerificationReceipt:
    candidate.validate(); envelope.validate(); cfg = (config or VerifierEcologyConfig()).validate()
    blockers: list[str] = []
    if candidate.genome.envelope_fingerprint != envelope.fingerprint: blockers.append("OUTER_ENVELOPE_DRIFT")
    if not candidate.held_out_hidden: blockers.append("HIDDEN_HELD_OUT_REQUIRED")
    if candidate.benchmark_access: blockers.append("BENCHMARK_ACCESS_FORBIDDEN")
    if candidate.score_tampering: blockers.append("SCORE_TAMPERING_DETECTED")
    if candidate.self_granted_authority: blockers.append("SELF_GRANTED_AUTHORITY_FORBIDDEN")
    if candidate.direct_production_self_mutation: blockers.append("DIRECT_PRODUCTION_SELF_MUTATION_FORBIDDEN")
    if candidate.fitness.safety < envelope.safety_floor: blockers.append("SAFETY_REGRESSION")
    if candidate.fitness.reliability < envelope.reliability_floor: blockers.append("RELIABILITY_REGRESSION")
    if not candidate.rollback_available: blockers.append("ROLLBACK_REQUIRED")
    if not candidate.provenance_available: blockers.append("PROVENANCE_REQUIRED")
    if not candidate.proof_refs: blockers.append("INDEPENDENT_PROOF_REQUIRED")
    if len(set(candidate.independent_verifier_domains)) < cfg.minimum_independent_domains: blockers.append("INDEPENDENT_VERIFIER_DOMAIN_QUORUM_REQUIRED")
    if len(set(candidate.evaluator_families)) < cfg.minimum_evaluator_families: blockers.append("EVALUATOR_FAMILY_DIVERSITY_REQUIRED")
    if candidate.replications < cfg.minimum_replications: blockers.append("REPLICATION_FLOOR_REQUIRED")
    for axis in cfg.required_transfer_axes:
        if axis not in candidate.transfer_scores: blockers.append(f"TRANSFER_AXIS_MISSING:{axis}")
        elif candidate.transfer_scores[axis] < cfg.transfer_floor: blockers.append(f"TRANSFER_FLOOR_FAILED:{axis}")
    blockers = sorted(set(blockers))
    payload = {"candidate": candidate.candidate_id, "envelope": envelope.fingerprint, "blockers": blockers, "transfer_axes": sorted(cfg.required_transfer_axes), "transfer_floor": cfg.transfer_floor}
    return VerificationReceipt(candidate.candidate_id, "PASS" if not blockers else "FAIL", tuple(blockers), envelope.fingerprint, _hash(payload))


class ArchiveClass(str, Enum):
    ELITE = "ELITE"
    STEPPING_STONE = "STEPPING_STONE"
    FAILURE = "FAILURE"
    ANTI_PATTERN = "ANTI_PATTERN"


@dataclass(frozen=True, slots=True)
class ArchiveEntry:
    candidate_id: str
    behavior_niche: str
    archive_class: ArchiveClass
    objective_score: float
    novelty: float
    ancestor_ids: tuple[str, ...] = ()
    failure_fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class QualityDiversityArchive:
    entries: tuple[ArchiveEntry, ...] = ()

    def by_class(self, archive_class: ArchiveClass) -> tuple[ArchiveEntry, ...]:
        return tuple(e for e in self.entries if e.archive_class == archive_class)

    def elite_for(self, niche: str) -> ArchiveEntry | None:
        rows = [e for e in self.entries if e.archive_class == ArchiveClass.ELITE and e.behavior_niche == niche]
        return max(rows, key=lambda e: (e.objective_score, e.candidate_id)) if rows else None


def _dedupe(entries: Iterable[ArchiveEntry]) -> tuple[ArchiveEntry, ...]:
    rows: dict[tuple[str, ArchiveClass], ArchiveEntry] = {}
    for e in entries: rows[(e.candidate_id, e.archive_class)] = e
    return tuple(sorted(rows.values(), key=lambda e: (e.archive_class.value, e.behavior_niche, e.candidate_id)))


def update_quality_diversity_archive(archive: QualityDiversityArchive, candidate: Candidate, verification: VerificationReceipt, *, novelty_threshold: float = 0.75, severe_failure: bool = False, failure_fingerprint: str = "") -> tuple[str, QualityDiversityArchive]:
    candidate.validate()
    if verification.candidate_id != candidate.candidate_id: raise ValueError("COGEVO_ARCHIVE_VERIFICATION_CANDIDATE_MISMATCH")
    if not 0 <= novelty_threshold <= 1: raise ValueError("COGEVO_NOVELTY_THRESHOLD_INVALID")
    rows = list(archive.entries); score = candidate.fitness.objective_score()
    if not verification.passed:
        failure = ArchiveEntry(candidate.candidate_id, candidate.behavior_niche, ArchiveClass.FAILURE, score, candidate.fitness.novelty, _norm(candidate.ancestor_ids), failure_fingerprint or verification.verification_fingerprint)
        rows.append(failure)
        if severe_failure:
            rows.append(replace(failure, archive_class=ArchiveClass.ANTI_PATTERN)); action = "FAILURE_AND_ANTI_PATTERN_RETAINED"
        else: action = "FAILURE_RETAINED"
        return action, QualityDiversityArchive(_dedupe(rows))
    incumbent = archive.elite_for(candidate.behavior_niche)
    elite = ArchiveEntry(candidate.candidate_id, candidate.behavior_niche, ArchiveClass.ELITE, score, candidate.fitness.novelty, _norm(candidate.ancestor_ids))
    if incumbent is None:
        rows.append(elite); action = "FIRST_NICHE_ELITE"
    elif score > incumbent.objective_score:
        rows = [e for e in rows if not (e.archive_class == ArchiveClass.ELITE and e.behavior_niche == candidate.behavior_niche)]
        rows.extend((elite, replace(incumbent, archive_class=ArchiveClass.STEPPING_STONE))); action = "ELITE_REPLACED_ANCESTOR_PRESERVED"
    elif candidate.fitness.novelty >= novelty_threshold:
        rows.append(replace(elite, archive_class=ArchiveClass.STEPPING_STONE)); action = "NOVEL_STEPPING_STONE_RETAINED"
    else: action = "NO_ARCHIVE_CHANGE"
    return action, QualityDiversityArchive(_dedupe(rows))


class ColdSlateDisposition(str, Enum):
    REUSE = "REUSE"
    EXTEND = "EXTEND"
    BUILD = "BUILD"


@dataclass(frozen=True, slots=True)
class MechanismRoute:
    harvested_id: str
    disposition: ColdSlateDisposition
    incumbent_id: str | None
    equivalence: float
    missing_requirements: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ColdSlatePlan:
    genome: CognitiveEvolutionGenome
    routes: tuple[MechanismRoute, ...]
    provider_effect_authorized: bool = False
    model_training_authorized: bool = False


def compile_cold_slate_plan(envelope: OuterEnvelope, genes: Sequence[CognitiveGene], harvested_mechanisms: Sequence[CapabilityMechanism], incumbent_mechanisms: Sequence[CapabilityMechanism], *, reuse_threshold: float = 0.92, extend_threshold: float = 0.60, parent_genomes: Iterable[str] = (), lineage_proof_refs: Iterable[str] = ()) -> ColdSlatePlan:
    if not 0 <= extend_threshold <= reuse_threshold <= 1: raise ValueError("COGEVO_COLD_SLATE_THRESHOLDS_INVALID")
    genome = compile_genome(envelope, genes, parent_genomes=parent_genomes, lineage_proof_refs=lineage_proof_refs)
    routes: list[MechanismRoute] = []
    for harvested in sorted(harvested_mechanisms, key=lambda x: x.capability_id):
        harvested.validate(); best = None; best_eq = 0.0
        for incumbent in incumbent_mechanisms:
            incumbent.validate(); eq = capability_equivalence(harvested, incumbent)
            if best is None or (eq, incumbent.capability_id) > (best_eq, best.capability_id): best, best_eq = incumbent, eq
        if best is None:
            routes.append(MechanismRoute(harvested.capability_id, ColdSlateDisposition.BUILD, None, 0.0, ())); continue
        coverage = capability_superset(best, harvested)
        if best_eq >= reuse_threshold and not coverage.missing_incumbent_requirements:
            disposition = ColdSlateDisposition.REUSE
        elif best_eq >= extend_threshold:
            disposition = ColdSlateDisposition.EXTEND
        else:
            disposition = ColdSlateDisposition.BUILD
        routes.append(MechanismRoute(harvested.capability_id, disposition, best.capability_id, best_eq, tuple(sorted(coverage.missing_incumbent_requirements))))
    return ColdSlatePlan(genome, tuple(routes))


@dataclass(frozen=True, slots=True)
class TenXCourtReceipt:
    state: str
    ratio: float
    blockers: tuple[str, ...]
    ten_x_proven: bool


def ten_x_composite_frontier_court(*, candidate: Candidate, verification: VerificationReceipt, candidate_cey: float, frontier_cey: float, evidence_maturity: str, independent_replications: int) -> TenXCourtReceipt:
    candidate.validate()
    if candidate_cey < 0 or frontier_cey <= 0 or independent_replications < 0: raise ValueError("COGEVO_TENX_INPUT_INVALID")
    blockers: list[str] = []
    if not verification.passed: blockers.append("VERIFICATION_REQUIRED")
    if evidence_maturity not in {"OPERATIONAL_VERIFIED", "SUSTAINED_VALUE_VERIFIED"}: blockers.append("OPERATIONAL_EVIDENCE_REQUIRED")
    if evidence_maturity != "SUSTAINED_VALUE_VERIFIED": blockers.append("SUSTAINED_VALUE_REQUIRED")
    if independent_replications < 2: blockers.append("TWO_INDEPENDENT_REPLICATIONS_REQUIRED")
    ratio = candidate_cey / frontier_cey
    if ratio < 10.0: blockers.append("TEN_X_CEY_RATIO_NOT_MET")
    blockers = sorted(set(blockers))
    return TenXCourtReceipt("TEN_X_COMPOSITE_FRONTIER" if not blockers else "HELD", round(ratio, 6), tuple(blockers), not blockers)


def phase1_receipt() -> Mapping[str, Any]:
    return {
        "schema": SCHEMA,
        "genome_ir": "RESIDUAL_MINIMUM_BUILD",
        "quality_diversity_archive": "RESIDUAL_MINIMUM_BUILD",
        "verifier_ecology": "EXTENDS_EXISTING_ASSURANCE",
        "transfer_court": "EXTENDS_EXISTING_REPLICATION_AND_PROPAGATION_GATES",
        "cold_slate_compiler": "REUSE_FIRST_MECHANISM_ROUTE_COMPILER",
        "ten_x_court": "MEASUREMENT_REQUIRED",
        "provider_effect_authorized": False,
        "model_training_authorized": False,
        "production_self_mutation_authorized": False,
        "stable_promotion_authorized": False,
        "truth_boundary": (
            "source contract is not provider deployment or model training",
            "quality-diversity retention does not grant authority or promotion",
            "10x requires sustained operational Cognitive Evolution Yield against a frozen composite frontier",
            "production self-mutation remains prohibited",
            "provider/model/IAM/spend/traffic effects require separate exact authority and native readback",
        ),
    }
