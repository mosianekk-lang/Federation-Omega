from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImprovementSpec:
    improvement_id: str
    category: str
    title: str
    frontier_gene: str
    target_module: str
    priority: str
    proof_gate: str


_CATEGORY_META = {
    "MISSION_INTELLIGENCE": ("AGENT_PLANNING+HANDOFFS+EVALUATOR_OPTIMIZER", "mission_compiler", "DETERMINISTIC_COMPILER_COURT"),
    "DURABLE_EXECUTION": ("TEMPORAL_DURABLE_EXECUTION+KUBERNETES_RECONCILIATION", "autopilot", "RESTART_RECOVERY_COURT"),
    "LEARNING_MEMORY": ("CORRECTION_DRIVEN_SKILL_EVOLUTION+PERSISTENT_STATE", "taste+learning", "REPLAY_AND_NON_SYNTHETIC_LEARNING_COURT"),
    "EVAL_SCIENCE": ("AGENT_EVALS+CHAMPION_CHALLENGER+FALSIFICATION", "meta_benchmark", "PREREGISTERED_EVAL_COURT"),
    "SCHEDULING": ("RAY_RESOURCE_AWARE_SCHEDULING+BACKPRESSURE", "scheduler", "LOAD_AND_FAILURE_DOMAIN_COURT"),
    "PROVIDER_ROUTING": ("MODEL_ROUTING+HEDGED_FALLBACK+CAPABILITY_MATCHING", "router+provider_mesh", "PROVIDER_NATIVE_READBACK_COURT"),
    "ASSET_VERSION_FABRIC": ("CONTENT_ADDRESSING+LINEAGE+SELECTIVE_INVALIDATION", "version_tree+asset_registry", "ASSET_INTEGRITY_COURT"),
    "OBSERVABILITY_PROOF": ("TRACING+STRUCTURED_EVENTS+PROOF_LINKAGE", "telemetry+proof", "TRACE_AND_READBACK_COURT"),
    "SECURITY_GOVERNANCE": ("LEAST_AUTHORITY+GUARDRAILS+POLICY_AS_CODE", "policy+authority", "AUTHORITY_AND_PRIVACY_COURT"),
    "VALUE_INTELLIGENCE": ("SLO_ERROR_BUDGETS+UNIT_ECONOMICS+OUTCOME_FEEDBACK", "commercial_value", "MEASURED_VALUE_COURT"),
}


_CATEGORY_TITLES = {
    "MISSION_INTELLIGENCE": (
        "Native intent-to-program compiler",
        "Goal decomposition into typed creative stages",
        "Dynamic workflow-versus-agent complexity selection",
        "Explicit outcome contracts per mission",
        "Automatic proof requirement compilation",
        "Automatic authority requirement compilation",
        "Context-budget compilation per stage",
        "Constraint propagation across the mission DAG",
        "Deterministic handoff contracts between creative subsystems",
        "Mission program digest and replay identity",
    ),
    "DURABLE_EXECUTION": (
        "Checkpoint every material mission transition",
        "Crash-safe mission resume",
        "Idempotent stage replay",
        "Bounded retry policy by failure class",
        "Automatic reroute after retry exhaustion",
        "Desired-state reconciliation loop",
        "Dead-letter isolation for terminal failures",
        "Compensation and rollback plans",
        "Lease-based stale-work rejection",
        "Cross-process result reuse without recomputation",
    ),
    "LEARNING_MEMORY": (
        "Durable TasteMemory persistence",
        "Correction-to-taste automatic learning",
        "Conflict-preserving preference learning",
        "Confidence decay and recency weighting",
        "Mission outcome episodic memory",
        "Failure pattern memory",
        "Successful route memory",
        "Skill update proposals from repeated corrections",
        "Memory compaction without losing proof lineage",
        "Cross-mission transfer only after bounded promotion",
    ),
    "EVAL_SCIENCE": (
        "Per-mission evaluator rubric compilation",
        "Automatic golden-case generation",
        "Adversarial creative regression cases",
        "Champion-challenger route tournaments",
        "Competing-hypothesis preregistration",
        "Counterfactual route comparison",
        "Quality-cost-latency Pareto scoring",
        "Regression-triggered automatic rollback candidate",
        "Repeated-cohort confidence estimation",
        "Promotion only after measured owner-value gain",
    ),
    "SCHEDULING": (
        "Resource-aware work graph scheduler",
        "Bounded parallel creative lanes",
        "Backpressure under tool or context saturation",
        "Failure-domain-aware lane isolation",
        "Priority inheritance for blocked critical paths",
        "Cancellation of obsolete speculative work",
        "Work stealing for idle specialist lanes",
        "Adaptive concurrency from observed throughput",
        "Deadline-aware stage prioritization",
        "Cost-aware scheduling before paid routes",
    ),
    "PROVIDER_ROUTING": (
        "Capability-contract provider selection",
        "Fresh provider-health leases",
        "Semantic readback before provider promotion",
        "Automatic zero-cost route preference when adequate",
        "Fallback without silent model substitution",
        "Provider diversity to reduce correlated failure",
        "Hedged read-only requests for tail-latency control",
        "Provider circuit breakers",
        "Model performance memory by creative task class",
        "Route retirement when a challenger repeatedly dominates",
    ),
    "ASSET_VERSION_FABRIC": (
        "Real durable creative asset registry",
        "Content-addressed asset storage",
        "Asset-to-mission provenance binding",
        "Rights and consent attached to asset lineage",
        "Branchable creative versions",
        "Selective Ripple invalidation",
        "Locked approved asset protection",
        "Deterministic package manifests",
        "Cross-format derivative lineage",
        "Garbage collection only for unreachable non-authoritative objects",
    ),
    "OBSERVABILITY_PROOF": (
        "Unified mission trace identifiers",
        "Stage-level structured event stream",
        "Tool-call latency and payload telemetry",
        "Provider semantic receipt correlation",
        "Proof graph links from claim to source and runtime",
        "Freshness lease telemetry",
        "Automatic anomaly and stall detection",
        "Recovery-time and retry telemetry",
        "Owner-intervention telemetry",
        "End-to-end mission value trace",
    ),
    "SECURITY_GOVERNANCE": (
        "Least-authority execution by stage",
        "External-effect firewall",
        "Finite-spend envelopes",
        "Publication release gates",
        "Privacy-class propagation into every route",
        "Rights-state propagation into every asset and provider request",
        "Secret-reference-only public source policy",
        "Sandbox high-risk generated code",
        "Policy drift detection",
        "Immutable audit receipts for consequential transitions",
    ),
    "VALUE_INTELLIGENCE": (
        "Creative quality baseline per content class",
        "Owner minutes per mission baseline",
        "Owner interventions per mission baseline",
        "Time-to-reviewable-output baseline",
        "Provider cost per accepted asset",
        "Recovery cost per failure",
        "Channel package throughput measurement",
        "Commercial outcome attribution",
        "SLO and error-budget governance",
        "Automatic CFBE reinvestment into highest-value gap",
    ),
}


def build_improvement_catalog() -> tuple[ImprovementSpec, ...]:
    rows: list[ImprovementSpec] = []
    ordinal = 1
    for category, titles in _CATEGORY_TITLES.items():
        frontier_gene, target_module, proof_gate = _CATEGORY_META[category]
        for index, title in enumerate(titles, start=1):
            priority = "P0" if index <= 4 else "P1" if index <= 7 else "P2"
            rows.append(
                ImprovementSpec(
                    improvement_id=f"SC-AUTO-{ordinal:03d}",
                    category=category,
                    title=title,
                    frontier_gene=frontier_gene,
                    target_module=target_module,
                    priority=priority,
                    proof_gate=proof_gate,
                )
            )
            ordinal += 1
    if len(rows) != 100:
        raise AssertionError("SOVARA improvement genome must contain exactly 100 improvements")
    return tuple(rows)


IMPROVEMENT_CATALOG = build_improvement_catalog()


def improvements_for(*, categories: tuple[str, ...] = (), priorities: tuple[str, ...] = ()) -> tuple[ImprovementSpec, ...]:
    category_set = {item.strip().upper() for item in categories if item.strip()}
    priority_set = {item.strip().upper() for item in priorities if item.strip()}
    return tuple(
        item
        for item in IMPROVEMENT_CATALOG
        if (not category_set or item.category in category_set)
        and (not priority_set or item.priority in priority_set)
    )
