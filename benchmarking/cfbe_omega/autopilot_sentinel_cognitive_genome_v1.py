from __future__ import annotations

"""FUSE Autopilot-Sentinel Cognitive Genome (FASCG) v1.

Clean-room, effect-free integration profile over the existing Federation owners:
- CFBE Full-Autopilot + Meta-Cognition Fabric v1;
- Sentinel Omega observability/causal/immune primitives;
- AO-CEF cognitive-evolution genome and verifier ecology;
- CFBE vNext multi-stream Formation;
- AO-Harmonic resource market;
- Bubbles mission/recovery host.

This module is deliberately *not* a new sovereign scheduler, provider executor,
authority plane, proof root, memory root, model trainer, or production self-mutator.
It compiles a typed genome and deterministic internal decision courts only.
"""

from dataclasses import dataclass
from enum import Enum, StrEnum
from hashlib import sha256
import json
import math
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "FUSE-AUTOPILOT-SENTINEL-COGNITIVE-GENOME-V1"
GENOME_SIZE = 144
PROVIDER_EFFECT_AUTHORIZED = False
MODEL_TRAINING_AUTHORIZED = False
AUTHORITY_MINTING_AUTHORIZED = False
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
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{label}_OUT_OF_RANGE")
    return value


class GeneDisposition(StrEnum):
    REUSE = "REUSE"
    EXTEND = "EXTEND"
    BUILD_RESIDUAL = "BUILD_RESIDUAL"
    RESEARCH_GATED = "RESEARCH_GATED"
    PROVIDER_GATED = "PROVIDER_GATED"


class PlasticityClock(StrEnum):
    FAST = "FAST"
    MEDIUM = "MEDIUM"
    SLOW = "SLOW"
    VERY_SLOW = "VERY_SLOW"
    OWNER_GATED = "OWNER_GATED"


class GeneDomain(StrEnum):
    HOMEOSTASIS = "HOMEOSTASIS"
    MISSION_AUTOPILOT = "MISSION_AUTOPILOT"
    SENTINEL_CELL_ECOLOGY = "SENTINEL_CELL_ECOLOGY"
    CAUSAL_GRAPH = "CAUSAL_GRAPH"
    ACTIVE_SENSING = "ACTIVE_SENSING"
    PRECURSOR_PREDICTION = "PRECURSOR_PREDICTION"
    AUTONOMIC_REPAIR = "AUTONOMIC_REPAIR"
    AGENT_SECURITY = "AGENT_SECURITY"
    NEURAL_COGNITION = "NEURAL_COGNITION"
    EVOLUTION = "EVOLUTION"
    DURABILITY_INTEROP = "DURABILITY_INTEROP"
    ASSURANCE_VALUE = "ASSURANCE_VALUE"


@dataclass(frozen=True, slots=True)
class CognitiveGene:
    gene_id: str
    domain: GeneDomain
    capability: str
    disposition: GeneDisposition
    receiver: str
    plasticity: PlasticityClock
    invariants: tuple[str, ...]
    frontier_gene: str

    def validate(self) -> "CognitiveGene":
        if not self.gene_id or not self.capability.strip() or not self.receiver.strip() or not self.frontier_gene.strip():
            raise ValueError("FASCG_GENE_IDENTITY_REQUIRED")
        if not self.invariants:
            raise ValueError("FASCG_GENE_INVARIANTS_REQUIRED")
        return self


DOMAIN_CAPABILITIES: Mapping[GeneDomain, tuple[str, ...]] = {
    GeneDomain.HOMEOSTASIS: (
        "Mission health vector",
        "Risk-envelope controller",
        "Evidence-debt regulator",
        "Owner-attention budget",
        "SLO/error-budget integration",
        "Cost-pressure regulator",
        "Safety-floor regulator",
        "Reliability-floor regulator",
        "Intervention-budget regulator",
        "Uncertainty-budget regulator",
        "Adaptive autonomy hysteresis",
        "Graceful autonomy degradation ladder",
    ),
    GeneDomain.MISSION_AUTOPILOT: (
        "Objective-drift detector",
        "Dependency-critical-path autopilot",
        "Autonomous next-best-action selector",
        "Dynamic specialist Formation planner",
        "Multi-mission WIP arbitration",
        "Provider-health-aware route selector",
        "Reflection return-on-compute gate",
        "Independent challenger-plan generator",
        "Compensation/rollback plan compiler",
        "Exact owner-trigger predicate",
        "Semantic terminality court",
        "Correlated successor-dispatch contract",
    ),
    GeneDomain.SENTINEL_CELL_ECOLOGY: (
        "Reliability Sentinel cell",
        "Security Sentinel cell",
        "Identity Sentinel cell",
        "Cloud-network Sentinel cell",
        "Data-privacy Sentinel cell",
        "Agent-runtime Sentinel cell",
        "Evidence-proof Sentinel cell",
        "Mobile-client Sentinel cell",
        "Cost-performance Sentinel cell",
        "Owner-value Sentinel cell",
        "Sentinel-of-Sentinel integrity cell",
        "Dynamic cell formation and dissolution",
    ),
    GeneDomain.CAUSAL_GRAPH: (
        "Continuous dependency graph",
        "Temporal causality ordering",
        "Change-to-regression attribution",
        "Differential diagnosis",
        "Probable-origin ranking",
        "Sandboxed causal intervention court",
        "Counterfactual graph simulation",
        "Blast-radius propagation map",
        "Attack-path reasoning",
        "Claim-to-evidence causal chain",
        "Causal-confidence calibration",
        "Verified-root-cause promotion court",
    ),
    GeneDomain.ACTIVE_SENSING: (
        "Information-gain observation selector",
        "Missing-evidence query planner",
        "Trace-expansion planner",
        "Metric/log evidence request planner",
        "Provider-readback request planner",
        "Synthetic no-effect probe planner",
        "Cost-aware observation budget",
        "Uncertainty-decomposition planner",
        "Evidence sufficiency stop rule",
        "Adversarial source cross-check",
        "Sensor trust score",
        "Active hypothesis pruning",
    ),
    GeneDomain.PRECURSOR_PREDICTION: (
        "Heartbeat cadence forecaster",
        "Learned precursor signature library",
        "Multi-window SLO burn prediction",
        "Concept-drift detector",
        "Change-risk forecaster",
        "Queue/backlog precursor",
        "Anomaly trajectory forecast",
        "Failure-recurrence hazard score",
        "Owner-burden forecast",
        "Predictive digital-twin risk simulation",
        "Forecast uncertainty interval",
        "Prevention-dividend estimator",
    ),
    GeneDomain.AUTONOMIC_REPAIR: (
        "Failure fingerprint memory",
        "Smallest-safe-repair selector",
        "Repair route competition",
        "Canary-first repair contract",
        "Semantic readback requirement",
        "Automatic rollback contract",
        "Dependency circuit breaker",
        "Poison-work quarantine/dead-letter lane",
        "Changed-route recovery rule",
        "Saga compensation planner",
        "Governed closed-loop response boundary",
        "Repair-outcome learning",
    ),
    GeneDomain.AGENT_SECURITY: (
        "Per-agent capability allowlist",
        "Identity/action binding",
        "Prompt-injection and tool-misuse sentinel",
        "Telemetry integrity/poisoning sentinel",
        "Data-exfiltration guard",
        "Model/tool supply-chain provenance",
        "Cross-agent compromise propagation map",
        "Risk-adaptive approval boundary",
        "Complete action audit trail",
        "Agent quarantine/isolation",
        "Adversarial agent red-team court",
        "Independent sentinel integrity verification",
    ),
    GeneDomain.NEURAL_COGNITION: (
        "Attention working-context substrate",
        "Durable external memory substrate",
        "Test-time neural-memory passport",
        "State-space/Mamba recurrence option",
        "Sparse-MoE specialist-routing option",
        "JEPA predictive world-model option",
        "Temporal-synchronization/CTM option",
        "Multi-token/speculative throughput option",
        "Surprise/novelty neural signal",
        "Memory consolidation policy",
        "Cross-model distillation passport",
        "Neural-architecture search contract",
    ),
    GeneDomain.EVOLUTION: (
        "Quality-diversity archive",
        "Island-population evolution",
        "Mutation-operator market",
        "Failure-derived eval synthesis",
        "Causal mutation attribution",
        "Learning-frontier curriculum",
        "Self-play incident generation",
        "Adversarial red/blue co-evolution",
        "Cross-model/harness/domain transfer court",
        "Catastrophic-forgetting court",
        "Stable-promotion hysteresis",
        "Cold-slate next-generation compiler",
    ),
    GeneDomain.DURABILITY_INTEROP: (
        "Durable event history",
        "Material-step checkpoints",
        "Crash-resume without duplicate work",
        "Exact idempotent replay identity",
        "Zero-compute external-wait parking",
        "MCP/A2A interoperability contract",
        "Runtime capability transpiler",
        "Cognitive-state version graph",
        "Cross-runtime migration passport",
        "FUSE multi-surface integration bridge",
        "Collision-safe multistream execution graph",
        "Single sovereign external-effect commit lane",
    ),
    GeneDomain.ASSURANCE_VALUE: (
        "Independent verifier ecology",
        "Hidden holdout/evaluator secrecy",
        "Chain-of-Evidence court",
        "Anti-Goodhart/reward-hacking court",
        "False-positive/false-negative calibration",
        "MTTR and recovery-quality measurement",
        "Prevention-dividend measurement",
        "Owner-attention-saved measurement",
        "Autonomic Resilience Yield metric",
        "Composite Frontier Baseline",
        "Ten-X lower-confidence-bound court",
        "Rollback/provenance/transfer terminal court",
    ),
}


_DOMAIN_RECEIVER = {
    GeneDomain.HOMEOSTASIS: "CFBE Autopilot + Sentinel + AO-Harmonic",
    GeneDomain.MISSION_AUTOPILOT: "CFBE Full-Autopilot + Formation + Bubbles/F130",
    GeneDomain.SENTINEL_CELL_ECOLOGY: "Sentinel Omega + CFBE vNext MultiStream",
    GeneDomain.CAUSAL_GRAPH: "Sentinel Omega + Living State + Digital Twin + ProofOS",
    GeneDomain.ACTIVE_SENSING: "Sentinel Omega + CFBE ResourceMarket + EvidenceOps",
    GeneDomain.PRECURSOR_PREDICTION: "Sentinel Omega + Digital Twin + Failure-Win",
    GeneDomain.AUTONOMIC_REPAIR: "Sentinel Omega + Bubbles Recovery + SOVARA",
    GeneDomain.AGENT_SECURITY: "Sentinel Omega + SOVARA + ProofOS + Agent Fabric",
    GeneDomain.NEURAL_COGNITION: "AO-CEF Neural Substrate Portfolio + runtime passports",
    GeneDomain.EVOLUTION: "AO-CEF + CFBE + Formation + ProofOS",
    GeneDomain.DURABILITY_INTEROP: "CFBE vNext + BMF + Bubbles + Capability Transpiler",
    GeneDomain.ASSURANCE_VALUE: "ProofOS + JARVIS + CFBE + Human-First Value",
}


_BUILD_CAPABILITIES = {
    "Mission health vector",
    "Risk-envelope controller",
    "Intervention-budget regulator",
    "Uncertainty-budget regulator",
    "Dynamic cell formation and dissolution",
    "Sandboxed causal intervention court",
    "Verified-root-cause promotion court",
    "Information-gain observation selector",
    "Missing-evidence query planner",
    "Synthetic no-effect probe planner",
    "Sensor trust score",
    "Active hypothesis pruning",
    "Telemetry integrity/poisoning sentinel",
    "Cross-agent compromise propagation map",
    "Agent quarantine/isolation",
    "Island-population evolution",
    "Autonomic Resilience Yield metric",
    "Ten-X lower-confidence-bound court",
}

_RESEARCH_CAPABILITIES = {
    "Test-time neural-memory passport",
    "State-space/Mamba recurrence option",
    "Sparse-MoE specialist-routing option",
    "JEPA predictive world-model option",
    "Temporal-synchronization/CTM option",
    "Cross-model distillation passport",
    "Neural-architecture search contract",
}

_PROVIDER_CAPABILITIES = {
    "Provider-health-aware route selector",
    "Provider-readback request planner",
    "Cross-runtime migration passport",
    "Single sovereign external-effect commit lane",
}

_EXTEND_CAPABILITIES = {
    "Evidence-debt regulator",
    "Adaptive autonomy hysteresis",
    "Dynamic specialist Formation planner",
    "Correlated successor-dispatch contract",
    "Security Sentinel cell",
    "Identity Sentinel cell",
    "Cloud-network Sentinel cell",
    "Data-privacy Sentinel cell",
    "Agent-runtime Sentinel cell",
    "Evidence-proof Sentinel cell",
    "Mobile-client Sentinel cell",
    "Sentinel-of-Sentinel integrity cell",
    "Counterfactual graph simulation",
    "Attack-path reasoning",
    "Claim-to-evidence causal chain",
    "Causal-confidence calibration",
    "Cost-aware observation budget",
    "Uncertainty-decomposition planner",
    "Adversarial source cross-check",
    "Learned precursor signature library",
    "Concept-drift detector",
    "Change-risk forecaster",
    "Anomaly trajectory forecast",
    "Predictive digital-twin risk simulation",
    "Forecast uncertainty interval",
    "Prevention-dividend estimator",
    "Governed closed-loop response boundary",
    "Repair-outcome learning",
    "Prompt-injection and tool-misuse sentinel",
    "Data-exfiltration guard",
    "Model/tool supply-chain provenance",
    "Risk-adaptive approval boundary",
    "Adversarial agent red-team court",
    "Independent sentinel integrity verification",
    "Durable external memory substrate",
    "Surprise/novelty neural signal",
    "Memory consolidation policy",
    "Self-play incident generation",
    "Adversarial red/blue co-evolution",
    "Runtime capability transpiler",
    "Cognitive-state version graph",
    "FUSE multi-surface integration bridge",
    "Chain-of-Evidence court",
    "Anti-Goodhart/reward-hacking court",
    "False-positive/false-negative calibration",
    "Prevention-dividend measurement",
    "Owner-attention-saved measurement",
}


def _disposition(capability: str) -> GeneDisposition:
    if capability in _BUILD_CAPABILITIES:
        return GeneDisposition.BUILD_RESIDUAL
    if capability in _RESEARCH_CAPABILITIES:
        return GeneDisposition.RESEARCH_GATED
    if capability in _PROVIDER_CAPABILITIES:
        return GeneDisposition.PROVIDER_GATED
    if capability in _EXTEND_CAPABILITIES:
        return GeneDisposition.EXTEND
    return GeneDisposition.REUSE


def _plasticity(domain: GeneDomain, capability: str) -> PlasticityClock:
    if domain in {GeneDomain.ACTIVE_SENSING, GeneDomain.PRECURSOR_PREDICTION, GeneDomain.HOMEOSTASIS}:
        return PlasticityClock.FAST
    if domain in {GeneDomain.MISSION_AUTOPILOT, GeneDomain.SENTINEL_CELL_ECOLOGY, GeneDomain.AUTONOMIC_REPAIR, GeneDomain.DURABILITY_INTEROP}:
        return PlasticityClock.MEDIUM
    if domain in {GeneDomain.CAUSAL_GRAPH, GeneDomain.AGENT_SECURITY, GeneDomain.EVOLUTION, GeneDomain.ASSURANCE_VALUE}:
        return PlasticityClock.SLOW
    if capability in _RESEARCH_CAPABILITIES:
        return PlasticityClock.OWNER_GATED
    return PlasticityClock.VERY_SLOW


def load_genome() -> tuple[CognitiveGene, ...]:
    genes: list[CognitiveGene] = []
    cursor = 1
    for domain in GeneDomain:
        names = DOMAIN_CAPABILITIES[domain]
        if len(names) != 12:
            raise ValueError(f"FASCG_DOMAIN_EXPECTED_12:{domain}")
        for capability in names:
            genes.append(
                CognitiveGene(
                    gene_id=f"FASCG-{cursor:03d}",
                    domain=domain,
                    capability=capability,
                    disposition=_disposition(capability),
                    receiver=_DOMAIN_RECEIVER[domain],
                    plasticity=_plasticity(domain, capability),
                    invariants=(
                        "NO_SELF_GRANTED_AUTHORITY",
                        "PROOF_STRENGTH_NOT_GREATER_THAN_EVIDENCE",
                        "NO_DIRECT_PRODUCTION_SELF_MUTATION",
                        "ROLLBACK_AND_PROVENANCE_REQUIRED_FOR_PROMOTION",
                    ),
                    frontier_gene=f"CLEAN_ROOM::{domain.value}::{capability}",
                ).validate()
            )
            cursor += 1
    validate_genome(tuple(genes))
    return tuple(genes)


def validate_genome(genes: Sequence[CognitiveGene]) -> None:
    if len(genes) != GENOME_SIZE:
        raise ValueError(f"FASCG_EXPECTED_{GENOME_SIZE}_GOT_{len(genes)}")
    ids = [g.gene_id for g in genes]
    if ids != [f"FASCG-{i:03d}" for i in range(1, GENOME_SIZE + 1)]:
        raise ValueError("FASCG_ID_SEQUENCE_INVALID")
    if len(set(ids)) != GENOME_SIZE:
        raise ValueError("FASCG_DUPLICATE_GENE_ID")
    if any(len(DOMAIN_CAPABILITIES[d]) != 12 for d in GeneDomain):
        raise ValueError("FASCG_DOMAIN_SHAPE_INVALID")


def genome_receipt() -> Mapping[str, Any]:
    genes = load_genome()
    by_disposition = {d.value: sum(g.disposition is d for g in genes) for d in GeneDisposition}
    by_domain = {d.value: sum(g.domain is d for g in genes) for d in GeneDomain}
    body = {
        "schema": SCHEMA,
        "gene_count": len(genes),
        "by_disposition": by_disposition,
        "by_domain": by_domain,
        "provider_effect_authorized": False,
        "model_training_authorized": False,
        "production_self_mutation_authorized": False,
        "ten_x_verified": False,
        "genes": [(g.gene_id, g.domain.value, g.capability, g.disposition.value, g.plasticity.value) for g in genes],
    }
    return {**body, "sha256": _hash(body)}


class HomeostasisAction(StrEnum):
    CONTINUE = "CONTINUE"
    ACTIVE_SENSE = "ACTIVE_SENSE"
    FORM_SENTINEL_CELLS = "FORM_SENTINEL_CELLS"
    CHALLENGE = "CHALLENGE"
    REPLAN = "REPLAN"
    SIMULATE_INTERVENTION = "SIMULATE_INTERVENTION"
    ROLLBACK = "ROLLBACK"
    QUARANTINE = "QUARANTINE"
    DEGRADE_AUTONOMY = "DEGRADE_AUTONOMY"
    HOLD_OWNER = "HOLD_OWNER"


@dataclass(frozen=True, slots=True)
class MissionHomeostasisState:
    quality: float
    safety: float
    reliability: float
    evidence_coverage: float
    uncertainty: float
    cost_pressure: float
    latency_pressure: float
    owner_burden: float
    blast_radius_risk: float
    adversarial_risk: float
    progress: float
    autonomy_trust: float
    repeated_failures: int = 0
    owner_only_decision: bool = False

    def validate(self) -> "MissionHomeostasisState":
        for label in (
            "quality", "safety", "reliability", "evidence_coverage", "uncertainty",
            "cost_pressure", "latency_pressure", "owner_burden", "blast_radius_risk",
            "adversarial_risk", "progress", "autonomy_trust",
        ):
            _unit(getattr(self, label), label.upper())
        if self.repeated_failures < 0:
            raise ValueError("FASCG_REPEATED_FAILURES_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class HomeostasisDecision:
    action: HomeostasisAction
    reasons: tuple[str, ...]
    autonomy_multiplier: float
    external_effect_authorized: bool = False


class MissionHomeostasisController:
    """Conservative mission-level regulator integrating Autopilot and Sentinel state."""

    def decide(self, state: MissionHomeostasisState) -> HomeostasisDecision:
        state.validate()
        if state.owner_only_decision:
            return HomeostasisDecision(HomeostasisAction.HOLD_OWNER, ("GENUINE_OWNER_ONLY_DECISION",), 0.0)
        if state.adversarial_risk >= 0.85:
            return HomeostasisDecision(HomeostasisAction.QUARANTINE, ("ADVERSARIAL_RISK_CRITICAL",), 0.0)
        if state.repeated_failures >= 3:
            return HomeostasisDecision(HomeostasisAction.ROLLBACK, ("REPEATED_FAILURE_THRESHOLD",), 0.1)
        if state.safety < 0.90 or state.reliability < 0.85:
            return HomeostasisDecision(HomeostasisAction.DEGRADE_AUTONOMY, ("SAFETY_OR_RELIABILITY_FLOOR",), 0.15)
        if state.evidence_coverage < 0.55 or state.uncertainty > 0.65:
            return HomeostasisDecision(HomeostasisAction.ACTIVE_SENSE, ("EVIDENCE_OR_UNCERTAINTY_GAP",), 0.35)
        if state.blast_radius_risk >= 0.70:
            return HomeostasisDecision(HomeostasisAction.SIMULATE_INTERVENTION, ("HIGH_BLAST_RADIUS_REQUIRES_COUNTERFACTUAL",), 0.25)
        if state.progress < 0.25 and (state.cost_pressure >= 0.7 or state.latency_pressure >= 0.7):
            return HomeostasisDecision(HomeostasisAction.REPLAN, ("LOW_PROGRESS_HIGH_RESOURCE_PRESSURE",), 0.45)
        if state.adversarial_risk >= 0.50:
            return HomeostasisDecision(HomeostasisAction.FORM_SENTINEL_CELLS, ("MULTI_DOMAIN_SENTINEL_REVIEW",), 0.50)
        if state.autonomy_trust < 0.45:
            return HomeostasisDecision(HomeostasisAction.CHALLENGE, ("AUTONOMY_TRUST_LOW",), 0.40)
        multiplier = max(0.0, min(1.0, min(state.autonomy_trust, state.evidence_coverage, state.safety, state.reliability)))
        return HomeostasisDecision(HomeostasisAction.CONTINUE, ("MISSION_WITHIN_HOMEOSTATIC_ENVELOPE",), round(multiplier, 6))


class SentinelDomain(StrEnum):
    RELIABILITY = "RELIABILITY"
    SECURITY = "SECURITY"
    IDENTITY = "IDENTITY"
    CLOUD_NETWORK = "CLOUD_NETWORK"
    DATA_PRIVACY = "DATA_PRIVACY"
    AGENT_RUNTIME = "AGENT_RUNTIME"
    EVIDENCE = "EVIDENCE"
    MOBILE_CLIENT = "MOBILE_CLIENT"
    COST_PERFORMANCE = "COST_PERFORMANCE"
    OWNER_VALUE = "OWNER_VALUE"
    INTEGRITY = "INTEGRITY"


@dataclass(frozen=True, slots=True)
class SentinelCell:
    cell_id: str
    domain: SentinelDomain
    priority: float
    evidence_refs: tuple[str, ...]
    collision_keys: tuple[str, ...]
    authority_ceiling: str = "A1_INTERNAL"
    external_effect: bool = False

    def validate(self) -> "SentinelCell":
        if not self.cell_id.strip() or not 0 <= self.priority <= 1 or not self.evidence_refs:
            raise ValueError("FASCG_SENTINEL_CELL_INVALID")
        if self.external_effect:
            raise ValueError("FASCG_SENTINEL_CELL_EFFECT_FORBIDDEN")
        return self


_DOMAIN_KEYWORDS: Mapping[SentinelDomain, tuple[str, ...]] = {
    SentinelDomain.RELIABILITY: ("latency", "error", "availability", "slo", "heartbeat", "queue"),
    SentinelDomain.SECURITY: ("threat", "malware", "exploit", "attack", "injection", "compromise"),
    SentinelDomain.IDENTITY: ("identity", "auth", "oauth", "token", "credential", "permission"),
    SentinelDomain.CLOUD_NETWORK: ("cloud", "network", "dns", "gateway", "route", "firewall"),
    SentinelDomain.DATA_PRIVACY: ("privacy", "secret", "pii", "data", "exfiltration", "leak"),
    SentinelDomain.AGENT_RUNTIME: ("agent", "model", "tool", "prompt", "runtime", "handoff"),
    SentinelDomain.EVIDENCE: ("proof", "evidence", "receipt", "contradiction", "claim", "attestation"),
    SentinelDomain.MOBILE_CLIENT: ("android", "ios", "mobile", "client", "device", "app"),
    SentinelDomain.COST_PERFORMANCE: ("cost", "token", "throughput", "performance", "compute", "budget"),
    SentinelDomain.OWNER_VALUE: ("owner", "burden", "interruption", "value", "time", "approval"),
    SentinelDomain.INTEGRITY: ("sentinel", "tamper", "poison", "integrity", "spoof", "observer"),
}


@dataclass(frozen=True, slots=True)
class SentinelFormationPlan:
    cells: tuple[SentinelCell, ...]
    max_parallel: int
    plan_sha256: str


class SentinelCellEcology:
    """Forms bounded, non-effectful specialist cells from incident semantics."""

    @staticmethod
    def form(signals: Sequence[str], *, evidence_refs: Sequence[str], max_parallel: int = 6) -> SentinelFormationPlan:
        refs = _clean(evidence_refs)
        if not refs:
            raise ValueError("FASCG_SENTINEL_EVIDENCE_REQUIRED")
        if max_parallel < 1:
            raise ValueError("FASCG_SENTINEL_MAX_PARALLEL_INVALID")
        text = " ".join(str(x).casefold() for x in signals)
        scores: list[tuple[float, SentinelDomain]] = []
        for domain, keywords in _DOMAIN_KEYWORDS.items():
            hit = sum(1 for kw in keywords if kw in text)
            if hit:
                scores.append((min(1.0, 0.25 + 0.15 * hit), domain))
        if not scores:
            scores = [(0.35, SentinelDomain.RELIABILITY), (0.30, SentinelDomain.EVIDENCE)]
        scores.sort(key=lambda x: (-x[0], x[1].value))
        cells = []
        for score, domain in scores[:max_parallel]:
            body = {"domain": domain.value, "signals": sorted(map(str, signals)), "refs": refs}
            cells.append(SentinelCell(
                cell_id=f"SCELL-{domain.value}-{_hash(body)[:12].upper()}",
                domain=domain,
                priority=round(score, 6),
                evidence_refs=refs,
                collision_keys=(f"sentinel:{domain.value.lower()}",),
            ).validate())
        body = [(c.cell_id, c.domain.value, c.priority) for c in cells]
        return SentinelFormationPlan(tuple(cells), min(max_parallel, len(cells)), _hash(body))


@dataclass(frozen=True, slots=True)
class SensingCandidate:
    sensing_id: str
    hypothesis_id: str
    expected_information_gain: float
    cost: float
    latency: float
    privacy_risk: float
    corruption_risk: float
    no_effect: bool = True

    def validate(self) -> "SensingCandidate":
        if not self.sensing_id.strip() or not self.hypothesis_id.strip():
            raise ValueError("FASCG_SENSING_IDENTITY_REQUIRED")
        for label in ("expected_information_gain", "privacy_risk", "corruption_risk"):
            _unit(getattr(self, label), label.upper())
        for label in ("cost", "latency"):
            value = getattr(self, label)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0:
                raise ValueError(f"FASCG_{label.upper()}_INVALID")
        if not self.no_effect:
            raise ValueError("FASCG_ACTIVE_SENSING_EFFECT_FORBIDDEN")
        return self


class ActiveSensingPlanner:
    EPSILON = 1e-9

    @staticmethod
    def score(candidate: SensingCandidate) -> float:
        candidate.validate()
        positive = candidate.expected_information_gain * (1.0 - candidate.corruption_risk)
        burden = candidate.cost + candidate.latency + 2.0 * candidate.privacy_risk + ActiveSensingPlanner.EPSILON
        return positive / burden

    def rank(self, candidates: Sequence[SensingCandidate]) -> tuple[SensingCandidate, ...]:
        validated = [c.validate() for c in candidates]
        return tuple(sorted(validated, key=lambda c: (-self.score(c), c.sensing_id)))

    def best(self, candidates: Sequence[SensingCandidate], *, minimum_information_gain: float = 0.05) -> SensingCandidate | None:
        _unit(minimum_information_gain, "MINIMUM_INFORMATION_GAIN")
        ranked = [c for c in self.rank(candidates) if c.expected_information_gain >= minimum_information_gain]
        return ranked[0] if ranked else None


@dataclass(frozen=True, slots=True)
class InterventionCandidate:
    intervention_id: str
    target: str
    predicted_risk_reduction: float
    predicted_quality_delta: float
    predicted_cost_delta: float
    blast_radius: float
    reversible: bool
    simulation_only: bool
    evidence_refs: tuple[str, ...]

    def validate(self) -> "InterventionCandidate":
        if not self.intervention_id.strip() or not self.target.strip() or not self.evidence_refs:
            raise ValueError("FASCG_INTERVENTION_IDENTITY_REQUIRED")
        _unit(self.predicted_risk_reduction, "INTERVENTION_RISK_REDUCTION")
        _unit(self.blast_radius, "INTERVENTION_BLAST_RADIUS")
        for label in ("predicted_quality_delta", "predicted_cost_delta"):
            value = getattr(self, label)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError(f"FASCG_{label.upper()}_INVALID")
        if not self.reversible or not self.simulation_only:
            raise ValueError("FASCG_INTERVENTION_MUST_BE_REVERSIBLE_SIMULATION")
        return self


@dataclass(frozen=True, slots=True)
class InterventionPlan:
    ranked_ids: tuple[str, ...]
    selected_id: str | None
    external_effect_authorized: bool
    plan_sha256: str


class CausalInterventionCourt:
    """Ranks counterfactual interventions but never authorizes provider mutation."""

    def plan(self, candidates: Sequence[InterventionCandidate]) -> InterventionPlan:
        rows = [c.validate() for c in candidates]
        def utility(c: InterventionCandidate) -> float:
            return 1.8*c.predicted_risk_reduction + 0.8*c.predicted_quality_delta - 0.35*max(0.0, c.predicted_cost_delta) - 1.2*c.blast_radius
        rows.sort(key=lambda c: (-utility(c), c.intervention_id))
        selected = rows[0].intervention_id if rows and utility(rows[0]) > 0 else None
        body = {"ranked": [c.intervention_id for c in rows], "selected": selected, "external_effect_authorized": False}
        return InterventionPlan(tuple(body["ranked"]), selected, False, _hash(body))


class AutonomyLevel(StrEnum):
    OBSERVE_ONLY = "OBSERVE_ONLY"
    BOUNDED_INTERNAL = "BOUNDED_INTERNAL"
    UNATTENDED_REVERSIBLE = "UNATTENDED_REVERSIBLE"
    HOLD_EXTERNAL_GATE = "HOLD_EXTERNAL_GATE"
    HOLD_OWNER = "HOLD_OWNER"


@dataclass(frozen=True, slots=True)
class AutonomyContext:
    effect_class: str
    reversible: bool
    exact_authority: bool
    evidence_coverage: float
    uncertainty: float
    blast_radius_risk: float
    adversarial_risk: float
    provider_runtime_available: bool
    owner_approval_required: bool = False

    def validate(self) -> "AutonomyContext":
        for label in ("evidence_coverage", "uncertainty", "blast_radius_risk", "adversarial_risk"):
            _unit(getattr(self, label), label.upper())
        if not self.effect_class.strip():
            raise ValueError("FASCG_EFFECT_CLASS_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class AutonomyReceipt:
    level: AutonomyLevel
    reasons: tuple[str, ...]
    external_effect_authorized: bool = False


class RiskAdaptiveAutonomyGate:
    def decide(self, context: AutonomyContext) -> AutonomyReceipt:
        context.validate()
        effect = context.effect_class.strip().upper()
        if context.owner_approval_required:
            return AutonomyReceipt(AutonomyLevel.HOLD_OWNER, ("OWNER_APPROVAL_REQUIRED",))
        if context.adversarial_risk >= 0.75 or context.blast_radius_risk >= 0.80:
            return AutonomyReceipt(AutonomyLevel.OBSERVE_ONLY, ("RISK_TOO_HIGH_FOR_AUTONOMY",))
        if context.evidence_coverage < 0.60 or context.uncertainty > 0.55:
            return AutonomyReceipt(AutonomyLevel.OBSERVE_ONLY, ("INSUFFICIENT_EVIDENCE_OR_HIGH_UNCERTAINTY",))
        if effect in {"NO_EFFECT", "A0", "READ"}:
            return AutonomyReceipt(AutonomyLevel.BOUNDED_INTERNAL, ("NO_EXTERNAL_EFFECT",))
        if effect in {"A1", "INTERNAL"} and context.reversible and context.exact_authority:
            return AutonomyReceipt(AutonomyLevel.BOUNDED_INTERNAL, ("INTERNAL_REVERSIBLE_AUTHORIZED",))
        if effect in {"A2", "REVERSIBLE_PROVIDER"}:
            if not context.provider_runtime_available:
                return AutonomyReceipt(AutonomyLevel.HOLD_EXTERNAL_GATE, ("PROVIDER_RUNTIME_UNAVAILABLE",))
            return AutonomyReceipt(AutonomyLevel.HOLD_EXTERNAL_GATE, ("PROVIDER_EFFECT_REQUIRES_SEPARATE_EFFECT_GATE",))
        return AutonomyReceipt(AutonomyLevel.HOLD_EXTERNAL_GATE, ("EFFECT_CLASS_NOT_AUTONOMOUSLY_AUTHORIZED",))


@dataclass(frozen=True, slots=True)
class ColdSlateMissionSpec:
    mission_id: str
    objective: str
    required_domains: tuple[GeneDomain, ...]
    authority_ceiling: str
    data_boundary: str
    maximum_genes: int = GENOME_SIZE

    def validate(self) -> "ColdSlateMissionSpec":
        if not self.mission_id.strip() or not self.objective.strip() or not self.required_domains:
            raise ValueError("FASCG_COLD_SLATE_SPEC_REQUIRED")
        if not 1 <= self.maximum_genes <= GENOME_SIZE:
            raise ValueError("FASCG_COLD_SLATE_MAX_GENES_INVALID")
        if not self.authority_ceiling.strip() or not self.data_boundary.strip():
            raise ValueError("FASCG_COLD_SLATE_ENVELOPE_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class CompiledCognitiveProfile:
    profile_id: str
    gene_ids: tuple[str, ...]
    domains: tuple[str, ...]
    source_genome_sha256: str
    profile_sha256: str
    external_effect_authorized: bool = False


class ColdSlateAutopilotSentinelCompiler:
    """Compiles mission-specific profiles from the 144-gene genome."""

    def compile(self, spec: ColdSlateMissionSpec) -> CompiledCognitiveProfile:
        spec.validate()
        genes = load_genome()
        selected = [g for g in genes if g.domain in set(spec.required_domains)]
        selected = selected[:spec.maximum_genes]
        if not selected:
            raise ValueError("FASCG_COLD_SLATE_EMPTY_PROFILE")
        genome = genome_receipt()
        body = {
            "schema": "FASCG-COLD-SLATE-PROFILE-V1",
            "mission_id": spec.mission_id,
            "objective": spec.objective,
            "authority_ceiling": spec.authority_ceiling,
            "data_boundary": spec.data_boundary,
            "gene_ids": [g.gene_id for g in selected],
            "domains": sorted({g.domain.value for g in selected}),
            "source_genome_sha256": genome["sha256"],
            "external_effect_authorized": False,
        }
        digest = _hash(body)
        return CompiledCognitiveProfile(
            profile_id=f"FASCG-PROFILE-{digest[:18].upper()}",
            gene_ids=tuple(body["gene_ids"]),
            domains=tuple(body["domains"]),
            source_genome_sha256=genome["sha256"],
            profile_sha256=digest,
        )


__all__ = [
    "SCHEMA", "GENOME_SIZE", "TEN_X_VERIFIED", "GeneDisposition", "PlasticityClock", "GeneDomain",
    "CognitiveGene", "load_genome", "validate_genome", "genome_receipt", "HomeostasisAction",
    "MissionHomeostasisState", "HomeostasisDecision", "MissionHomeostasisController", "SentinelDomain",
    "SentinelCell", "SentinelFormationPlan", "SentinelCellEcology", "SensingCandidate", "ActiveSensingPlanner",
    "InterventionCandidate", "InterventionPlan", "CausalInterventionCourt", "AutonomyLevel", "AutonomyContext",
    "AutonomyReceipt", "RiskAdaptiveAutonomyGate", "ColdSlateMissionSpec", "CompiledCognitiveProfile",
    "ColdSlateAutopilotSentinelCompiler",
]
