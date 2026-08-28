from __future__ import annotations

"""Capability Genesis Foundry and Architecture Genome.

Missing capabilities are formed through a strict evidence-bearing lifecycle.
The foundry reuses existing capability first, blocks stage skipping, and cannot
mint external authority or self-certify promotion.
"""

from dataclasses import asdict, dataclass, replace
from enum import Enum
from typing import Any, Mapping, Sequence

from .contracts import CapabilityDescriptor, CivitasError, ProofLevel, digest, proof_at_least, safe_id


class GenesisStage(str, Enum):
    REUSE_SEARCHED = "REUSE_SEARCHED"
    REQUIREMENTS = "REQUIREMENTS"
    ARCHITECTURE = "ARCHITECTURE"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    RED_TEAMED = "RED_TEAMED"
    SHADOW = "SHADOW"
    VALUE_VERIFIED = "VALUE_VERIFIED"
    PROMOTION_ELIGIBLE = "PROMOTION_ELIGIBLE"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"


ORDERED_STAGES = (
    GenesisStage.REUSE_SEARCHED,
    GenesisStage.REQUIREMENTS,
    GenesisStage.ARCHITECTURE,
    GenesisStage.IMPLEMENTED,
    GenesisStage.TESTED,
    GenesisStage.RED_TEAMED,
    GenesisStage.SHADOW,
    GenesisStage.VALUE_VERIFIED,
    GenesisStage.PROMOTION_ELIGIBLE,
)
STAGE_RANK = {stage: index for index, stage in enumerate(ORDERED_STAGES)}


@dataclass(frozen=True)
class EngineeringGene:
    gene_id: str
    problem_class: str
    pattern: str
    prerequisites: tuple[str, ...]
    exclusions: tuple[str, ...]
    benefits: tuple[str, ...]
    tradeoffs: tuple[str, ...]
    failure_modes: tuple[str, ...]
    rollback_pattern: str
    proof_refs: tuple[str, ...]
    authority_ceiling: str = "A1_INTERNAL"
    privacy_ceiling: str = "PUBLIC_SAFE"

    def validate(self) -> "EngineeringGene":
        safe_id(self.gene_id, "gene_id")
        if not self.problem_class.strip() or not self.pattern.strip() or not self.rollback_pattern.strip():
            raise ValueError("gene problem_class, pattern and rollback required")
        if not self.proof_refs:
            raise ValueError("gene requires proof")
        if self.authority_ceiling not in {"A0_READ", "A1_INTERNAL"}:
            raise CivitasError("engineering gene cannot transfer effect authority")
        return self


@dataclass(frozen=True)
class ProductGenome:
    genome_id: str
    product_class: str
    gene_ids: tuple[str, ...]
    interface_contracts: tuple[str, ...]
    proof_contracts: tuple[str, ...]
    rollback_contracts: tuple[str, ...]
    zero_dilution_floor: tuple[str, ...]
    proof_refs: tuple[str, ...]

    def validate(self) -> "ProductGenome":
        safe_id(self.genome_id, "genome_id")
        if not self.product_class.strip() or not self.gene_ids:
            raise ValueError("genome product_class and genes required")
        if not self.proof_contracts or not self.rollback_contracts or not self.zero_dilution_floor:
            raise ValueError("proof, rollback and zero-dilution contracts required")
        if not self.proof_refs:
            raise ValueError("genome requires proof")
        return self


@dataclass(frozen=True)
class GenesisCandidate:
    candidate_id: str
    capability_name: str
    objective: str
    required_tags: tuple[str, ...]
    stage: GenesisStage
    evidence_refs: tuple[str, ...]
    reused_capability_id: str = ""
    architecture_genome_id: str = ""
    rollback_ready: bool = False
    regression_passed: bool = False
    independent_verifier: bool = False
    value_delta: float | None = None
    external_effects: int = 0

    def validate(self) -> "GenesisCandidate":
        safe_id(self.candidate_id, "candidate_id")
        if not self.capability_name.strip() or not self.objective.strip() or not self.required_tags:
            raise ValueError("candidate name, objective and tags required")
        if not self.evidence_refs:
            raise ValueError("candidate requires evidence")
        if self.external_effects:
            raise CivitasError("genesis candidate cannot execute external effects")
        return self


@dataclass(frozen=True)
class FoundryDecision:
    candidate_id: str
    disposition: str
    reuse_matches: tuple[str, ...]
    next_stage: GenesisStage
    explanation: str
    proof_refs: tuple[str, ...]
    external_effects: int = 0


class ArchitectureGenomeRegistry:
    def __init__(self) -> None:
        self._genes: dict[str, EngineeringGene] = {}
        self._genomes: dict[str, ProductGenome] = {}

    def register_gene(self, gene: EngineeringGene) -> str:
        gene.validate()
        existing = self._genes.get(gene.gene_id)
        if existing is not None and existing != gene:
            raise CivitasError("gene id collision")
        self._genes[gene.gene_id] = gene
        return digest(asdict(gene))

    def register_genome(self, genome: ProductGenome) -> str:
        genome.validate()
        missing = [gene_id for gene_id in genome.gene_ids if gene_id not in self._genes]
        if missing:
            raise CivitasError("genome references unknown gene: " + missing[0])
        existing = self._genomes.get(genome.genome_id)
        if existing is not None and existing != genome:
            raise CivitasError("genome id collision")
        self._genomes[genome.genome_id] = genome
        return digest(asdict(genome))

    def search(self, terms: Sequence[str]) -> tuple[EngineeringGene, ...]:
        wanted = {str(term).lower() for term in terms if str(term).strip()}
        matches: list[EngineeringGene] = []
        for gene in self._genes.values():
            corpus = " ".join((
                gene.problem_class,
                gene.pattern,
                *gene.prerequisites,
                *gene.exclusions,
                *gene.benefits,
                *gene.tradeoffs,
                *gene.failure_modes,
            )).lower()
            if all(term in corpus for term in wanted):
                matches.append(gene)
        return tuple(sorted(matches, key=lambda item: item.gene_id))

    def genome(self, genome_id: str) -> ProductGenome:
        if genome_id not in self._genomes:
            raise CivitasError("unknown product genome")
        return self._genomes[genome_id]


class CapabilityFoundry:
    def __init__(self, genomes: ArchitectureGenomeRegistry | None = None) -> None:
        self.genomes = genomes or ArchitectureGenomeRegistry()
        self._candidates: dict[str, GenesisCandidate] = {}

    @staticmethod
    def reuse_search(required_tags: Sequence[str], capabilities: Sequence[CapabilityDescriptor]) -> tuple[str, ...]:
        wanted = {str(tag).lower() for tag in required_tags}
        matches: list[str] = []
        for capability in capabilities:
            capability.validate()
            actual = {tag.lower() for tag in capability.tags}
            if wanted.issubset(actual) and proof_at_least(capability.proof.level, ProofLevel.SOURCE_READBACK):
                matches.append(capability.capability_id)
        return tuple(sorted(matches))

    def open_candidate(
        self,
        *,
        candidate_id: str,
        capability_name: str,
        objective: str,
        required_tags: Sequence[str],
        available_capabilities: Sequence[CapabilityDescriptor],
        proof_ref: str,
    ) -> tuple[GenesisCandidate, FoundryDecision]:
        matches = self.reuse_search(required_tags, available_capabilities)
        candidate = GenesisCandidate(
            candidate_id=candidate_id,
            capability_name=capability_name,
            objective=objective,
            required_tags=tuple(dict.fromkeys(str(item) for item in required_tags)),
            stage=GenesisStage.REUSE_SEARCHED,
            evidence_refs=(proof_ref,),
            reused_capability_id=matches[0] if matches else "",
        ).validate()
        existing = self._candidates.get(candidate_id)
        if existing is not None and existing != candidate:
            raise CivitasError("candidate id collision")
        self._candidates[candidate_id] = candidate
        decision = FoundryDecision(
            candidate_id,
            "REUSE_EXTEND_FIRST" if matches else "FORM_NEW_CAPABILITY_CANDIDATE",
            matches,
            GenesisStage.REQUIREMENTS,
            "adapt a compatible proof-bearing capability before creating a duplicate" if matches else "no compatible proof-bearing capability found; requirements may be formed",
            (proof_ref,),
        )
        return candidate, decision

    def candidate(self, candidate_id: str) -> GenesisCandidate:
        if candidate_id not in self._candidates:
            raise CivitasError("unknown genesis candidate")
        return self._candidates[candidate_id]

    def advance(
        self,
        candidate_id: str,
        target_stage: GenesisStage,
        *,
        evidence_refs: Sequence[str],
        architecture_genome_id: str | None = None,
        rollback_ready: bool | None = None,
        regression_passed: bool | None = None,
        independent_verifier: bool | None = None,
        value_delta: float | None = None,
        authority_expansion: bool = False,
    ) -> GenesisCandidate:
        current = self.candidate(candidate_id).validate()
        if authority_expansion:
            raise CivitasError("capability genesis cannot manufacture authority")
        if target_stage in {GenesisStage.REJECTED, GenesisStage.QUARANTINED}:
            updated = replace(
                current,
                stage=target_stage,
                evidence_refs=tuple(dict.fromkeys(current.evidence_refs + tuple(evidence_refs))),
            )
            self._candidates[candidate_id] = updated
            return updated
        if current.stage not in STAGE_RANK or target_stage not in STAGE_RANK:
            raise CivitasError("unsupported genesis transition")
        if STAGE_RANK[target_stage] != STAGE_RANK[current.stage] + 1:
            raise CivitasError("stage skipping or backward transition blocked")
        if not evidence_refs:
            raise ValueError("stage transition requires evidence")
        genome_id = current.architecture_genome_id if architecture_genome_id is None else architecture_genome_id
        rollback = current.rollback_ready if rollback_ready is None else rollback_ready
        regression = current.regression_passed if regression_passed is None else regression_passed
        verifier = current.independent_verifier if independent_verifier is None else independent_verifier
        value = current.value_delta if value_delta is None else value_delta
        if target_stage == GenesisStage.ARCHITECTURE:
            if not genome_id:
                raise CivitasError("architecture stage requires product genome")
            self.genomes.genome(genome_id)
        if target_stage == GenesisStage.TESTED and not regression:
            raise CivitasError("tested stage requires regression proof")
        if target_stage == GenesisStage.RED_TEAMED and not verifier:
            raise CivitasError("red-team stage requires independent verifier")
        if target_stage == GenesisStage.SHADOW and not rollback:
            raise CivitasError("shadow stage requires rollback readiness")
        if target_stage == GenesisStage.VALUE_VERIFIED and (value is None or value <= 0):
            raise CivitasError("value stage requires positive measured value")
        if target_stage == GenesisStage.PROMOTION_ELIGIBLE and not (
            rollback and regression and verifier and value is not None and value > 0
        ):
            raise CivitasError("promotion eligibility requires rollback, regression, independent assurance and positive value")
        updated = replace(
            current,
            stage=target_stage,
            evidence_refs=tuple(dict.fromkeys(current.evidence_refs + tuple(evidence_refs))),
            architecture_genome_id=genome_id,
            rollback_ready=rollback,
            regression_passed=regression,
            independent_verifier=verifier,
            value_delta=value,
        ).validate()
        self._candidates[candidate_id] = updated
        return updated

    def promotion_receipt(self, candidate_id: str) -> Mapping[str, Any]:
        candidate = self.candidate(candidate_id)
        if candidate.stage != GenesisStage.PROMOTION_ELIGIBLE:
            raise CivitasError("candidate is not promotion eligible")
        body = {
            "candidate": asdict(candidate),
            "disposition": "ELIGIBLE_FOR_SEPARATE_SOVARA_EFFECT_ADMISSION",
            "provider_execution_performed": False,
            "authority_created": False,
            "external_effects": 0,
        }
        return {**body, "receipt_sha256": digest(body)}


__all__ = [
    "GenesisStage", "EngineeringGene", "ProductGenome", "GenesisCandidate",
    "FoundryDecision", "ArchitectureGenomeRegistry", "CapabilityFoundry",
]
