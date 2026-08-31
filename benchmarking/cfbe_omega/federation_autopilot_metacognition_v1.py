from __future__ import annotations

"""CFBE Omega Full-Autopilot + Meta-Cognition Fabric v1.

Bounded control/compiler layer over existing Federation owners. It does not create
another sovereign scheduler, provider executor, memory service, or authority plane.
Autonomous cognition/workflow selection is explicitly separated from authority to
create external effects. "Meta-cognition" means machine-observable control state,
not disclosure or storage of private chain-of-thought.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
from typing import Iterable, Mapping, Sequence

SCHEMA = "CFBE-FULL-AUTOPILOT-METACOGNITION-V1"


class ImplementationMode(str, Enum):
    REUSE_VERIFIED = "REUSE_VERIFIED"
    COMPOSED_BY_FABRIC = "COMPOSED_BY_FABRIC"
    PROVIDER_GATED_CONTRACT = "PROVIDER_GATED_CONTRACT"


class AutonomyLevel(str, Enum):
    ASSIST = "ASSIST"
    BOUNDED_AUTOPILOT = "BOUNDED_AUTOPILOT"
    UNATTENDED_REVERSIBLE = "UNATTENDED_REVERSIBLE"
    HOLD_OWNER_TRIGGER = "HOLD_OWNER_TRIGGER"
    HOLD_PROVIDER_RUNTIME = "HOLD_PROVIDER_RUNTIME"


class MetaAction(str, Enum):
    CONTINUE = "CONTINUE"
    REFLECT = "REFLECT"
    SEEK_EVIDENCE = "SEEK_EVIDENCE"
    REPLAN = "REPLAN"
    CHALLENGE = "CHALLENGE"
    ROLLBACK = "ROLLBACK"


@dataclass(frozen=True, slots=True)
class AutopilotGene:
    gene_id: str
    domain: str
    control_family: str
    improvement: str
    implementation_mode: ImplementationMode
    implementation_owner: str
    acceptance_gate: str


@dataclass(frozen=True, slots=True)
class ImplementationReceipt:
    schema: str
    gene_count: int
    routed_count: int
    reuse_count: int
    composed_count: int
    provider_gated_count: int
    unrouted_gene_ids: tuple[str, ...]
    provider_runtime_proven: bool = False
    provider_effect_authorized: bool = False
    stable_self_modification_allowed: bool = False

    def canonical_mapping(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MetaCognitiveState:
    confidence: float
    evidence_coverage: float
    contradiction_pressure: float
    novelty: float
    progress: float
    plan_stability: float
    context_freshness: float
    resource_pressure: float
    repeated_failure_count: int = 0


@dataclass(frozen=True, slots=True)
class MetaCognitiveDecision:
    action: MetaAction
    reasons: tuple[str, ...]
    confidence_band: str
    owner_interrupt_required: bool = False


@dataclass(frozen=True, slots=True)
class AutonomyDecision:
    level: AutonomyLevel
    reasons: tuple[str, ...]
    external_effect_authorized: bool = False


@dataclass(frozen=True, slots=True)
class ReflectionDecision:
    run_reflection: bool
    reason: str
    expected_value: float
    bounded_cost: float


@dataclass(frozen=True, slots=True)
class OwnerEscalationDecision:
    interrupt_owner: bool
    exact_trigger: str | None
    exhausted_safe_routes: bool


@dataclass(frozen=True, slots=True)
class TerminalityDecision:
    terminal: bool
    state: str
    missing: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SelfModificationDecision:
    state: str
    delta: float
    stable_promotion_allowed: bool
    rollback_required: bool


@dataclass(frozen=True, slots=True)
class AutopilotProfile:
    schema: str
    mission_id: str
    autonomy: AutonomyDecision
    metacognition: MetaCognitiveDecision
    active_gene_ids: tuple[str, ...]
    provider_gated_gene_ids: tuple[str, ...]
    truth_boundary: tuple[str, ...]


DOMAIN_NAMES = {
    "AUTONOMY": "Mission Autonomy & Goal Management",
    "METACOG": "Meta-Cognitive State & Self-Model",
    "DELIBERATION": "Planning Reflection & Deliberation",
    "DURABILITY": "Durable Unattended Execution & Recovery",
    "EPISTEMIC": "Epistemic Control Truth & Uncertainty",
    "SELF_GOVERNANCE": "Tool Agent & Provider Self-Governance",
    "SELF_EVAL": "Self-Evaluation Calibration & Learning",
    "INTROSPECTION": "Introspection Observability & Self-Diagnosis",
    "OWNER_AUTONOMY": "Owner-Burden Minimization & Autonomy UX",
    "EVOLUTION": "Safe Self-Modification & Evolution",
}

DOMAIN_GENE_NAMES = {
    "AUTONOMY": "Explicit goal-stack compiler|Objective-drift detector|Autonomous next-best-action selector|Dependency-critical-path autopilot|Always-on event-driven mission intake and trigger router|Owner-interruption minimizer|Risk/effect-based autonomy-level selector|Semantic terminality court|Cancellation and compensating-action plan|Multi-mission priority and WIP arbitration".split("|"),
    "METACOG": "Explicit metacognitive state vector|Confidence-to-evidence calibration|Uncertainty decomposition|Contradiction-pressure monitor|Novelty/out-of-distribution detector|Reasoning-stagnation fingerprint detector|Self-capability awareness map|Self-authority awareness boundary|Self-resource budget awareness|Context sufficiency and freshness monitor".split("|"),
    "DELIBERATION": "Pre-action plan-quality court|Trigger-based reflection instead of reflexive self-talk|Reflection return-on-compute budget|Independent challenger-plan generation|Counterfactual route simulation|Pre-mortem failure enumeration|Causal dependency graph maintenance|Hypothesis-counterhypothesis-falsifier ledger|Plan revision as deterministic diff|Rejected-plan learning capture".split("|"),
    "DURABILITY": "Material-step durable checkpoints|Crash-resume without duplicate work|Zero-compute external-wait parking|Human-approval interrupt and resume|Exact idempotent replay identity|Poison-work quarantine/dead-letter lane|Bounded retry with backoff and changed-route rule|Dependency circuit breaker and half-open recovery|Missed-run watchdog and catch-up recovery|Saga-style compensation and rollback orchestration".split("|"),
    "EPISTEMIC": "Evidence-source hierarchy enforcement|FACT/INFERENCE/ANALYSIS/UNVERIFIED typing|Claim-to-proof-class binding|Persistent contradiction ledger|Evidence freshness leases|Evidence-coverage score|Calibrated confidence bands|Active evidence-seeking trigger|Adversarial fact verification|Semantic-fruit terminal verification".split("|"),
    "SELF_GOVERNANCE": "Per-agent capability allowlists|Central versioned toolbox registry|Provider-health-aware route selection|Risk-cost-quality model routing|Tool-failure alternate-route compiler|Lifecycle hook trust and sandbox policy|Minimum-necessary handoff context|Provider identity plus action-specific readback|Single serialized external-effect commit lane|AI asset inventory and lifecycle state".split("|"),
    "SELF_EVAL": "Golden semantic eval registry|Real failure-cluster eval harvesting|Dynamic user-simulation evals|Paired champion/challenger campaigns|Optimizer proposals across instruction/tool/skill/model|No-self-promotion optimizer gate|Regression memory and recurrence prevention|Confidence calibration outcome tracking|Observed value-realization ledger|Holdout/anti-overfitting evaluation set".split("|"),
    "INTROSPECTION": "End-to-end mission trace identity|Turn/tool/guardrail/handoff spans|Metacognitive-state trace fields|Cost/token/latency telemetry|Self-diagnosis incident event|Change-to-regression attribution|Adaptive behavior baseline|Prospective precursor warning|Trace-to-proof lineage|Sensitive introspection suppression".split("|"),
    "OWNER_AUTONOMY": "Owner technical-intervention counter|Ask-once durable decision memory|Preference-evidence memory with confidence|Autonomous recovery before owner escalation|Exact owner-trigger predicate|Batched owner-decision queue|Owner-burden error budget|Explainable autonomy receipt|Reversible-default action policy|Graceful autonomy degradation".split("|"),
    "EVOLUTION": "Capability-gap compiler|Reuse-extend-compose-new-last law|Self-change proposal sandbox|Source-only self-improvement candidate state|Paired-eval self-modification gate|Architecture-sprawl detector|Stable-promotion hysteresis|Automatic rollback on verified regression|Fresh frontier re-benchmark cadence|Constitutional self-challenge".split("|"),
}

FAMILY_OWNERS = {
    "AUTONOMY": "MissionIR + Bubbles + Omega-One + SOVARA",
    "METACOG": "CFBE + Bubbles + JARVIS + Sentinel",
    "DELIBERATION": "CFBE + Formation + Omega-Scientist + JARVIS",
    "DURABILITY": "BCOmega + BMF + Result Fabric + Failure-Win",
    "EPISTEMIC": "EvidenceOps + ProofOS + JARVIS + Terminal Truth",
    "SELF_GOVERNANCE": "SOVARA + Bubbles Agent Fabric + Unified Capability Graph",
    "SELF_EVAL": "CFBE + Failure-Win + ProofOS + BMF",
    "INTROSPECTION": "Bubbles Trace Spine + Sentinel + ProofOS",
    "OWNER_AUTONOMY": "SOVARA + Bubbles + BMF + CFBE",
    "EVOLUTION": "CFBE + Formation + Capability Foundry + JARVIS + Sentinel",
}

FAMILY_GATES = {
    "AUTONOMY": "objective fidelity, bounded autonomy, owner-trigger precision and semantic terminality",
    "METACOG": "calibrated self-state without private-chain-of-thought disclosure or confidence inflation",
    "DELIBERATION": "triggered reflection, challenger/falsifier coverage and minimum-diff replanning",
    "DURABILITY": "checkpoint, resume, idempotency, recovery, compensation and provider-runtime proof where required",
    "EPISTEMIC": "claim strength cannot exceed fresh evidence and proof class",
    "SELF_GOVERNANCE": "least privilege, exact identity, tool/provider health and serialized external effects",
    "SELF_EVAL": "paired evaluation, holdout coverage, no self-promotion and observed outcome learning",
    "INTROSPECTION": "trace completeness with sensitive payload suppression and proof lineage",
    "OWNER_AUTONOMY": "minimize owner burden while escalating only exact non-delegable decisions",
    "EVOLUTION": "reuse-first, sandboxed changes, paired evidence, hysteresis and automatic rollback",
}

REUSE_IDS = frozenset({
    "APM-004","APM-008","APM-014","APM-017","APM-018","APM-024","APM-027","APM-028",
    "APM-032","APM-035","APM-037","APM-038","APM-039","APM-041","APM-042","APM-043",
    "APM-044","APM-045","APM-049","APM-050","APM-051","APM-055","APM-059","APM-064",
    "APM-067","APM-069","APM-071","APM-076","APM-077","APM-078","APM-081","APM-084",
    "APM-091","APM-092","APM-098","APM-099",
})
PROVIDER_GATED_IDS = frozenset({"APM-005","APM-033","APM-058"})


def _band(value: float) -> str:
    return "LOW" if value < 0.35 else "MEDIUM" if value < 0.75 else "HIGH"


def load_genome() -> tuple[AutopilotGene, ...]:
    genes: list[AutopilotGene] = []
    cursor = 1
    for family, names in DOMAIN_GENE_NAMES.items():
        for improvement in names:
            gene_id = f"APM-{cursor:03d}"
            mode = (
                ImplementationMode.PROVIDER_GATED_CONTRACT if gene_id in PROVIDER_GATED_IDS
                else ImplementationMode.REUSE_VERIFIED if gene_id in REUSE_IDS
                else ImplementationMode.COMPOSED_BY_FABRIC
            )
            genes.append(AutopilotGene(
                gene_id, DOMAIN_NAMES[family], family, improvement, mode,
                FAMILY_OWNERS[family], FAMILY_GATES[family],
            ))
            cursor += 1
    validate_genome(tuple(genes))
    return tuple(genes)


def validate_genome(genes: Sequence[AutopilotGene]) -> None:
    if len(genes) != 100:
        raise ValueError(f"AUTOPILOT_METACOG_GENOME_EXPECTED_100_GOT_{len(genes)}")
    ids = [item.gene_id for item in genes]
    if ids != [f"APM-{i:03d}" for i in range(1, 101)] or len(set(ids)) != 100:
        raise ValueError("AUTOPILOT_METACOG_ID_SEQUENCE_INVALID")
    if set(REUSE_IDS) & set(PROVIDER_GATED_IDS):
        raise ValueError("AUTOPILOT_METACOG_MODE_COLLISION")
    if len(DOMAIN_GENE_NAMES) != 10 or any(len(names) != 10 for names in DOMAIN_GENE_NAMES.values()):
        raise ValueError("AUTOPILOT_METACOG_DOMAIN_SHAPE_INVALID")


def compile_implementation_receipt() -> ImplementationReceipt:
    genes = load_genome()
    return ImplementationReceipt(
        SCHEMA, len(genes), len(genes),
        sum(g.implementation_mode == ImplementationMode.REUSE_VERIFIED for g in genes),
        sum(g.implementation_mode == ImplementationMode.COMPOSED_BY_FABRIC for g in genes),
        sum(g.implementation_mode == ImplementationMode.PROVIDER_GATED_CONTRACT for g in genes),
        (),
    )


def metacognitive_assessment(state: MetaCognitiveState) -> MetaCognitiveDecision:
    values = (state.confidence, state.evidence_coverage, state.contradiction_pressure, state.novelty,
              state.progress, state.plan_stability, state.context_freshness, state.resource_pressure)
    if any(not 0.0 <= value <= 1.0 for value in values) or state.repeated_failure_count < 0:
        raise ValueError("METACOG_STATE_INVALID")
    if state.repeated_failure_count >= 3:
        action, reasons = MetaAction.ROLLBACK, ("repeated_failure_threshold",)
    elif state.contradiction_pressure >= 0.65:
        action, reasons = MetaAction.CHALLENGE, ("contradiction_pressure",)
    elif state.evidence_coverage < 0.55 or state.context_freshness < 0.45:
        action, reasons = MetaAction.SEEK_EVIDENCE, ("evidence_or_freshness_gap",)
    elif state.plan_stability < 0.45 or (state.progress < 0.25 and state.resource_pressure >= 0.70):
        action, reasons = MetaAction.REPLAN, ("plan_instability_or_low_progress",)
    elif state.novelty >= 0.70 or state.confidence < 0.45:
        action, reasons = MetaAction.REFLECT, ("novel_or_low_confidence",)
    else:
        action, reasons = MetaAction.CONTINUE, ("state_within_operating_band",)
    effective = min(state.confidence, state.evidence_coverage, state.context_freshness)
    return MetaCognitiveDecision(action, reasons, _band(effective), False)


def reflection_gate(*, trigger_present: bool, expected_decision_gain: float,
                    estimated_reflection_cost: float, hard_deadline_pressure: float = 0.0) -> ReflectionDecision:
    if min(expected_decision_gain, estimated_reflection_cost, hard_deadline_pressure) < 0:
        raise ValueError("REFLECTION_BUDGET_INVALID")
    if not trigger_present:
        return ReflectionDecision(False, "no_material_metacognitive_trigger", expected_decision_gain, estimated_reflection_cost)
    if hard_deadline_pressure >= 0.9 and expected_decision_gain <= estimated_reflection_cost:
        return ReflectionDecision(False, "deadline_pressure_outweighs_reflection_value", expected_decision_gain, estimated_reflection_cost)
    run = expected_decision_gain > estimated_reflection_cost
    return ReflectionDecision(run, "expected_decision_gain_exceeds_cost" if run else "reflection_overhead_not_justified",
                              expected_decision_gain, estimated_reflection_cost)


def autonomy_gate(*, effect_class: str, reversible: bool, exact_authority: bool,
                  provider_runtime_available: bool, evidence_coverage: float,
                  owner_approval_required: bool = False) -> AutonomyDecision:
    effect = effect_class.strip().upper()
    if not 0 <= evidence_coverage <= 1:
        raise ValueError("AUTONOMY_EVIDENCE_INVALID")
    if owner_approval_required:
        return AutonomyDecision(AutonomyLevel.HOLD_OWNER_TRIGGER, ("owner_approval_required",))
    if effect not in {"NO_EFFECT","READ_ONLY","PRIVATE_REVERSIBLE","CONSEQUENTIAL"}:
        raise ValueError("AUTONOMY_EFFECT_CLASS_INVALID")
    if effect == "CONSEQUENTIAL" and not exact_authority:
        return AutonomyDecision(AutonomyLevel.HOLD_OWNER_TRIGGER, ("exact_effect_authority_required",))
    if effect in {"PRIVATE_REVERSIBLE","CONSEQUENTIAL"} and not provider_runtime_available:
        return AutonomyDecision(AutonomyLevel.HOLD_PROVIDER_RUNTIME, ("provider_runtime_open",))
    if evidence_coverage < 0.55:
        return AutonomyDecision(AutonomyLevel.ASSIST, ("insufficient_evidence_for_autopilot",))
    if effect in {"NO_EFFECT","READ_ONLY"}:
        return AutonomyDecision(AutonomyLevel.BOUNDED_AUTOPILOT, ("non_effectful_or_read_only",))
    if reversible and exact_authority:
        return AutonomyDecision(AutonomyLevel.UNATTENDED_REVERSIBLE,
                                ("reversible_effect_with_exact_authority",), True)
    return AutonomyDecision(AutonomyLevel.HOLD_OWNER_TRIGGER, ("irreversible_or_unbounded_effect",))


def owner_escalation_gate(*, safe_routes_remaining: int, exact_owner_decision_required: bool,
                          provider_only_gate: bool, safety_or_legal_gate: bool) -> OwnerEscalationDecision:
    if safe_routes_remaining < 0:
        raise ValueError("OWNER_ESCALATION_ROUTE_COUNT_INVALID")
    if safety_or_legal_gate:
        return OwnerEscalationDecision(True, "safety_or_legal_owner_gate", safe_routes_remaining == 0)
    if exact_owner_decision_required:
        return OwnerEscalationDecision(True, "exact_owner_decision_required", safe_routes_remaining == 0)
    return OwnerEscalationDecision(False, None, safe_routes_remaining == 0)


def stagnation_detected(plan_fingerprints: Sequence[str], evidence_revision_ids: Sequence[str],
                        *, threshold: int = 3) -> bool:
    if threshold < 2:
        raise ValueError("STAGNATION_THRESHOLD_INVALID")
    if len(plan_fingerprints) < threshold:
        return False
    recent = tuple(plan_fingerprints[-threshold:])
    if len(set(recent)) != 1:
        return False
    recent_evidence = tuple(evidence_revision_ids[-threshold:])
    return len(recent_evidence) < threshold or len(set(recent_evidence)) <= 1


def terminality_court(*, objective_satisfied: bool, semantic_readback: bool, proof_complete: bool,
                      unresolved_critical_contradictions: int, external_effect_pending: bool) -> TerminalityDecision:
    if unresolved_critical_contradictions < 0:
        raise ValueError("TERMINALITY_CONTRADICTION_COUNT_INVALID")
    missing = []
    if not objective_satisfied: missing.append("objective")
    if not semantic_readback: missing.append("semantic_readback")
    if not proof_complete: missing.append("proof")
    if unresolved_critical_contradictions: missing.append("critical_contradictions")
    if external_effect_pending: missing.append("external_effect")
    return TerminalityDecision(not missing, "VERIFIED_COMPLETE" if not missing else "CONTINUE_OR_HOLD_EXACT_GATE",
                               tuple(missing))


def self_modification_gate(*, baseline_score: float, candidate_score: float, paired_cases: int,
                           hard_regressions: int, rollback_available: bool,
                           independent_verifier_pass: bool, observed_value_positive: bool) -> SelfModificationDecision:
    if not 0 <= baseline_score <= 1 or not 0 <= candidate_score <= 1:
        raise ValueError("SELF_MOD_SCORE_INVALID")
    if paired_cases < 0 or hard_regressions < 0:
        raise ValueError("SELF_MOD_SAMPLE_INVALID")
    delta = candidate_score - baseline_score
    if hard_regressions:
        return SelfModificationDecision("REJECT_REGRESSION", delta, False, rollback_available)
    if not rollback_available:
        return SelfModificationDecision("HOLD_ROLLBACK_REQUIRED", delta, False, False)
    if paired_cases < 20:
        return SelfModificationDecision("HOLD_PAIRED_EVIDENCE", delta, False, False)
    if delta <= 0:
        return SelfModificationDecision("REJECT_NO_MEASURED_GAIN", delta, False, False)
    if not independent_verifier_pass:
        return SelfModificationDecision("HOLD_INDEPENDENT_VERIFICATION", delta, False, False)
    if not observed_value_positive:
        return SelfModificationDecision("CANDIDATE_VALUE_OPEN", delta, False, False)
    return SelfModificationDecision("CANDIDATE_STABLE_REVIEW", delta, False, False)


def compile_autopilot_profile(*, mission_id: str, effect_class: str, reversible: bool,
                              exact_authority: bool, provider_runtime_available: bool,
                              evidence_coverage: float, meta_state: MetaCognitiveState,
                              owner_approval_required: bool = False,
                              requested_families: Iterable[str] = ()) -> AutopilotProfile:
    mission = mission_id.strip()
    if not mission:
        raise ValueError("AUTOPILOT_MISSION_ID_REQUIRED")
    genes = load_genome()
    autonomy = autonomy_gate(effect_class=effect_class, reversible=reversible,
        exact_authority=exact_authority, provider_runtime_available=provider_runtime_available,
        evidence_coverage=evidence_coverage, owner_approval_required=owner_approval_required)
    meta = metacognitive_assessment(meta_state)
    families = {"AUTONOMY","METACOG","DELIBERATION","EPISTEMIC","SELF_EVAL","INTROSPECTION","OWNER_AUTONOMY"}
    if provider_runtime_available or effect_class.strip().upper() not in {"NO_EFFECT","READ_ONLY"}:
        families.update({"DURABILITY","SELF_GOVERNANCE"})
    if meta.action in {MetaAction.REPLAN, MetaAction.CHALLENGE, MetaAction.ROLLBACK}:
        families.add("EVOLUTION")
    families.update(str(item).strip().upper() for item in requested_families if str(item).strip())
    unknown = families - set(DOMAIN_GENE_NAMES)
    if unknown:
        raise ValueError("AUTOPILOT_UNKNOWN_CONTROL_FAMILY:" + ",".join(sorted(unknown)))
    active = tuple(g.gene_id for g in genes if g.control_family in families)
    gated = tuple(g.gene_id for g in genes if g.gene_id in active and
                  g.implementation_mode == ImplementationMode.PROVIDER_GATED_CONTRACT)
    return AutopilotProfile(SCHEMA, mission, autonomy, meta, active, gated, (
        "autonomous_cognition_does_not_grant_external_effect_authority",
        "metacognitive_state_is_control_metadata_not_private_chain_of_thought",
        "provider_gated_genes_require_provider_native_runtime_or_identity_readback",
        "self_modification_never_self_promotes_stable_state",
        "owner_interruption_is_reserved_for_exact_non_delegable_or_safety_legal_gates",
    ))


def benchmark_dimensions() -> tuple[tuple[str, float, float, str], ...]:
    return (
        ("Goal persistence & objective fidelity",84,70,"prospective long-horizon mission cohorts"),
        ("Autonomous initiative & next-action selection",90,75,"always-on event intake and measured route value"),
        ("Durable unattended execution",74,48,"provider-hosted resumable workflow/sandbox proof"),
        ("Meta-state awareness",78,55,"live calibrated meta-state telemetry"),
        ("Reflection & replanning quality",86,68,"paired reflection-value experiments"),
        ("Uncertainty & calibration",73,50,"prospective confidence-vs-outcome calibration"),
        ("Causal/falsification reasoning",91,78,"prospective causal outcome cohorts"),
        ("Self-capability & authority awareness",94,82,"fresh cross-provider identity/action readback"),
        ("Tool/provider self-governance",91,72,"managed toolbox and provider-health runtime evidence"),
        ("Recovery & anti-stall autonomy",89,74,"sustained unattended recovery cohorts"),
        ("Self-evaluation & optimizer loop",83,62,"real paired optimizer campaigns with holdouts"),
        ("Safe self-modification",85,60,"candidate-to-canary-to-rollback-to-value proof"),
        ("Owner-burden minimization",88,64,"sustained observed burden/value pairs"),
        ("Introspection & observability",90,72,"standardized live meta/agent telemetry"),
        ("Cross-mission autonomous operations",77,54,"always-on multi-mission scheduler and priority cohorts"),
    )


def benchmark_summary() -> dict[str, object]:
    dims = benchmark_dimensions()
    return {
        "schema": "CFBE-AUTOPILOT-METACOG-BENCHMARK-V1",
        "dimension_count": len(dims),
        "architecture_average": round(sum(item[1] for item in dims) / len(dims), 2),
        "proof_adjusted_average": round(sum(item[2] for item in dims) / len(dims), 2),
        "lowest_proof_dimensions": tuple(item[0] for item in sorted(dims, key=lambda row: row[2])[:5]),
        "highest_proof_dimensions": tuple(item[0] for item in sorted(dims, key=lambda row: row[2], reverse=True)[:5]),
        "vendor_certified": False,
        "full_autopilot_runtime_proven": False,
        "private_chain_of_thought_required": False,
    }


def deterministic_receipt_digest(mapping: Mapping[str, object]) -> str:
    material = repr(sorted((str(key), repr(value)) for key, value in mapping.items()))
    return sha256(material.encode("utf-8")).hexdigest()
