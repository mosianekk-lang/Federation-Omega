from __future__ import annotations

"""CFBE Hyperleverage Wave 2 scientific capability compiler.

This module is deliberately a bounded CFBE composition layer, not a new sovereign
scheduler, memory root, provider executor, or authority plane.

It turns frontier-harvest candidates into source-bound capability genes, applies
reuse-first admission, and provides deep executable controls for the highest-value
Wave 2 tranche. Provider effects remain disabled. External market claims, owner
value, provider runtime, and stable promotion require independent evidence.

The deep controls independently implement patterns inspired by public standards
and documented architecture ideas; they do not copy proprietary implementations.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
import math
import re
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "CFBE_HYPERLEVERAGE_WAVE2_SCIENTIFIC_COMPILER_V1"
REGISTRY_SCHEMA = "CFBE_HYPERLEVERAGE_WAVE2_100_V1"
MIN_OWNER_VALUE_PAIRS = 10

DEEP_GENE_IDS = frozenset({
    "CF2-001","CF2-002","CF2-003","CF2-008","CF2-013","CF2-016",
    "CF2-020","CF2-021","CF2-023","CF2-031","CF2-032","CF2-041",
    "CF2-047","CF2-050","CF2-061","CF2-064","CF2-072","CF2-076",
    "CF2-080","CF2-091","CF2-095","CF2-100",
})

GENE_NAMES = (
    "Capability DNA Compiler","Primitive-Decomposition Engine","Semantic Novelty Detector","Capability Equivalence Court","Capability Superset Detector","Frontier Half-Life Estimator","Standardization Momentum Radar","Incident-to-Capability Harvester","Negative-Design Harvester","Competitive Architecture Diff Engine","Hidden Cost-Surface Extractor","License/IP Admissibility Analyzer","Clean-Room Reimplementation Compiler","Multi-Source Truth Triangulator","Market-Motion Predictor",
    "Capability Hypothesis Generator","Experiment Preregistration Compiler","Sequential Evidence Court","Bayesian Capability Belief Engine","Evidence Information-Gain Scheduler","Causal Attribution Graph","Counterfactual Challenger Simulator","Conformal Uncertainty Gate","Confidence Calibration Court","Adaptive Multi-Armed Challenger Allocation","Pareto Frontier Optimizer","Dominance Stability Test","Benchmark Contamination Detector","Distribution-Shift Sentinel","Evaluation-Version Pinning",
    "Portable Sandbox Manifest","Cross-Provider Workspace Snapshot Format","Ephemeral Specialist Enclaves","Dynamic Skill Paging","Skill Dependency Solver","Agent Contract Negotiation Protocol","Typed Tool Semantic Layer","Pre/Postcondition Tool Firewall","Saga Compensation Compiler","Read-Only Speculative Execution","Durable Fiber Primitive","Long-Horizon Wake/Sleep Scheduler","Execution-Granularity Optimizer","Autonomy Envelope Compiler","Context Sharding Mesh",
    "Memory Class Taxonomy","Remember/Forget Reconciler","Conflict-Aware Memory CRDT","Memory Provenance Chain","Memory Influence Attribution","Memory Poisoning Quarantine","Counterfactual Memory Court","Semantic Aging Engine","Memory Consolidation Optimizer","Knowledge Loss Detector","Evidence-to-Concept Graph","Retrieval-Intent Router","Retrieval Value Predictor","Cross-Modal Evidence Binder","Privacy Boundary Compiler",
    "Capability-Based Authority Lattice","Intent-Bound Credential Token","Pre-Effect Policy Simulator","Prompt-Injection Taint Tracking","Information-Flow Labels","Structured Tool-Output Decoder","Untrusted Artifact Detonation Sandbox","Agent Egress Firewall","Permission Drift Detector","Authority Utilization Heatmap","Approval Token Proof Objects","Cryptographic Execution Transcript","Agent Bill of Materials","Reproducible Agent Build","Confidential-Compute Route Classifier",
    "Agent Flight Recorder","Trace-to-Replay Debugger","Semantic Span Classification","Causal Incident Clustering","Cognitive Load Index","Intervention Entropy","Unnecessary-Work Meter","Value-Weighted Error Budget","Semantic SLOs","Cost-to-Proof Ratio","Marginal Capability Curve","Rework Leakage Detector","Toil Discovery Engine","Dead Capability Detector","Complexity Tax Ledger",
    "Universal Agent Protocol Gateway","Protocol Conformance Fuzzer","Model Hardware Standard Adapter Court","Multimodal Actuator Digital Twin","API-to-Capability Compiler","Capability Upgrade Transformer","Synthetic Failure-Case Generator","Online-to-Golden Dataset Promotion","Privacy-Preserving Benchmark Federation","Capability Ecology Governor",
)

DOMAIN_RANGES = (
    (1, 15, "HARVEST_INTELLIGENCE"),
    (16, 30, "SCIENTIFIC_CORE"),
    (31, 45, "RUNTIME_HARVEST"),
    (46, 60, "MEMORY_INTELLIGENCE"),
    (61, 75, "SECURITY_AUTHORITY"),
    (76, 79, "OBSERVABILITY"),
    (80, 90, "OWNER_VALUE"),
    (91, 92, "PROTOCOL_FRONTIER"),
    (93, 94, "PHYSICAL_FRONTIER"),
    (95, 96, "DEVELOPER_FRONTIER"),
    (97, 98, "EVALUATION_FRONTIER"),
    (99, 100, "STRATEGIC_FRONTIER"),
)

PROVIDER_GATED = frozenset({"CF2-067","CF2-075","CF2-093","CF2-094","CF2-098","CF2-099"})
RESEARCH_GATED = frozenset({"CF2-015","CF2-023","CF2-024","CF2-025","CF2-029","CF2-093","CF2-094","CF2-099"})


class RouteMode(str, Enum):
    REUSE = "REUSE"
    EXTEND = "EXTEND"
    SPECIALISE = "SPECIALISE"
    COMPOSE = "COMPOSE"
    PROVIDER_GATED = "PROVIDER_GATED"
    RESEARCH_GATED = "RESEARCH_GATED"


class AdmissionDecision(str, Enum):
    REUSE = "REUSE"
    EXTEND = "EXTEND"
    SPECIALISE = "SPECIALISE"
    COMPOSE = "COMPOSE"
    HOLD = "HOLD"
    ADMIT = "ADMIT"


class Taint(str, Enum):
    TRUSTED = "TRUSTED"
    UNTRUSTED = "UNTRUSTED"
    PRIVATE = "PRIVATE"
    SECRET = "SECRET"
    DERIVED = "DERIVED"


class TraceKind(str, Enum):
    PLAN = "PLAN"
    RETRIEVE = "RETRIEVE"
    DELEGATE = "DELEGATE"
    TOOL = "TOOL"
    EFFECT = "EFFECT"
    VERIFY = "VERIFY"
    RECOVER = "RECOVER"
    WAIT = "WAIT"
    OWNER_INTERVENTION = "OWNER_INTERVENTION"


def canonical_hash(value: Any) -> str:
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str
        ).encode("utf-8")
    ).hexdigest()


def _is_sha(value: str) -> bool:
    value = str(value).lower().strip()
    return len(value) == 40 and all(ch in "0123456789abcdef" for ch in value)


def _items(value: Iterable[Any] | None) -> tuple[str, ...]:
    return tuple(str(item).strip() for item in (value or ()) if str(item).strip())


def _tokenize(value: str) -> frozenset[str]:
    return frozenset(
        token for token in re.findall(r"[a-z0-9]+", str(value).lower()) if len(token) > 1
    )


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a, b = set(left), set(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _domain_for(index: int) -> str:
    for start, end, domain in DOMAIN_RANGES:
        if start <= index <= end:
            return domain
    raise ValueError("WAVE2_DOMAIN_NOT_FOUND")


@dataclass(frozen=True, slots=True)
class CapabilityGene:
    gene_id: str
    index: int
    name: str
    domain: str
    route_mode: RouteMode
    deep_control_implemented: bool
    source_contract_implemented: bool
    acceptance_gate: str
    provider_effect_authorized: bool = False

    def validate(self) -> "CapabilityGene":
        if self.gene_id != f"CF2-{self.index:03d}" or not self.name or not self.domain:
            raise ValueError("WAVE2_GENE_IDENTITY_INVALID")
        if self.provider_effect_authorized:
            raise ValueError("WAVE2_SOURCE_REGISTRY_MUST_NOT_AUTHORIZE_PROVIDER_EFFECT")
        return self


def load_wave2_genome() -> tuple[CapabilityGene, ...]:
    if len(GENE_NAMES) != 100:
        raise ValueError("WAVE2_GENOME_EXPECTED_100")
    genes: list[CapabilityGene] = []
    for index, name in enumerate(GENE_NAMES, start=1):
        gene_id = f"CF2-{index:03d}"
        if gene_id in PROVIDER_GATED:
            route = RouteMode.PROVIDER_GATED
        elif gene_id in RESEARCH_GATED:
            route = RouteMode.RESEARCH_GATED
        elif gene_id in DEEP_GENE_IDS:
            route = RouteMode.SPECIALISE
        elif index % 5 == 0:
            route = RouteMode.EXTEND
        elif index % 3 == 0:
            route = RouteMode.COMPOSE
        else:
            route = RouteMode.REUSE
        genes.append(
            CapabilityGene(
                gene_id=gene_id,
                index=index,
                name=name,
                domain=_domain_for(index),
                route_mode=route,
                deep_control_implemented=gene_id in DEEP_GENE_IDS,
                source_contract_implemented=True,
                acceptance_gate=(
                    "provider-native proof + rollback + exact authority"
                    if route is RouteMode.PROVIDER_GATED
                    else "prospective empirical falsification"
                    if route is RouteMode.RESEARCH_GATED
                    else "source tests + independent proof + measured value"
                ),
            ).validate()
        )
    ids = [g.gene_id for g in genes]
    if ids != [f"CF2-{i:03d}" for i in range(1, 101)] or len(set(ids)) != 100:
        raise ValueError("WAVE2_GENE_SEQUENCE_INVALID")
    return tuple(genes)


@dataclass(frozen=True, slots=True)
class Wave2ImplementationReceipt:
    schema: str
    gene_count: int
    routed_count: int
    source_contract_count: int
    deep_control_count: int
    provider_gated_count: int
    research_gated_count: int
    unrouted_gene_ids: tuple[str, ...]
    provider_effect_authorized: bool = False
    stable_promotion_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compile_wave2_receipt() -> Wave2ImplementationReceipt:
    genes = load_wave2_genome()
    return Wave2ImplementationReceipt(
        schema=REGISTRY_SCHEMA,
        gene_count=len(genes),
        routed_count=len(genes),
        source_contract_count=sum(g.source_contract_implemented for g in genes),
        deep_control_count=sum(g.deep_control_implemented for g in genes),
        provider_gated_count=sum(g.route_mode is RouteMode.PROVIDER_GATED for g in genes),
        research_gated_count=sum(g.route_mode is RouteMode.RESEARCH_GATED for g in genes),
        unrouted_gene_ids=(),
    )


@dataclass(frozen=True, slots=True)
class GeneAdmissionInput:
    gene_id: str
    measured_gap: bool
    existing_coverage: float
    composable_capability_count: int
    measurable_owner_value_hypothesis: bool
    public_provenance_verified: bool
    license_or_standard_admissible: bool
    exact_authority_available: bool = False
    provider_effect_required: bool = False
    proof_refs: tuple[str, ...] = ()

    def validate(self) -> "GeneAdmissionInput":
        if self.gene_id not in {g.gene_id for g in load_wave2_genome()}:
            raise ValueError("WAVE2_UNKNOWN_GENE")
        if not 0 <= self.existing_coverage <= 1:
            raise ValueError("WAVE2_EXISTING_COVERAGE_INVALID")
        if self.composable_capability_count < 0:
            raise ValueError("WAVE2_COMPOSABLE_COUNT_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class GeneAdmissionReceipt:
    gene_id: str
    decision: AdmissionDecision
    blockers: tuple[str, ...]
    provider_effect_authorized: bool
    stable_promotion_authorized: bool
    receipt_sha256: str


def evaluate_gene_admission(value: GeneAdmissionInput) -> GeneAdmissionReceipt:
    value.validate()
    blockers: list[str] = []
    if not value.measured_gap:
        blockers.append("MEASURED_GAP_REQUIRED")
    if not value.measurable_owner_value_hypothesis:
        blockers.append("OWNER_VALUE_HYPOTHESIS_REQUIRED")
    if not value.public_provenance_verified:
        blockers.append("PUBLIC_PROVENANCE_REQUIRED")
    if not value.license_or_standard_admissible:
        blockers.append("LICENSE_OR_STANDARD_ADMISSIBILITY_REQUIRED")
    if value.provider_effect_required and not value.exact_authority_available:
        blockers.append("EXACT_PROVIDER_AUTHORITY_REQUIRED")

    if blockers:
        decision = AdmissionDecision.HOLD
    elif value.existing_coverage >= 0.85:
        decision = AdmissionDecision.REUSE
    elif value.existing_coverage >= 0.55:
        decision = AdmissionDecision.EXTEND
    elif value.composable_capability_count >= 2:
        decision = AdmissionDecision.COMPOSE
    elif value.existing_coverage > 0:
        decision = AdmissionDecision.SPECIALISE
    else:
        decision = AdmissionDecision.ADMIT

    payload = {
        "gene_id": value.gene_id,
        "decision": decision.value,
        "blockers": sorted(blockers),
        "provider_effect_authorized": False,
        "stable_promotion_authorized": False,
    }
    return GeneAdmissionReceipt(
        gene_id=value.gene_id,
        decision=decision,
        blockers=tuple(sorted(blockers)),
        provider_effect_authorized=False,
        stable_promotion_authorized=False,
        receipt_sha256=canonical_hash(payload),
    )


@dataclass(frozen=True, slots=True)
class CapabilityDNA:
    capability_id: str
    objective: str
    triggers: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    primitives: tuple[str, ...]
    invariants: tuple[str, ...]
    failure_modes: tuple[str, ...]
    recovery_controls: tuple[str, ...]
    authority_requirements: tuple[str, ...]
    proof_requirements: tuple[str, ...]
    value_hypothesis: str
    provenance_refs: tuple[str, ...]
    license_class: str
    dna_sha256: str = ""

    def validate(self) -> "CapabilityDNA":
        if not self.capability_id or not self.objective or not self.value_hypothesis:
            raise ValueError("CAPABILITY_DNA_IDENTITY_OBJECTIVE_VALUE_REQUIRED")
        if not self.primitives or not self.invariants or not self.proof_requirements:
            raise ValueError("CAPABILITY_DNA_PRIMITIVES_INVARIANTS_PROOF_REQUIRED")
        if not self.provenance_refs or not self.license_class:
            raise ValueError("CAPABILITY_DNA_PROVENANCE_LICENSE_REQUIRED")
        return self

    def to_dict(self, include_hash: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        if not include_hash:
            payload.pop("dna_sha256", None)
        return payload


def compile_capability_dna(value: Mapping[str, Any]) -> CapabilityDNA:
    dna = CapabilityDNA(
        capability_id=str(value.get("capability_id") or "").strip(),
        objective=str(value.get("objective") or "").strip(),
        triggers=_items(value.get("triggers")),
        inputs=_items(value.get("inputs")),
        outputs=_items(value.get("outputs")),
        primitives=tuple(sorted(set(_items(value.get("primitives"))))),
        invariants=tuple(sorted(set(_items(value.get("invariants"))))),
        failure_modes=tuple(sorted(set(_items(value.get("failure_modes"))))),
        recovery_controls=tuple(sorted(set(_items(value.get("recovery_controls"))))),
        authority_requirements=tuple(sorted(set(_items(value.get("authority_requirements"))))),
        proof_requirements=tuple(sorted(set(_items(value.get("proof_requirements"))))),
        value_hypothesis=str(value.get("value_hypothesis") or "").strip(),
        provenance_refs=tuple(sorted(set(_items(value.get("provenance_refs"))))),
        license_class=str(value.get("license_class") or "").strip().upper(),
    ).validate()
    payload = dna.to_dict(include_hash=False)
    return CapabilityDNA(**payload, dna_sha256=canonical_hash(payload)).validate()


@dataclass(frozen=True, slots=True)
class PrimitiveDecomposition:
    capability_id: str
    required: tuple[str, ...]
    reusable: tuple[str, ...]
    missing: tuple[str, ...]
    overlap_ratio: float
    recommended_route: AdmissionDecision
    decomposition_sha256: str


def decompose_primitives(
    *, capability_id: str, required_primitives: Iterable[str], estate_primitives: Iterable[str]
) -> PrimitiveDecomposition:
    required = tuple(sorted(set(_items(required_primitives))))
    estate = set(_items(estate_primitives))
    if not capability_id or not required:
        raise ValueError("PRIMITIVE_DECOMPOSITION_INPUT_REQUIRED")
    reusable = tuple(item for item in required if item in estate)
    missing = tuple(item for item in required if item not in estate)
    overlap = len(reusable) / len(required)
    route = (
        AdmissionDecision.REUSE if not missing
        else AdmissionDecision.EXTEND if overlap >= 0.5
        else AdmissionDecision.COMPOSE if reusable
        else AdmissionDecision.ADMIT
    )
    payload = {
        "capability_id": capability_id,
        "required": required,
        "reusable": reusable,
        "missing": missing,
        "overlap_ratio": round(overlap, 6),
        "recommended_route": route.value,
    }
    return PrimitiveDecomposition(
        capability_id=capability_id,
        required=required,
        reusable=reusable,
        missing=missing,
        overlap_ratio=round(overlap, 6),
        recommended_route=route,
        decomposition_sha256=canonical_hash(payload),
    )


@dataclass(frozen=True, slots=True)
class SemanticFingerprint:
    capability_id: str
    objective_tokens: frozenset[str]
    primitive_tokens: frozenset[str]
    invariant_tokens: frozenset[str]
    output_tokens: frozenset[str]


@dataclass(frozen=True, slots=True)
class NoveltyReceipt:
    candidate_id: str
    closest_capability_id: str | None
    maximum_similarity: float
    novelty_score: float
    decision: AdmissionDecision
    receipt_sha256: str


def fingerprint(dna: CapabilityDNA) -> SemanticFingerprint:
    dna.validate()
    return SemanticFingerprint(
        capability_id=dna.capability_id,
        objective_tokens=_tokenize(dna.objective),
        primitive_tokens=frozenset(item.lower() for item in dna.primitives),
        invariant_tokens=frozenset(item.lower() for item in dna.invariants),
        output_tokens=frozenset(item.lower() for item in dna.outputs),
    )


def semantic_similarity(left: SemanticFingerprint, right: SemanticFingerprint) -> float:
    return (
        0.35 * _jaccard(left.objective_tokens, right.objective_tokens)
        + 0.35 * _jaccard(left.primitive_tokens, right.primitive_tokens)
        + 0.20 * _jaccard(left.invariant_tokens, right.invariant_tokens)
        + 0.10 * _jaccard(left.output_tokens, right.output_tokens)
    )


def detect_semantic_novelty(candidate: CapabilityDNA, incumbents: Sequence[CapabilityDNA]) -> NoveltyReceipt:
    c = fingerprint(candidate)
    best_id: str | None = None
    best = 0.0
    for incumbent in incumbents:
        score = semantic_similarity(c, fingerprint(incumbent))
        if score > best:
            best, best_id = score, incumbent.capability_id
    novelty = max(0.0, 1.0 - best)
    if best >= 0.88:
        decision = AdmissionDecision.REUSE
    elif best >= 0.68:
        decision = AdmissionDecision.EXTEND
    elif best >= 0.45:
        decision = AdmissionDecision.SPECIALISE
    else:
        decision = AdmissionDecision.ADMIT
    payload = {
        "candidate_id": candidate.capability_id,
        "closest_capability_id": best_id,
        "maximum_similarity": round(best, 6),
        "novelty_score": round(novelty, 6),
        "decision": decision.value,
    }
    return NoveltyReceipt(
        candidate_id=candidate.capability_id,
        closest_capability_id=best_id,
        maximum_similarity=round(best, 6),
        novelty_score=round(novelty, 6),
        decision=decision,
        receipt_sha256=canonical_hash(payload),
    )


@dataclass(frozen=True, slots=True)
class IncidentRecord:
    incident_id: str
    symptom: str
    root_cause: str
    failed_control: str
    repair_pattern: str
    proof_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IncidentHarvestProposal:
    proposal_id: str
    incident_id: str
    objective: str
    primitive_candidates: tuple[str, ...]
    negative_design_rule: str
    evidence_refs: tuple[str, ...]
    proposal_sha256: str


def harvest_incident(record: IncidentRecord) -> IncidentHarvestProposal:
    if not all((record.incident_id, record.symptom, record.root_cause, record.repair_pattern)):
        raise ValueError("INCIDENT_HARVEST_IDENTITY_REQUIRED")
    if len(set(record.proof_refs)) < 1:
        raise ValueError("INCIDENT_HARVEST_PROOF_REQUIRED")
    primitives = tuple(sorted(_tokenize(record.repair_pattern) | _tokenize(record.failed_control)))
    payload = {
        "proposal_id": f"INC-CAP-{record.incident_id}",
        "incident_id": record.incident_id,
        "objective": f"Prevent recurrence of: {record.root_cause}",
        "primitive_candidates": primitives,
        "negative_design_rule": f"DO_NOT_REPEAT::{record.failed_control or record.root_cause}",
        "evidence_refs": sorted(set(record.proof_refs)),
    }
    return IncidentHarvestProposal(
        proposal_id=payload["proposal_id"],
        incident_id=record.incident_id,
        objective=payload["objective"],
        primitive_candidates=primitives,
        negative_design_rule=payload["negative_design_rule"],
        evidence_refs=tuple(payload["evidence_refs"]),
        proposal_sha256=canonical_hash(payload),
    )


@dataclass(frozen=True, slots=True)
class CleanRoomPlan:
    capability_id: str
    public_spec_refs: tuple[str, ...]
    allowed_inputs: tuple[str, ...]
    prohibited_inputs: tuple[str, ...]
    independent_primitives: tuple[str, ...]
    acceptance_tests: tuple[str, ...]
    license_class: str
    clean_room_admissible: bool
    blockers: tuple[str, ...]
    plan_sha256: str


def compile_clean_room_plan(
    *,
    capability_id: str,
    public_spec_refs: Iterable[str],
    behavioral_requirements: Iterable[str],
    independent_primitives: Iterable[str],
    license_class: str,
    proprietary_source_used: bool = False,
    acceptance_tests: Iterable[str] = (),
) -> CleanRoomPlan:
    refs = tuple(sorted(set(_items(public_spec_refs))))
    requirements = tuple(sorted(set(_items(behavioral_requirements))))
    primitives = tuple(sorted(set(_items(independent_primitives))))
    tests = tuple(sorted(set(_items(acceptance_tests))))
    blockers: list[str] = []
    if not capability_id or not refs or not requirements or not primitives:
        blockers.append("PUBLIC_SPEC_REQUIREMENTS_PRIMITIVES_REQUIRED")
    if proprietary_source_used:
        blockers.append("PROPRIETARY_SOURCE_INPUT_PROHIBITED")
    if not str(license_class).strip():
        blockers.append("LICENSE_CLASS_REQUIRED")
    payload = {
        "capability_id": capability_id,
        "public_spec_refs": refs,
        "allowed_inputs": requirements,
        "prohibited_inputs": ("proprietary source code", "non-public implementation details", "secret credentials"),
        "independent_primitives": primitives,
        "acceptance_tests": tests,
        "license_class": str(license_class).strip().upper(),
        "clean_room_admissible": not blockers,
        "blockers": sorted(blockers),
    }
    return CleanRoomPlan(
        capability_id=capability_id,
        public_spec_refs=refs,
        allowed_inputs=requirements,
        prohibited_inputs=payload["prohibited_inputs"],
        independent_primitives=primitives,
        acceptance_tests=tests,
        license_class=payload["license_class"],
        clean_room_admissible=not blockers,
        blockers=tuple(sorted(blockers)),
        plan_sha256=canonical_hash(payload),
    )


@dataclass(frozen=True, slots=True)
class CapabilityHypothesis:
    hypothesis_id: str
    capability_id: str
    outcome_metric: str
    expected_direction: str
    minimum_effect: float
    guardrail_metrics: tuple[str, ...]
    disqualifiers: tuple[str, ...]
    preregistered: bool
    hypothesis_sha256: str


def generate_hypothesis(
    *,
    capability_id: str,
    outcome_metric: str,
    expected_direction: str,
    minimum_effect: float,
    guardrail_metrics: Iterable[str],
    disqualifiers: Iterable[str],
) -> CapabilityHypothesis:
    direction = expected_direction.strip().upper()
    if direction not in {"INCREASE", "DECREASE"}:
        raise ValueError("HYPOTHESIS_DIRECTION_INVALID")
    if not capability_id or not outcome_metric or minimum_effect <= 0:
        raise ValueError("HYPOTHESIS_IDENTITY_EFFECT_REQUIRED")
    payload = {
        "hypothesis_id": f"HYP-{canonical_hash([capability_id,outcome_metric,direction,minimum_effect])[:16]}",
        "capability_id": capability_id,
        "outcome_metric": outcome_metric,
        "expected_direction": direction,
        "minimum_effect": float(minimum_effect),
        "guardrail_metrics": tuple(sorted(set(_items(guardrail_metrics)))),
        "disqualifiers": tuple(sorted(set(_items(disqualifiers)))),
        "preregistered": True,
    }
    return CapabilityHypothesis(**payload, hypothesis_sha256=canonical_hash(payload))


@dataclass(frozen=True, slots=True)
class ExperimentCandidate:
    experiment_id: str
    prior_uncertainty: float
    expected_posterior_uncertainty: float
    cost: float
    risk: float
    decision_relevance: float

    @property
    def information_gain(self) -> float:
        return max(0.0, self.prior_uncertainty - self.expected_posterior_uncertainty)

    @property
    def utility(self) -> float:
        denominator = max(self.cost * (1.0 + self.risk), 1e-9)
        return self.information_gain * self.decision_relevance / denominator


def select_information_gain_experiment(candidates: Sequence[ExperimentCandidate]) -> ExperimentCandidate:
    if not candidates:
        raise ValueError("INFO_GAIN_CANDIDATES_REQUIRED")
    for item in candidates:
        values = (
            item.prior_uncertainty, item.expected_posterior_uncertainty,
            item.cost, item.risk, item.decision_relevance,
        )
        if item.cost <= 0 or any(v < 0 for v in values):
            raise ValueError("INFO_GAIN_CANDIDATE_INVALID")
        if item.expected_posterior_uncertainty > item.prior_uncertainty:
            raise ValueError("INFO_GAIN_POSTERIOR_CANNOT_EXCEED_PRIOR")
    return max(candidates, key=lambda item: (item.utility, item.information_gain, item.experiment_id))


@dataclass(frozen=True, slots=True)
class CausalEdge:
    cause: str
    effect: str
    confidence: float
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CausalGraphReceipt:
    nodes: tuple[str, ...]
    edges: tuple[CausalEdge, ...]
    acyclic: bool
    weak_edges: tuple[tuple[str, str], ...]
    graph_sha256: str


def compile_causal_graph(edges: Sequence[CausalEdge], *, min_confidence: float = 0.6) -> CausalGraphReceipt:
    if not 0 <= min_confidence <= 1:
        raise ValueError("CAUSAL_MIN_CONFIDENCE_INVALID")
    nodes = sorted({x for edge in edges for x in (edge.cause, edge.effect)})
    adjacency: dict[str, list[str]] = {node: [] for node in nodes}
    weak: list[tuple[str, str]] = []
    for edge in edges:
        if not edge.cause or not edge.effect or edge.cause == edge.effect:
            raise ValueError("CAUSAL_EDGE_INVALID")
        if not 0 <= edge.confidence <= 1 or not edge.evidence_refs:
            raise ValueError("CAUSAL_EDGE_CONFIDENCE_EVIDENCE_REQUIRED")
        adjacency[edge.cause].append(edge.effect)
        if edge.confidence < min_confidence:
            weak.append((edge.cause, edge.effect))
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return False
        if node in visited:
            return True
        visiting.add(node)
        for child in adjacency[node]:
            if not visit(child):
                return False
        visiting.remove(node)
        visited.add(node)
        return True

    acyclic = all(visit(node) for node in nodes)
    payload = {
        "nodes": nodes,
        "edges": [asdict(edge) for edge in edges],
        "acyclic": acyclic,
        "weak_edges": sorted(weak),
    }
    return CausalGraphReceipt(
        nodes=tuple(nodes), edges=tuple(edges), acyclic=acyclic,
        weak_edges=tuple(sorted(weak)), graph_sha256=canonical_hash(payload)
    )


def matched_counterfactual_effect(treated: Sequence[float], control: Sequence[float]) -> float:
    if not treated or len(treated) != len(control):
        raise ValueError("COUNTERFACTUAL_MATCHED_PAIRS_REQUIRED")
    return mean(float(t) - float(c) for t, c in zip(treated, control))


@dataclass(frozen=True, slots=True)
class ConformalInterval:
    prediction: float
    lower: float
    upper: float
    alpha: float
    residual_quantile: float
    sufficiently_bounded: bool


def conformal_interval(
    *, prediction: float, calibration_residuals: Sequence[float], alpha: float,
    maximum_width: float | None = None
) -> ConformalInterval:
    if not calibration_residuals or not 0 < alpha < 1:
        raise ValueError("CONFORMAL_CALIBRATION_ALPHA_REQUIRED")
    residuals = sorted(abs(float(x)) for x in calibration_residuals)
    n = len(residuals)
    rank = min(n - 1, max(0, math.ceil((n + 1) * (1 - alpha)) - 1))
    q = residuals[rank]
    width = 2 * q
    bounded = maximum_width is None or width <= maximum_width
    return ConformalInterval(
        prediction=float(prediction),
        lower=float(prediction) - q,
        upper=float(prediction) + q,
        alpha=float(alpha),
        residual_quantile=q,
        sufficiently_bounded=bounded,
    )


@dataclass(frozen=True, slots=True)
class PortableSandboxManifest:
    manifest_id: str
    source_head_sha: str
    filesystem_mounts: tuple[str, ...]
    tools: tuple[str, ...]
    dependencies: tuple[str, ...]
    network_allowlist: tuple[str, ...]
    secret_handles: tuple[str, ...]
    resource_limits: tuple[tuple[str, float], ...]
    provider_neutral: bool
    manifest_sha256: str

    def validate(self) -> "PortableSandboxManifest":
        if not self.manifest_id or not _is_sha(self.source_head_sha):
            raise ValueError("SANDBOX_MANIFEST_ID_SOURCE_REQUIRED")
        if any("://" in item and item.startswith(("http://","https://")) for item in self.secret_handles):
            raise ValueError("SANDBOX_SECRET_HANDLE_MUST_NOT_BE_URL_VALUE")
        if any(value <= 0 for _, value in self.resource_limits):
            raise ValueError("SANDBOX_RESOURCE_LIMIT_POSITIVE_REQUIRED")
        if not self.provider_neutral:
            raise ValueError("SANDBOX_MANIFEST_MUST_BE_PROVIDER_NEUTRAL")
        return self


def compile_sandbox_manifest(
    *, manifest_id: str, source_head_sha: str, filesystem_mounts: Iterable[str],
    tools: Iterable[str], dependencies: Iterable[str], network_allowlist: Iterable[str] = (),
    secret_handles: Iterable[str] = (), resource_limits: Mapping[str, float] | None = None
) -> PortableSandboxManifest:
    payload = {
        "manifest_id": manifest_id,
        "source_head_sha": source_head_sha,
        "filesystem_mounts": tuple(sorted(set(_items(filesystem_mounts)))),
        "tools": tuple(sorted(set(_items(tools)))),
        "dependencies": tuple(sorted(set(_items(dependencies)))),
        "network_allowlist": tuple(sorted(set(_items(network_allowlist)))),
        "secret_handles": tuple(sorted(set(_items(secret_handles)))),
        "resource_limits": tuple(sorted((str(k), float(v)) for k, v in (resource_limits or {}).items())),
        "provider_neutral": True,
    }
    return PortableSandboxManifest(**payload, manifest_sha256=canonical_hash(payload)).validate()


@dataclass(frozen=True, slots=True)
class WorkspaceSnapshot:
    snapshot_id: str
    source_head_sha: str
    manifest_sha256: str
    files: tuple[tuple[str, str], ...]
    state_items: tuple[tuple[str, str], ...]
    provider_specific_state_included: bool
    portable: bool
    snapshot_sha256: str


def compile_workspace_snapshot(
    *, snapshot_id: str, source_head_sha: str, manifest_sha256: str,
    files: Mapping[str, str], state_items: Mapping[str, str] | None = None,
    provider_specific_state_included: bool = False,
) -> WorkspaceSnapshot:
    if not snapshot_id or not _is_sha(source_head_sha) or len(manifest_sha256) != 64:
        raise ValueError("WORKSPACE_SNAPSHOT_ID_SOURCE_MANIFEST_REQUIRED")
    normalized_files: list[tuple[str, str]] = []
    for path, digest in sorted(files.items()):
        digest = str(digest).lower()
        if len(digest) != 64 or not all(ch in "0123456789abcdef" for ch in digest):
            raise ValueError("WORKSPACE_FILE_DIGEST_INVALID")
        normalized_files.append((str(path), digest))
    state = tuple(sorted((str(k), str(v)) for k, v in (state_items or {}).items()))
    portable = not provider_specific_state_included
    payload = {
        "snapshot_id": snapshot_id,
        "source_head_sha": source_head_sha,
        "manifest_sha256": manifest_sha256,
        "files": normalized_files,
        "state_items": state,
        "provider_specific_state_included": provider_specific_state_included,
        "portable": portable,
    }
    return WorkspaceSnapshot(
        snapshot_id=snapshot_id, source_head_sha=source_head_sha,
        manifest_sha256=manifest_sha256, files=tuple(normalized_files),
        state_items=state, provider_specific_state_included=provider_specific_state_included,
        portable=portable, snapshot_sha256=canonical_hash(payload)
    )


@dataclass(frozen=True, slots=True)
class FiberCheckpoint:
    fiber_id: str
    generation: int
    state: str
    idempotency_key: str
    resume_after: str | None
    payload_digest: str
    checkpoint_sha256: str


def create_fiber_checkpoint(
    *, fiber_id: str, generation: int, previous_generation: int,
    state: str, idempotency_key: str, payload: Mapping[str, Any],
    resume_after: str | None = None
) -> FiberCheckpoint:
    if not fiber_id or not idempotency_key or generation <= previous_generation:
        raise ValueError("FIBER_GENERATION_FENCE_OR_IDENTITY_INVALID")
    if state not in {"RUNNABLE","WAITING","SLEEPING","COMPLETED","FAILED","COMPENSATING"}:
        raise ValueError("FIBER_STATE_INVALID")
    payload_digest = canonical_hash(payload)
    body = {
        "fiber_id": fiber_id, "generation": generation, "state": state,
        "idempotency_key": idempotency_key, "resume_after": resume_after,
        "payload_digest": payload_digest,
    }
    return FiberCheckpoint(**body, checkpoint_sha256=canonical_hash(body))


@dataclass(frozen=True, slots=True)
class MemoryItem:
    memory_id: str
    memory_class: str
    value_digest: str
    source_refs: tuple[str, ...]
    version: int
    state: str
    confidence: float


def reconcile_memory(
    current: MemoryItem | None,
    *, operation: str, memory_id: str, memory_class: str = "",
    value: str = "", source_refs: Iterable[str] = (), confidence: float = 1.0
) -> MemoryItem:
    op = operation.strip().upper()
    if op not in {"REMEMBER","UPDATE","FORGET"}:
        raise ValueError("MEMORY_OPERATION_INVALID")
    if not memory_id or not 0 <= confidence <= 1:
        raise ValueError("MEMORY_ID_CONFIDENCE_REQUIRED")
    if current and current.memory_id != memory_id:
        raise ValueError("MEMORY_ID_DRIFT")
    version = 1 if current is None else current.version + 1
    if op == "FORGET":
        if current is None:
            raise ValueError("MEMORY_FORGET_REQUIRES_EXISTING_ITEM")
        return MemoryItem(
            memory_id=memory_id, memory_class=current.memory_class,
            value_digest=current.value_digest, source_refs=current.source_refs,
            version=version, state="FORGOTTEN", confidence=current.confidence
        )
    refs = tuple(sorted(set(_items(source_refs))))
    if not memory_class or not value or not refs:
        raise ValueError("MEMORY_REMEMBER_UPDATE_VALUE_SOURCE_REQUIRED")
    return MemoryItem(
        memory_id=memory_id, memory_class=memory_class,
        value_digest=canonical_hash({"value": value}), source_refs=refs,
        version=version, state="ACTIVE", confidence=float(confidence)
    )


@dataclass(frozen=True, slots=True)
class MemoryInfluenceReceipt:
    decision_id: str
    memory_id: str
    with_memory_score: float
    without_memory_score: float
    influence_delta: float
    materially_influential: bool
    receipt_sha256: str


def attribute_memory_influence(
    *, decision_id: str, memory_id: str, with_memory_score: float,
    without_memory_score: float, materiality_threshold: float = 0.05
) -> MemoryInfluenceReceipt:
    if not decision_id or not memory_id or materiality_threshold < 0:
        raise ValueError("MEMORY_INFLUENCE_IDENTITY_THRESHOLD_REQUIRED")
    delta = float(with_memory_score) - float(without_memory_score)
    payload = {
        "decision_id": decision_id, "memory_id": memory_id,
        "with_memory_score": float(with_memory_score),
        "without_memory_score": float(without_memory_score),
        "influence_delta": delta,
        "materially_influential": abs(delta) >= materiality_threshold,
    }
    return MemoryInfluenceReceipt(**payload, receipt_sha256=canonical_hash(payload))


@dataclass(frozen=True, slots=True)
class CapabilityGrant:
    operation: str
    resource: str
    purpose: str
    constraints: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AuthorityDecision:
    allowed: bool
    exact_match: bool
    matched_grant: CapabilityGrant | None
    blockers: tuple[str, ...]


def authorize_capability(required: CapabilityGrant, grants: Sequence[CapabilityGrant]) -> AuthorityDecision:
    if not all((required.operation, required.resource, required.purpose)):
        raise ValueError("AUTHORITY_REQUIRED_CAPABILITY_INCOMPLETE")
    for grant in grants:
        if (
            grant.operation == required.operation
            and grant.resource == required.resource
            and grant.purpose == required.purpose
            and set(required.constraints).issubset(set(grant.constraints))
        ):
            return AuthorityDecision(True, True, grant, ())
    return AuthorityDecision(False, False, None, ("EXACT_CAPABILITY_GRANT_REQUIRED",))


@dataclass(frozen=True, slots=True)
class TaintedValue:
    value_digest: str
    labels: frozenset[Taint]
    source_refs: tuple[str, ...]


def taint_value(value: str, labels: Iterable[Taint], source_refs: Iterable[str]) -> TaintedValue:
    label_set = frozenset(labels)
    refs = tuple(sorted(set(_items(source_refs))))
    if not label_set or not refs:
        raise ValueError("TAINT_LABEL_SOURCE_REQUIRED")
    return TaintedValue(canonical_hash({"value": value}), label_set, refs)


def propagate_taint(values: Sequence[TaintedValue]) -> frozenset[Taint]:
    labels: set[Taint] = set()
    for value in values:
        labels.update(value.labels)
    return frozenset(labels)


def taint_flow_allowed(labels: Iterable[Taint], *, sink: str) -> bool:
    label_set = set(labels)
    sink = sink.strip().upper()
    if sink in {"EXTERNAL_EFFECT","AUTHORITY_DECISION","CANONICAL_MEMORY"} and Taint.UNTRUSTED in label_set:
        return False
    if sink == "PUBLIC_OUTPUT" and (Taint.PRIVATE in label_set or Taint.SECRET in label_set):
        return False
    if sink in {"MODEL_CONTEXT","LOG"} and Taint.SECRET in label_set:
        return False
    return True


@dataclass(frozen=True, slots=True)
class TranscriptEvent:
    sequence: int
    event_type: str
    subject: str
    payload_digest: str
    previous_hash: str
    event_hash: str


class ExecutionTranscript:
    def __init__(self) -> None:
        self._events: list[TranscriptEvent] = []

    @property
    def events(self) -> tuple[TranscriptEvent, ...]:
        return tuple(self._events)

    def append(self, *, event_type: str, subject: str, payload: Mapping[str, Any]) -> TranscriptEvent:
        if not event_type or not subject:
            raise ValueError("TRANSCRIPT_EVENT_IDENTITY_REQUIRED")
        sequence = len(self._events) + 1
        previous_hash = self._events[-1].event_hash if self._events else "GENESIS"
        payload_digest = canonical_hash(payload)
        body = {
            "sequence": sequence, "event_type": event_type, "subject": subject,
            "payload_digest": payload_digest, "previous_hash": previous_hash,
        }
        event = TranscriptEvent(**body, event_hash=canonical_hash(body))
        self._events.append(event)
        return event

    def verify(self) -> bool:
        previous = "GENESIS"
        for expected_sequence, event in enumerate(self._events, start=1):
            body = {
                "sequence": event.sequence, "event_type": event.event_type,
                "subject": event.subject, "payload_digest": event.payload_digest,
                "previous_hash": event.previous_hash,
            }
            if (
                event.sequence != expected_sequence
                or event.previous_hash != previous
                or event.event_hash != canonical_hash(body)
            ):
                return False
            previous = event.event_hash
        return True


@dataclass(frozen=True, slots=True)
class FlightEvent:
    sequence: int
    kind: TraceKind
    subject: str
    correlation_id: str
    duration_ms: float
    proof_refs: tuple[str, ...]
    payload_digest: str


@dataclass(slots=True)
class AgentFlightRecorder:
    mission_id: str
    _events: list[FlightEvent] = field(default_factory=list)

    def record(
        self, *, kind: TraceKind, subject: str, correlation_id: str,
        duration_ms: float, payload: Mapping[str, Any], proof_refs: Iterable[str] = ()
    ) -> FlightEvent:
        if not self.mission_id or not subject or not correlation_id or duration_ms < 0:
            raise ValueError("FLIGHT_RECORDER_EVENT_INVALID")
        event = FlightEvent(
            sequence=len(self._events) + 1,
            kind=kind, subject=subject, correlation_id=correlation_id,
            duration_ms=float(duration_ms),
            proof_refs=tuple(sorted(set(_items(proof_refs)))),
            payload_digest=canonical_hash(payload),
        )
        self._events.append(event)
        return event

    @property
    def events(self) -> tuple[FlightEvent, ...]:
        return tuple(self._events)

    def execution_narrative(self) -> tuple[str, ...]:
        return tuple(
            f"{item.sequence}:{item.kind.value}:{item.subject}:{item.correlation_id}"
            for item in self._events
        )


@dataclass(frozen=True, slots=True)
class CognitiveLoadObservation:
    owner_interventions: int
    clarification_loops: int
    correction_loops: int
    technical_decisions_required: int
    explanation_units: int
    context_switches: int


@dataclass(frozen=True, slots=True)
class CognitiveLoadReceipt:
    raw_index: float
    normalized_index: float
    low_burden: bool
    components: Mapping[str, int]


def cognitive_load_index(observation: CognitiveLoadObservation, *, ceiling: float = 100.0) -> CognitiveLoadReceipt:
    values = asdict(observation)
    if any(int(value) < 0 for value in values.values()) or ceiling <= 0:
        raise ValueError("COGNITIVE_LOAD_COUNTS_OR_CEILING_INVALID")
    weights = {
        "owner_interventions": 8.0,
        "clarification_loops": 5.0,
        "correction_loops": 7.0,
        "technical_decisions_required": 6.0,
        "explanation_units": 1.5,
        "context_switches": 4.0,
    }
    raw = sum(values[key] * weights[key] for key in weights)
    normalized = min(1.0, raw / ceiling)
    return CognitiveLoadReceipt(raw, normalized, normalized <= 0.25, values)


@dataclass(frozen=True, slots=True)
class CanonicalAgentEnvelope:
    protocol: str
    protocol_version: str
    mission_id: str
    capability: str
    operation: str
    arguments_digest: str
    authority_ref: str | None
    trace_id: str
    read_only: bool


SUPPORTED_PROTOCOLS = frozenset({"MCP","A2A","AG_UI","A2UI","MHS"})


def compile_protocol_envelope(
    *, protocol: str, protocol_version: str, mission_id: str,
    capability: str, operation: str, arguments: Mapping[str, Any],
    trace_id: str, read_only: bool, authority_ref: str | None = None
) -> CanonicalAgentEnvelope:
    proto = protocol.strip().upper().replace("-","_")
    if proto not in SUPPORTED_PROTOCOLS:
        raise ValueError("PROTOCOL_NOT_SUPPORTED")
    if not all((protocol_version, mission_id, capability, operation, trace_id)):
        raise ValueError("PROTOCOL_ENVELOPE_IDENTITY_REQUIRED")
    if not read_only and not authority_ref:
        raise ValueError("EFFECTFUL_PROTOCOL_ENVELOPE_AUTHORITY_REQUIRED")
    return CanonicalAgentEnvelope(
        protocol=proto, protocol_version=protocol_version,
        mission_id=mission_id, capability=capability, operation=operation,
        arguments_digest=canonical_hash(arguments), authority_ref=authority_ref,
        trace_id=trace_id, read_only=read_only
    )


@dataclass(frozen=True, slots=True)
class CompiledTool:
    tool_name: str
    method: str
    path: str
    required_inputs: tuple[str, ...]
    effect_class: str
    authority_required: bool
    negative_tests: tuple[str, ...]


def compile_openapi_capabilities(spec: Mapping[str, Any]) -> tuple[CompiledTool, ...]:
    paths = spec.get("paths")
    if not isinstance(paths, Mapping) or not paths:
        raise ValueError("OPENAPI_PATHS_REQUIRED")
    tools: list[CompiledTool] = []
    for path, operations in sorted(paths.items()):
        if not isinstance(operations, Mapping):
            continue
        for method, operation in sorted(operations.items()):
            method_upper = str(method).upper()
            if method_upper not in {"GET","POST","PUT","PATCH","DELETE"} or not isinstance(operation, Mapping):
                continue
            op_id = str(operation.get("operationId") or f"{method_upper}_{path}").strip()
            params = operation.get("parameters") or ()
            required = tuple(sorted(
                str(item.get("name"))
                for item in params if isinstance(item, Mapping) and item.get("required") is True and item.get("name")
            ))
            read_only = method_upper == "GET"
            tools.append(CompiledTool(
                tool_name=op_id, method=method_upper, path=str(path),
                required_inputs=required,
                effect_class="READ_ONLY" if read_only else "PROVIDER_EFFECT",
                authority_required=not read_only,
                negative_tests=(
                    "reject_unknown_parameters",
                    "reject_missing_required_inputs",
                    "reject_effect_without_authority" if not read_only else "assert_no_effect_authority",
                ),
            ))
    if not tools:
        raise ValueError("OPENAPI_NO_SUPPORTED_OPERATIONS")
    return tuple(tools)


@dataclass(frozen=True, slots=True)
class EcologyCapability:
    capability_id: str
    value_score: float
    complexity_cost: float
    invocation_count: int
    dependency_ids: tuple[str, ...]
    semantic_cluster: str
    superseded_by: str | None = None


@dataclass(frozen=True, slots=True)
class EcologyReceipt:
    capability_count: int
    dormant_ids: tuple[str, ...]
    superseded_ids: tuple[str, ...]
    high_overlap_clusters: tuple[str, ...]
    dependency_concentration: float
    aggregate_value_density: float
    actions: tuple[str, ...]
    receipt_sha256: str


def evaluate_capability_ecology(
    capabilities: Sequence[EcologyCapability], *, dormant_threshold: int = 0
) -> EcologyReceipt:
    if not capabilities:
        raise ValueError("ECOLOGY_CAPABILITIES_REQUIRED")
    ids = [item.capability_id for item in capabilities]
    if len(set(ids)) != len(ids):
        raise ValueError("ECOLOGY_CAPABILITY_IDS_UNIQUE_REQUIRED")
    dormant = sorted(item.capability_id for item in capabilities if item.invocation_count <= dormant_threshold)
    superseded = sorted(item.capability_id for item in capabilities if item.superseded_by)
    clusters: dict[str, int] = {}
    dep_counts: dict[str, int] = {}
    total_value, total_cost = 0.0, 0.0
    for item in capabilities:
        if item.value_score < 0 or item.complexity_cost < 0 or item.invocation_count < 0:
            raise ValueError("ECOLOGY_METRICS_NONNEGATIVE_REQUIRED")
        clusters[item.semantic_cluster] = clusters.get(item.semantic_cluster, 0) + 1
        for dep in item.dependency_ids:
            dep_counts[dep] = dep_counts.get(dep, 0) + 1
        total_value += item.value_score
        total_cost += item.complexity_cost
    high_overlap = tuple(sorted(cluster for cluster, count in clusters.items() if cluster and count >= 3))
    max_dep = max(dep_counts.values(), default=0)
    concentration = max_dep / len(capabilities)
    density = total_value / max(total_cost, 1e-9)
    actions: list[str] = []
    actions.extend(f"REVIEW_DORMANT:{item}" for item in dormant)
    actions.extend(f"RETIRE_OR_ALIAS_SUPERSEDED:{item}" for item in superseded)
    actions.extend(f"RUN_EQUIVALENCE_COURT:{cluster}" for cluster in high_overlap)
    if concentration >= 0.5:
        actions.append("REDUCE_DEPENDENCY_CONCENTRATION")
    payload = {
        "capability_count": len(capabilities),
        "dormant_ids": dormant,
        "superseded_ids": superseded,
        "high_overlap_clusters": high_overlap,
        "dependency_concentration": round(concentration, 6),
        "aggregate_value_density": round(density, 6),
        "actions": actions,
    }
    return EcologyReceipt(
        capability_count=len(capabilities), dormant_ids=tuple(dormant),
        superseded_ids=tuple(superseded), high_overlap_clusters=high_overlap,
        dependency_concentration=round(concentration, 6),
        aggregate_value_density=round(density, 6),
        actions=tuple(actions), receipt_sha256=canonical_hash(payload)
    )


def benchmark_summary() -> dict[str, Any]:
    receipt = compile_wave2_receipt()
    return {
        "schema": SCHEMA,
        "wave2_gene_count": receipt.gene_count,
        "routed_count": receipt.routed_count,
        "source_contract_count": receipt.source_contract_count,
        "deep_control_count": receipt.deep_control_count,
        "provider_gated_count": receipt.provider_gated_count,
        "research_gated_count": receipt.research_gated_count,
        "deep_gene_ids": sorted(DEEP_GENE_IDS),
        "truth_boundary": {
            "source_contract_is_not_provider_runtime": True,
            "deep_control_is_not_market_superiority": True,
            "provider_effect_authorized": False,
            "stable_promotion_authorized": False,
            "owner_value_requires_empirical_matched_observations": True,
        },
    }


__all__ = [
    "AdmissionDecision","AgentFlightRecorder","AuthorityDecision","CapabilityDNA",
    "CapabilityGene","CapabilityGrant","CapabilityHypothesis","CausalEdge",
    "CausalGraphReceipt","CanonicalAgentEnvelope","CleanRoomPlan","CognitiveLoadObservation",
    "CognitiveLoadReceipt","CompiledTool","ConformalInterval","DEEP_GENE_IDS",
    "EcologyCapability","EcologyReceipt","ExecutionTranscript","ExperimentCandidate",
    "FiberCheckpoint","FlightEvent","GENE_NAMES","GeneAdmissionInput","GeneAdmissionReceipt",
    "IncidentHarvestProposal","IncidentRecord","MemoryInfluenceReceipt","MemoryItem",
    "NoveltyReceipt","PortableSandboxManifest","REGISTRY_SCHEMA","RouteMode","SCHEMA",
    "SUPPORTED_PROTOCOLS","SemanticFingerprint","Taint","TaintedValue","TraceKind",
    "TranscriptEvent","Wave2ImplementationReceipt","WorkspaceSnapshot",
    "attribute_memory_influence","authorize_capability","benchmark_summary",
    "canonical_hash","cognitive_load_index","compile_capability_dna","compile_causal_graph",
    "compile_clean_room_plan","compile_openapi_capabilities","compile_protocol_envelope",
    "compile_sandbox_manifest","compile_wave2_receipt","compile_workspace_snapshot",
    "conformal_interval","create_fiber_checkpoint","decompose_primitives",
    "detect_semantic_novelty","evaluate_capability_ecology","evaluate_gene_admission",
    "fingerprint","generate_hypothesis","harvest_incident","load_wave2_genome",
    "matched_counterfactual_effect","propagate_taint","reconcile_memory",
    "select_information_gain_experiment","semantic_similarity","taint_flow_allowed",
    "taint_value",
]
