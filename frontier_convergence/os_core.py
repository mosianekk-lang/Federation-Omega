"""Frontier Convergence OS — Sovereign Evolution Fabric v1.

Additive evolution layer over the merged Frontier Convergence primitives and the
Federation Stage-20 autonomous maturation controller. This module does not call
providers, mutate external state, grant authority, lower proof thresholds or
self-amend the constitutional root.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
from typing import Any, Iterable, Mapping, Sequence

from .core import (
    CapabilityLease,
    FinOpsParetoRouter,
    FrontierSignal,
    ProofLevel,
    RobustnessVerdict,
    ValueReceipt,
    assert_public_safe,
    canonical_json,
    clean,
    digest,
    parse_time,
    utc_now,
)

AUTHORITY_CEILING = "A1_INTERNAL"
EXTERNAL_EFFECT_DEFAULT = False
SHEETS_HARD_CELL_LIMIT = 50_000
DEFAULT_EVIDENCE_CHUNK = 12_000


class EvolutionMode(str, Enum):
    VERTICAL = "VERTICAL"
    HORIZONTAL = "HORIZONTAL"
    ARCHITECTURAL = "ARCHITECTURAL"


@dataclass(frozen=True)
class CapabilityGene:
    gene_key: str
    name: str
    mechanism: str
    dependencies: tuple[str, ...]
    proof_requirements: tuple[str, ...]
    portability: float
    reversibility: float
    provider_specific: bool = False

    @classmethod
    def create(
        cls,
        *,
        name: str,
        mechanism: str,
        dependencies: Iterable[str] = (),
        proof_requirements: Iterable[str] = (),
        portability: float = 1.0,
        reversibility: float = 1.0,
        provider_specific: bool = False,
    ) -> "CapabilityGene":
        portability = float(portability)
        reversibility = float(reversibility)
        if not 0.0 <= portability <= 1.0 or not 0.0 <= reversibility <= 1.0:
            raise ValueError("GENE_SCORE_OUT_OF_RANGE")
        body = {
            "name": " ".join(name.split()),
            "mechanism": " ".join(mechanism.split()),
            "dependencies": clean(dependencies),
            "proof_requirements": clean(proof_requirements),
            "portability": portability,
            "reversibility": reversibility,
            "provider_specific": bool(provider_specific),
        }
        if not body["name"] or not body["mechanism"]:
            raise ValueError("GENE_FIELDS_REQUIRED")
        assert_public_safe(body)
        return cls(gene_key=f"FCOS-GENE-{digest(body)[:24].upper()}", **body)


@dataclass(frozen=True)
class CapabilityGenome:
    genome_key: str
    capability_class: str
    genes: tuple[CapabilityGene, ...]
    source_signal_keys: tuple[str, ...]
    provider_neutral_core: bool
    authority_ceiling: str = AUTHORITY_CEILING

    @classmethod
    def compile(
        cls,
        *,
        capability_class: str,
        genes: Sequence[CapabilityGene],
        source_signals: Sequence[FrontierSignal] = (),
    ) -> "CapabilityGenome":
        capability_class = " ".join(capability_class.split())
        if not capability_class or not genes:
            raise ValueError("GENOME_CAPABILITY_AND_GENES_REQUIRED")
        if source_signals and any(signal.capability_class != capability_class for signal in source_signals):
            raise ValueError("GENOME_SIGNAL_CLASS_MISMATCH")
        unique = {gene.gene_key: gene for gene in genes}
        ordered = tuple(unique[key] for key in sorted(unique))
        body = {
            "capability_class": capability_class,
            "gene_keys": tuple(gene.gene_key for gene in ordered),
            "source_signal_keys": tuple(sorted(signal.signal_id for signal in source_signals)),
            "provider_neutral_core": all(not gene.provider_specific for gene in ordered),
            "authority_ceiling": AUTHORITY_CEILING,
        }
        return cls(
            genome_key=f"FCOS-GENOME-{digest(body)[:24].upper()}",
            capability_class=capability_class,
            genes=ordered,
            source_signal_keys=body["source_signal_keys"],
            provider_neutral_core=body["provider_neutral_core"],
        )

    def portable_genes(self) -> tuple[CapabilityGene, ...]:
        return tuple(
            gene for gene in self.genes
            if not gene.provider_specific and gene.portability >= 0.5
        )


@dataclass(frozen=True)
class ExperimentOption:
    option_key: str
    label: str
    expected_information_gain: float
    mission_value: float
    proof_strength_gain: float
    reversibility: float
    estimated_cost: float
    latency_burden: float
    owner_burden: float
    risk: float
    evidence_refs: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        label: str,
        expected_information_gain: float,
        mission_value: float,
        proof_strength_gain: float,
        reversibility: float,
        estimated_cost: float,
        latency_burden: float,
        owner_burden: float,
        risk: float,
        evidence_refs: Iterable[str] = (),
    ) -> "ExperimentOption":
        values = {
            "expected_information_gain": expected_information_gain,
            "mission_value": mission_value,
            "proof_strength_gain": proof_strength_gain,
            "reversibility": reversibility,
            "estimated_cost": estimated_cost,
            "latency_burden": latency_burden,
            "owner_burden": owner_burden,
            "risk": risk,
        }
        if any(value is None for value in values.values()):
            raise ValueError("EXPERIMENT_ECONOMICS_UNKNOWN_VALUE")
        numeric = {key: float(value) for key, value in values.items()}
        if any(not 0.0 <= value <= 1.0 for value in numeric.values()):
            raise ValueError("EXPERIMENT_ECONOMICS_VALUE_OUT_OF_RANGE")
        body = {
            "label": " ".join(label.split()),
            **numeric,
            "evidence_refs": clean(evidence_refs),
        }
        if not body["label"]:
            raise ValueError("EXPERIMENT_LABEL_REQUIRED")
        assert_public_safe(body)
        return cls(option_key=f"FCOS-OPTION-{digest(body)[:24].upper()}", **body)

    @property
    def information_value_score(self) -> float:
        positive = (
            0.32 * self.expected_information_gain
            + 0.24 * self.mission_value
            + 0.18 * self.proof_strength_gain
            + 0.14 * self.reversibility
        )
        penalty = (
            0.04 * self.estimated_cost
            + 0.03 * self.latency_burden
            + 0.03 * self.owner_burden
            + 0.12 * self.risk
        )
        return round(positive - penalty, 9)


class EvidenceEconomicsSelector:
    @staticmethod
    def rank(options: Iterable[ExperimentOption]) -> tuple[ExperimentOption, ...]:
        items = tuple(options)
        if not items:
            raise ValueError("AT_LEAST_ONE_EXPERIMENT_OPTION_REQUIRED")
        return tuple(sorted(items, key=lambda item: (-item.information_value_score, item.option_key)))

    @classmethod
    def select(cls, options: Iterable[ExperimentOption]) -> ExperimentOption:
        return cls.rank(options)[0]


@dataclass(frozen=True)
class CausalTrial:
    trial_key: str
    comparison_key: str
    candidate_key: str
    active_gene_keys: tuple[str, ...]
    outcome_score: float
    evidence_refs: tuple[str, ...]

    @classmethod
    def create(
        cls,
        *,
        comparison_context: Mapping[str, Any],
        candidate_key: str,
        active_gene_keys: Iterable[str],
        outcome_score: float,
        evidence_refs: Iterable[str],
    ) -> "CausalTrial":
        outcome_score = float(outcome_score)
        if not 0.0 <= outcome_score <= 1.0:
            raise ValueError("CAUSAL_OUTCOME_OUT_OF_RANGE")
        refs = clean(evidence_refs)
        if not refs:
            raise ValueError("CAUSAL_TRIAL_EVIDENCE_REQUIRED")
        assert_public_safe(comparison_context)
        body = {
            "comparison_key": digest(comparison_context),
            "candidate_key": candidate_key.strip(),
            "active_gene_keys": clean(active_gene_keys),
            "outcome_score": outcome_score,
            "evidence_refs": refs,
        }
        if not body["candidate_key"] or not body["active_gene_keys"]:
            raise ValueError("CAUSAL_TRIAL_FIELDS_REQUIRED")
        return cls(trial_key=f"FCOS-TRIAL-{digest(body)[:24].upper()}", **body)


@dataclass(frozen=True)
class CausalAttribution:
    attribution_key: str
    changed_gene_key: str
    outcome_delta: float
    direction: str
    comparison_key: str
    evidence_refs: tuple[str, ...]


class CausalAttributionEngine:
    @staticmethod
    def attribute(control: CausalTrial, treatment: CausalTrial) -> CausalAttribution:
        if control.comparison_key != treatment.comparison_key:
            raise ValueError("CAUSAL_TRIAL_NOT_COMPARABLE")
        changed = set(control.active_gene_keys) ^ set(treatment.active_gene_keys)
        if len(changed) != 1:
            raise ValueError("CAUSAL_ATTRIBUTION_REQUIRES_SINGLE_GENE_DELTA")
        delta = round(treatment.outcome_score - control.outcome_score, 9)
        direction = "POSITIVE" if delta > 0 else "NEGATIVE" if delta < 0 else "NEUTRAL"
        refs = clean((*control.evidence_refs, *treatment.evidence_refs))
        body = {
            "changed_gene_key": next(iter(changed)),
            "outcome_delta": delta,
            "direction": direction,
            "comparison_key": control.comparison_key,
            "evidence_refs": refs,
        }
        return CausalAttribution(
            attribution_key=f"FCOS-CAUSE-{digest(body)[:24].upper()}",
            **body,
        )


@dataclass(frozen=True)
class TournamentEntry:
    candidate_key: str
    comparison_key: str
    value: ValueReceipt
    robustness: RobustnessVerdict


@dataclass(frozen=True)
class TournamentVerdict:
    decision: str
    champion_key: str
    winning_key: str
    eligible_keys: tuple[str, ...]
    blocked_keys: tuple[str, ...]
    verdict_sha256: str


class ShadowTournament:
    """Fail-closed champion/challenger comparison with protected floors."""

    @staticmethod
    def evaluate(
        *,
        champion: TournamentEntry,
        challengers: Sequence[TournamentEntry],
        minimum_quality: float | None = None,
        minimum_reliability: float | None = None,
    ) -> TournamentVerdict:
        entries = (champion, *tuple(challengers))
        if any(entry.comparison_key != champion.comparison_key for entry in entries):
            raise ValueError("TOURNAMENT_COMPARISON_KEY_MISMATCH")
        q_floor = champion.value.quality if minimum_quality is None else max(champion.value.quality, float(minimum_quality))
        r_floor = champion.value.reliability if minimum_reliability is None else max(champion.value.reliability, float(minimum_reliability))
        eligible: list[TournamentEntry] = []
        blocked: list[str] = []
        for entry in entries:
            value = entry.value
            protected = (
                value.measured
                and entry.robustness.passed
                and value.quality >= q_floor
                and value.reliability >= r_floor
                and value.owner_burden <= champion.value.owner_burden
            )
            if protected:
                eligible.append(entry)
            else:
                blocked.append(entry.candidate_key)
        if champion not in eligible:
            raise ValueError("CHAMPION_MUST_REMAIN_ELIGIBLE")
        pareto = FinOpsParetoRouter.pareto_front(
            [entry.value for entry in eligible],
            minimum_quality=q_floor,
            minimum_reliability=r_floor,
        )
        value_to_entry = {entry.value.receipt_id: entry for entry in eligible}
        front_entries = tuple(value_to_entry[item.receipt_id] for item in pareto)
        winning_key = champion.candidate_key
        decision = "KEEP_CHAMPION"
        challenger_front = [entry for entry in front_entries if entry.candidate_key != champion.candidate_key]
        if len(front_entries) == 1 and challenger_front:
            contender = challenger_front[0]
            if contender.value.outcome_value > champion.value.outcome_value:
                winning_key = contender.candidate_key
                decision = "CHALLENGER_WINS"
        elif challenger_front:
            decision = "HOLD_NON_UNIQUE_PARETO_FRONT"
        body = {
            "decision": decision,
            "champion_key": champion.candidate_key,
            "winning_key": winning_key,
            "eligible_keys": tuple(sorted(entry.candidate_key for entry in eligible)),
            "blocked_keys": tuple(sorted(blocked)),
            "front_keys": tuple(sorted(entry.candidate_key for entry in front_entries)),
        }
        return TournamentVerdict(
            verdict_sha256=digest(body),
            **{key: value for key, value in body.items() if key != "front_keys"},
        )


@dataclass(frozen=True)
class EvolutionProposal:
    proposal_key: str
    mode: EvolutionMode
    capability_key: str
    source_receiver: str
    target_receiver: str
    description: str
    changes_constitutional_boundary: bool = False
    expands_authority: bool = False
    lowers_proof_threshold: bool = False

    @classmethod
    def create(
        cls,
        *,
        mode: EvolutionMode,
        capability_key: str,
        source_receiver: str,
        target_receiver: str,
        description: str,
        changes_constitutional_boundary: bool = False,
        expands_authority: bool = False,
        lowers_proof_threshold: bool = False,
    ) -> "EvolutionProposal":
        body = {
            "mode": EvolutionMode(mode).value,
            "capability_key": capability_key.strip(),
            "source_receiver": source_receiver.strip(),
            "target_receiver": target_receiver.strip(),
            "description": " ".join(description.split()),
            "changes_constitutional_boundary": bool(changes_constitutional_boundary),
            "expands_authority": bool(expands_authority),
            "lowers_proof_threshold": bool(lowers_proof_threshold),
        }
        if any(not body[key] for key in ("capability_key", "source_receiver", "target_receiver", "description")):
            raise ValueError("EVOLUTION_PROPOSAL_FIELDS_REQUIRED")
        if EvolutionMode(mode) == EvolutionMode.ARCHITECTURAL and not body["changes_constitutional_boundary"]:
            raise ValueError("ARCHITECTURAL_MODE_REQUIRES_BOUNDARY_CHANGE")
        assert_public_safe(body)
        return cls(
            proposal_key=f"FCOS-EVOL-{digest(body)[:24].upper()}",
            mode=EvolutionMode(mode),
            **{key: value for key, value in body.items() if key != "mode"},
        )


@dataclass(frozen=True)
class EvolutionGateVerdict:
    decision: str
    blockers: tuple[str, ...]
    verdict_sha256: str


class ConstitutionalEvolutionGate:
    @staticmethod
    def evaluate(
        proposal: EvolutionProposal,
        *,
        proof_refs: Iterable[str] = (),
        simulation_ref: str = "",
        rollback_ref: str = "",
        independent_readback_ref: str = "",
        owner_approved: bool = False,
        target_lease: CapabilityLease | None = None,
        at: str | None = None,
    ) -> EvolutionGateVerdict:
        blockers: list[str] = []
        refs = clean(proof_refs)
        if proposal.expands_authority:
            blockers.append("AUTHORITY_EXPANSION_NOT_AUTO_PROMOTABLE")
        if proposal.lowers_proof_threshold:
            blockers.append("PROOF_THRESHOLD_REDUCTION_PROHIBITED")
        if not refs:
            blockers.append("PROOF_REQUIRED")
        if not simulation_ref:
            blockers.append("SIMULATION_REQUIRED")
        if not rollback_ref:
            blockers.append("ROLLBACK_REQUIRED")
        if not independent_readback_ref:
            blockers.append("INDEPENDENT_READBACK_REQUIRED")
        if proposal.mode == EvolutionMode.ARCHITECTURAL and not owner_approved:
            blockers.append("OWNER_APPROVAL_REQUIRED_FOR_ARCHITECTURAL_EVOLUTION")
        if proposal.mode == EvolutionMode.HORIZONTAL:
            instant = at or utc_now()
            if (
                target_lease is None
                or target_lease.receiver_id != proposal.target_receiver
                or target_lease.capability_id != proposal.capability_key
                or not target_lease.valid_at(instant)
            ):
                blockers.append("TARGET_RECEIVER_PROOF_LEASE_REQUIRED")
        body = {
            "proposal_key": proposal.proposal_key,
            "blockers": tuple(sorted(set(blockers))),
            "proof_refs": refs,
            "simulation_ref": simulation_ref,
            "rollback_ref": rollback_ref,
            "independent_readback_ref": independent_readback_ref,
            "owner_approved": bool(owner_approved),
            "target_lease_key": target_lease.lease_id if target_lease else "",
        }
        return EvolutionGateVerdict(
            decision="QUALIFIED" if not blockers else "HOLD",
            blockers=tuple(sorted(set(blockers))),
            verdict_sha256=digest(body),
        )


@dataclass(frozen=True)
class ChaosExperiment:
    experiment_key: str
    failure_domain: str
    injected_fault: str
    expected_degraded_state: str
    rollback_required: bool = True
    destructive: bool = False

    @classmethod
    def create(
        cls,
        *,
        failure_domain: str,
        injected_fault: str,
        expected_degraded_state: str,
        destructive: bool = False,
    ) -> "ChaosExperiment":
        body = {
            "failure_domain": failure_domain.strip(),
            "injected_fault": " ".join(injected_fault.split()),
            "expected_degraded_state": expected_degraded_state.strip(),
            "rollback_required": True,
            "destructive": bool(destructive),
        }
        if any(not body[key] for key in ("failure_domain", "injected_fault", "expected_degraded_state")):
            raise ValueError("CHAOS_EXPERIMENT_FIELDS_REQUIRED")
        if body["destructive"]:
            raise ValueError("DESTRUCTIVE_CHAOS_REQUIRES_SEPARATE_AUTHORITY")
        assert_public_safe(body)
        return cls(experiment_key=f"FCOS-CHAOS-{digest(body)[:24].upper()}", **body)


@dataclass(frozen=True)
class RecoveryObservation:
    experiment_key: str
    detected: bool
    isolated: bool
    degraded_state_correct: bool
    rollback_verified: bool
    no_collateral_regression: bool
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class RecoveryVerdict:
    passed: bool
    blockers: tuple[str, ...]
    verdict_sha256: str


class RecoveryCourt:
    @staticmethod
    def evaluate(experiment: ChaosExperiment, observation: RecoveryObservation) -> RecoveryVerdict:
        if observation.experiment_key != experiment.experiment_key:
            raise ValueError("RECOVERY_EXPERIMENT_MISMATCH")
        blockers = []
        checks = {
            "FAULT_NOT_DETECTED": observation.detected,
            "FAILURE_NOT_ISOLATED": observation.isolated,
            "WRONG_DEGRADED_STATE": observation.degraded_state_correct,
            "ROLLBACK_NOT_VERIFIED": observation.rollback_verified,
            "COLLATERAL_REGRESSION": observation.no_collateral_regression,
            "RECOVERY_EVIDENCE_REQUIRED": bool(observation.evidence_refs),
        }
        blockers.extend(name for name, ok in checks.items() if not ok)
        body = {
            "experiment_key": experiment.experiment_key,
            "blockers": tuple(sorted(blockers)),
            "evidence_refs": clean(observation.evidence_refs),
        }
        return RecoveryVerdict(
            passed=not blockers,
            blockers=tuple(sorted(blockers)),
            verdict_sha256=digest(body),
        )


@dataclass(frozen=True)
class ValueRealizationReceipt:
    receipt_key: str
    candidate_key: str
    quality_delta: float
    reliability_delta: float
    latency_delta_ms: float
    cost_delta: float
    owner_burden_delta: float
    outcome_value_delta: float
    protected_floors_preserved: bool
    evidence_refs: tuple[str, ...]

    @classmethod
    def compare(
        cls,
        baseline: ValueReceipt,
        current: ValueReceipt,
        *,
        evidence_refs: Iterable[str],
    ) -> "ValueRealizationReceipt":
        if baseline.candidate_id != current.candidate_id:
            raise ValueError("VALUE_REALIZATION_CANDIDATE_MISMATCH")
        refs = clean(evidence_refs)
        if not refs:
            raise ValueError("VALUE_REALIZATION_EVIDENCE_REQUIRED")
        body = {
            "candidate_key": current.candidate_id,
            "quality_delta": round(current.quality - baseline.quality, 9),
            "reliability_delta": round(current.reliability - baseline.reliability, 9),
            "latency_delta_ms": round(current.latency_ms - baseline.latency_ms, 9),
            "cost_delta": round(current.cost - baseline.cost, 9),
            "owner_burden_delta": round(current.owner_burden - baseline.owner_burden, 9),
            "outcome_value_delta": round(current.outcome_value - baseline.outcome_value, 9),
            "protected_floors_preserved": (
                current.quality >= baseline.quality
                and current.reliability >= baseline.reliability
                and current.owner_burden <= baseline.owner_burden
            ),
            "evidence_refs": refs,
        }
        return cls(receipt_key=f"FCOS-VALUE-{digest(body)[:24].upper()}", **body)

    @property
    def positive_operational_value(self) -> bool:
        return self.protected_floors_preserved and self.outcome_value_delta > 0


@dataclass(frozen=True)
class EvidencePointer:
    pointer_key: str
    storage_ref: str
    content_sha256: str
    byte_count: int
    excerpt: str
    chunk_count: int
    raw_inline: bool = False


class EvidenceVirtualizer:
    """Keep large evidence out of chat/Sheets while preserving verifiable pointers."""

    @staticmethod
    def chunk_text(text: str, *, target_chars: int = DEFAULT_EVIDENCE_CHUNK) -> tuple[str, ...]:
        target_chars = int(target_chars)
        if target_chars <= 0 or target_chars >= SHEETS_HARD_CELL_LIMIT:
            raise ValueError("EVIDENCE_CHUNK_LIMIT_INVALID")
        if not text:
            return ("",)
        return tuple(text[index:index + target_chars] for index in range(0, len(text), target_chars))

    @classmethod
    def virtualize(
        cls,
        *,
        storage_ref: str,
        content: str | bytes,
        excerpt_chars: int = 512,
        target_chars: int = DEFAULT_EVIDENCE_CHUNK,
    ) -> EvidencePointer:
        if isinstance(content, str):
            raw = content.encode("utf-8")
            rendered = content
        else:
            raw = bytes(content)
            rendered = raw.decode("utf-8", errors="replace")
        chunks = cls.chunk_text(rendered, target_chars=target_chars)
        body = {
            "storage_ref": storage_ref.strip(),
            "content_sha256": hashlib.sha256(raw).hexdigest(),
            "byte_count": len(raw),
            "excerpt": rendered[:max(0, min(int(excerpt_chars), 1024))],
            "chunk_count": len(chunks),
            "raw_inline": False,
        }
        if not body["storage_ref"]:
            raise ValueError("EVIDENCE_STORAGE_REF_REQUIRED")
        assert_public_safe(body)
        return EvidencePointer(pointer_key=f"FCOS-EVID-{digest(body)[:24].upper()}", **body)


@dataclass(frozen=True)
class DiscoveryProbe:
    probe_key: str
    terms: tuple[str, ...]
    maximum_result_chars: int


class BoundedDiscoveryPlanner:
    """Prevents provider discovery output from exceeding receiver payload limits."""

    @staticmethod
    def plan(
        terms: Iterable[str],
        *,
        max_terms_per_probe: int = 3,
        maximum_result_chars: int = 12_000,
    ) -> tuple[DiscoveryProbe, ...]:
        unique = clean(terms)
        max_terms_per_probe = int(max_terms_per_probe)
        maximum_result_chars = int(maximum_result_chars)
        if max_terms_per_probe <= 0:
            raise ValueError("DISCOVERY_TERM_BATCH_INVALID")
        if maximum_result_chars <= 0 or maximum_result_chars >= SHEETS_HARD_CELL_LIMIT:
            raise ValueError("DISCOVERY_RESULT_LIMIT_INVALID")
        probes = []
        for index in range(0, len(unique), max_terms_per_probe):
            batch = unique[index:index + max_terms_per_probe]
            body = {"terms": batch, "maximum_result_chars": maximum_result_chars}
            probes.append(
                DiscoveryProbe(
                    probe_key=f"FCOS-DISC-{digest(body)[:24].upper()}",
                    terms=batch,
                    maximum_result_chars=maximum_result_chars,
                )
            )
        return tuple(probes)


class Stage20Bridge:
    """Bridge FC-OS genomes into the existing Stage-20 maturity controller."""

    @staticmethod
    def to_maturation_gap(
        genome: CapabilityGenome,
        *,
        system_key: str,
        stage: Any,
        mission_value_gain: float,
        failure_recurrence_reduction: float,
        owner_burden_reduction: float,
        proof_strength_gain: float,
        resilience_gain: float,
        capability_reuse_gain: float,
        reversibility: float = 1.0,
        cost: float = 0.0,
        risk: float = 0.0,
        evidence_refs: Iterable[str] = (),
    ) -> Any:
        from evidenceops.caseforge.autonomous_maturation import MaturationGap
        return MaturationGap(
            gap_id=f"FCOS-GAP-{genome.genome_key[-20:]}",
            system_id=system_key,
            stage=stage,
            description=f"Qualify capability genome {genome.genome_key} for {genome.capability_class}.",
            mission_value_gain=mission_value_gain,
            failure_recurrence_reduction=failure_recurrence_reduction,
            owner_burden_reduction=owner_burden_reduction,
            proof_strength_gain=proof_strength_gain,
            resilience_gain=resilience_gain,
            capability_reuse_gain=capability_reuse_gain,
            reversibility=reversibility,
            cost=cost,
            risk=risk,
            evidence_refs=clean(evidence_refs),
        )


@dataclass(frozen=True)
class FCOSPlan:
    plan_key: str
    genome_key: str
    selected_experiment_key: str
    evolution_mode: EvolutionMode
    authority_ceiling: str
    external_effect: bool
    next_gate: str


class FrontierConvergenceOS:
    """Internal coordinator. External/provider effects remain in SOVARA."""

    def plan(
        self,
        *,
        genome: CapabilityGenome,
        experiment_options: Sequence[ExperimentOption],
        evolution_mode: EvolutionMode,
    ) -> FCOSPlan:
        selected = EvidenceEconomicsSelector.select(experiment_options)
        mode = EvolutionMode(evolution_mode)
        next_gate = (
            "OWNER_CONSTITUTIONAL_REVIEW"
            if mode == EvolutionMode.ARCHITECTURAL
            else "SHADOW_TOURNAMENT"
        )
        body = {
            "genome_key": genome.genome_key,
            "selected_experiment_key": selected.option_key,
            "evolution_mode": mode.value,
            "authority_ceiling": AUTHORITY_CEILING,
            "external_effect": False,
            "next_gate": next_gate,
        }
        return FCOSPlan(
            plan_key=f"FCOS-PLAN-{digest(body)[:24].upper()}",
            genome_key=genome.genome_key,
            selected_experiment_key=selected.option_key,
            evolution_mode=mode,
            authority_ceiling=AUTHORITY_CEILING,
            external_effect=False,
            next_gate=next_gate,
        )


__all__ = [
    "AUTHORITY_CEILING",
    "EXTERNAL_EFFECT_DEFAULT",
    "SHEETS_HARD_CELL_LIMIT",
    "BoundedDiscoveryPlanner",
    "CapabilityGene",
    "CapabilityGenome",
    "CausalAttribution",
    "CausalAttributionEngine",
    "CausalTrial",
    "ChaosExperiment",
    "ConstitutionalEvolutionGate",
    "DiscoveryProbe",
    "EvidenceEconomicsSelector",
    "EvidencePointer",
    "EvidenceVirtualizer",
    "EvolutionGateVerdict",
    "EvolutionMode",
    "EvolutionProposal",
    "ExperimentOption",
    "FCOSPlan",
    "FrontierConvergenceOS",
    "RecoveryCourt",
    "RecoveryObservation",
    "RecoveryVerdict",
    "ShadowTournament",
    "Stage20Bridge",
    "TournamentEntry",
    "TournamentVerdict",
    "ValueRealizationReceipt",
]
