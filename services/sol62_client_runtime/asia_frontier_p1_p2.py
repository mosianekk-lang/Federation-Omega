from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable, Mapping, Sequence


SCHEMA = "SOL62_ASIA_FRONTIER_P1_P2_RUNTIME_V1"


class ReasoningMode(str, Enum):
    FAST = "FAST"
    BALANCED = "BALANCED"
    DEEP = "DEEP"


@dataclass(frozen=True)
class ContextItem:
    item_id: str
    text: str
    token_estimate: int
    relevance: float
    currentness: float
    contradiction_risk: float = 0.0
    immutable: bool = False


@dataclass(frozen=True)
class ModelRoute:
    route_id: str
    roles: tuple[str, ...]
    context_limit: int
    multimodalities: tuple[str, ...]
    local: bool
    privacy_fit: float
    reliability: float
    cost: float
    latency_ms: float
    active_compute_ratio: float = 1.0
    callable: bool = True


@dataclass(frozen=True)
class Specialist:
    specialist_id: str
    capabilities: tuple[str, ...]
    privacy_class: str
    max_parallel_tasks: int
    cost_weight: float = 1.0


@dataclass(frozen=True)
class ResearchHypothesis:
    hypothesis_id: str
    claim: str
    falsifier: str
    expected_information_gain: float


@dataclass(frozen=True)
class ResearchResult:
    hypothesis_id: str
    falsified: bool
    evidence_strength: float
    reproducible: bool


@dataclass(frozen=True)
class DeviceCarrier:
    carrier_id: str
    failure_domain: str
    carrier_epoch: int
    healthy: bool
    privacy_fit: float
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeCell:
    cell_id: str
    operations: tuple[str, ...]
    network_enabled: bool
    filesystem_mode: str
    max_cpu: float
    max_memory_mb: int
    callable: bool = True


@dataclass(frozen=True)
class DeploymentCell:
    cell_id: str
    data_residency: str
    operations_residency: str
    technology_control: str
    private_network: bool
    portable_exit: bool
    callable: bool


@dataclass(frozen=True)
class RegionalModelResult:
    model_id: str
    language: str
    matched_samples: int
    quality: float
    code_quality: float
    document_quality: float
    safety: float
    latency_ms: float
    cost: float
    critical_regressions: int = 0


def externalize_working_set(
    items: Sequence[ContextItem],
    *,
    active_token_budget: int,
    contradiction_floor: float = 0.6,
) -> dict[str, object]:
    """Keep a bounded active set while preserving durable external references.

    Immutable/high-contradiction items are preferred into the active set so compaction
    cannot silently erase authority/currentness conflicts.
    """
    if active_token_budget < 1:
        raise ValueError("INVALID_ACTIVE_TOKEN_BUDGET")
    normalized = [
        item for item in items
        if item.token_estimate >= 0
        and 0 <= item.relevance <= 1
        and 0 <= item.currentness <= 1
        and 0 <= item.contradiction_risk <= 1
    ]

    def priority(item: ContextItem) -> tuple[float, float, str]:
        must_preserve = 2.0 if item.immutable else 0.0
        contradiction = 1.0 if item.contradiction_risk >= contradiction_floor else item.contradiction_risk
        value = must_preserve + 0.42 * item.relevance + 0.33 * item.currentness + 0.25 * contradiction
        return (-value, item.token_estimate, item.item_id)

    active: list[ContextItem] = []
    externalized: list[ContextItem] = []
    used = 0
    for item in sorted(normalized, key=priority):
        if used + item.token_estimate <= active_token_budget or (item.immutable and not active):
            active.append(item)
            used += item.token_estimate
        else:
            externalized.append(item)

    return {
        "schema": SCHEMA,
        "state": "READY",
        "mechanism": "EXTERNALIZED_LONG_CONTEXT_WORKING_SET",
        "active_token_budget": active_token_budget,
        "active_token_estimate": used,
        "active_item_ids": [item.item_id for item in active],
        "externalized_item_ids": [item.item_id for item in externalized],
        "contradiction_item_ids": [
            item.item_id for item in normalized if item.contradiction_risk >= contradiction_floor
        ],
        "authority_granted": False,
        "truth_boundary": "WORKING_SET_COMPILED_NE_EXTERNAL_STORE_READBACK_NE_MODEL_CONTEXT_LOADED",
    }


def select_reasoning_effort(
    *,
    risk: float,
    uncertainty: float,
    reversibility: float,
    cost_pressure: float,
    deadline_pressure: float = 0.0,
) -> dict[str, object]:
    values = (risk, uncertainty, reversibility, cost_pressure, deadline_pressure)
    if any(value < 0 or value > 1 for value in values):
        raise ValueError("REASONING_SIGNAL_OUT_OF_RANGE")
    deep_need = 0.42 * risk + 0.36 * uncertainty + 0.22 * (1 - reversibility)
    speed_need = 0.55 * cost_pressure + 0.45 * deadline_pressure
    if deep_need >= 0.68 and speed_need < 0.8:
        mode = ReasoningMode.DEEP
        budget = 1.0
    elif deep_need >= 0.36 or speed_need < 0.45:
        mode = ReasoningMode.BALANCED
        budget = 0.6
    else:
        mode = ReasoningMode.FAST
        budget = 0.3
    return {
        "schema": SCHEMA,
        "mechanism": "TASK_RISK_SCALED_THINKING_EFFORT",
        "mode": mode.value,
        "reasoning_budget_fraction": budget,
        "deep_need": deep_need,
        "speed_need": speed_need,
        "authority_granted": False,
    }


def compile_engineering_loop(
    *,
    requirement: str,
    repo_epoch: str,
    tests_available: bool,
    acceptance_predicates: Sequence[str],
) -> dict[str, object]:
    if not requirement.strip():
        return {"schema": SCHEMA, "state": "HOLD", "reason": "REQUIREMENT_REQUIRED"}
    if not repo_epoch.strip():
        return {"schema": SCHEMA, "state": "HOLD", "reason": "REPO_EPOCH_REQUIRED"}
    predicates = tuple(item.strip() for item in acceptance_predicates if item.strip())
    if not predicates:
        return {"schema": SCHEMA, "state": "HOLD", "reason": "ACCEPTANCE_PREDICATES_REQUIRED"}
    phases = [
        "CLARIFY_REQUIREMENT",
        "READ_CURRENT_SOURCE",
        "PLAN_MINIMUM_DELTA",
        "IMPLEMENT",
        "STATIC_ANALYSIS",
    ]
    if tests_available:
        phases.extend(["RUN_TARGETED_TESTS", "DEBUG_FAILURES", "RUN_REGRESSION_TESTS"])
    else:
        phases.append("BUILD_MINIMUM_TEST_HARNESS")
    phases.extend(["SEMANTIC_READBACK", "PROOF_ENVELOPE", "INDEPENDENT_REVIEW"])
    return {
        "schema": SCHEMA,
        "state": "READY",
        "mechanism": "REQUIREMENT_TO_CODE_DEBUG_VALIDATE_END_TO_END",
        "requirement": requirement,
        "repo_epoch": repo_epoch,
        "acceptance_predicates": list(predicates),
        "phases": phases,
        "source_mutation_authority_granted": False,
        "truth_boundary": "ENGINEERING_LOOP_COMPILED_NE_SOURCE_CHANGED_NE_TEST_PASS_NE_SOURCE_ADMITTED",
    }


def terminal_coding_loop_state(
    *,
    compile_pass: bool,
    targeted_tests_pass: bool,
    regression_tests_pass: bool,
    semantic_readback_pass: bool,
    unresolved_failures: int,
) -> dict[str, object]:
    if unresolved_failures < 0:
        raise ValueError("NEGATIVE_FAILURE_COUNT")
    if not compile_pass:
        next_action = "REPAIR_COMPILE"
    elif not targeted_tests_pass:
        next_action = "DEBUG_TARGETED_FAILURES"
    elif not regression_tests_pass:
        next_action = "REPAIR_REGRESSION"
    elif not semantic_readback_pass:
        next_action = "REPAIR_SEMANTIC_MISMATCH"
    elif unresolved_failures:
        next_action = "RESOLVE_REMAINING_FAILURES"
    else:
        next_action = "READY_FOR_PROOFOS"
    return {
        "schema": SCHEMA,
        "mechanism": "TERMINAL_AGENT_BUGFIX_REFACTOR_COMPLEX_TASK_LOOP",
        "next_action": next_action,
        "local_complete": next_action == "READY_FOR_PROOFOS",
        "source_admitted": False,
    }


def compile_deep_retrieval_plan(
    *,
    query: str,
    allowed_surfaces: Sequence[str],
    privacy_class: str,
    require_primary_sources: bool = True,
) -> dict[str, object]:
    if not query.strip():
        return {"schema": SCHEMA, "state": "HOLD", "reason": "QUERY_REQUIRED"}
    surfaces = [surface.upper() for surface in allowed_surfaces]
    safe = [surface for surface in surfaces if surface in {"MEMORY", "KDV", "FILES", "MCP", "WEB", "GITHUB", "DRIVE"}]
    if not safe:
        return {"schema": SCHEMA, "state": "HOLD", "reason": "NO_ALLOWED_RETRIEVAL_SURFACE"}
    if privacy_class.upper() in {"SECRET", "HIGHLY_SENSITIVE"}:
        safe = [surface for surface in safe if surface in {"MEMORY", "KDV", "FILES", "DRIVE"}]
    if not safe:
        return {"schema": SCHEMA, "state": "HOLD", "reason": "PRIVACY_ELIMINATED_ALL_SURFACES"}
    ordered = sorted(
        safe,
        key=lambda item: (
            {"MEMORY": 0, "KDV": 1, "FILES": 2, "DRIVE": 3, "GITHUB": 4, "MCP": 5, "WEB": 6}.get(item, 9),
            item,
        ),
    )
    return {
        "schema": SCHEMA,
        "state": "READY",
        "mechanism": "WEB_SEARCH_FETCH_SKILL_MCP_EXPLORATION",
        "query": query,
        "privacy_class": privacy_class,
        "surfaces": ordered,
        "require_primary_sources": require_primary_sources,
        "contradiction_detection": True,
        "source_provenance_required": True,
        "authority_granted": False,
    }


def hybrid_reasoning_route(
    *,
    task_complexity: float,
    uncertainty: float,
    failure_cost: float,
    observed_fast_confidence: float,
) -> dict[str, object]:
    values = (task_complexity, uncertainty, failure_cost, observed_fast_confidence)
    if any(value < 0 or value > 1 for value in values):
        raise ValueError("HYBRID_SIGNAL_OUT_OF_RANGE")
    escalation_need = (
        0.34 * task_complexity
        + 0.33 * uncertainty
        + 0.33 * failure_cost
        + 0.25 * (1 - observed_fast_confidence)
    )
    use_deep = escalation_need >= 0.7
    return {
        "schema": SCHEMA,
        "mechanism": "HYBRID_FAST_AND_SLOW_THINKING_ROUTE",
        "first_pass": "FAST",
        "escalate_to": "DEEP" if use_deep else "NONE",
        "escalation_need": escalation_need,
        "fast_result_may_commit_effect": False,
        "authority_granted": False,
    }


def select_efficient_model_route(
    routes: Sequence[ModelRoute],
    *,
    required_role: str,
    required_context: int = 0,
    required_modalities: Sequence[str] = (),
    minimum_privacy: float = 0.0,
) -> dict[str, object]:
    role = required_role.upper()
    modalities = {item.lower() for item in required_modalities}
    eligible = [
        route
        for route in routes
        if route.callable
        and role in {item.upper() for item in route.roles}
        and route.context_limit >= required_context
        and modalities.issubset({item.lower() for item in route.multimodalities})
        and route.privacy_fit >= minimum_privacy
        and 0 < route.active_compute_ratio <= 1
    ]
    if not eligible:
        return {"schema": SCHEMA, "state": "HOLD", "reason": "NO_EFFICIENT_MODEL_ROUTE"}

    def score(route: ModelRoute) -> tuple[float, str]:
        efficiency = (
            0.34 * route.reliability
            + 0.26 * route.privacy_fit
            + 0.18 * (1 - min(route.active_compute_ratio, 1.0))
            - 0.12 * min(route.cost / 10.0, 1.0)
            - 0.10 * min(route.latency_ms / 30_000.0, 1.0)
        )
        return efficiency, route.route_id

    selected = max(eligible, key=score)
    return {
        "schema": SCHEMA,
        "state": "READY",
        "mechanism": "MOE_ACTIVE_PARAMETER_COST_PERFORMANCE_OPTIMIZATION",
        "selected_route_id": selected.route_id,
        "active_compute_ratio": selected.active_compute_ratio,
        "score": score(selected)[0],
        "provider_call_authority_granted": False,
    }


def synthesize_specialist_collective(
    tasks: Sequence[tuple[str, str]],
    specialists: Sequence[Specialist],
) -> dict[str, object]:
    assignments: dict[str, list[str]] = {row.specialist_id: [] for row in specialists}
    unassigned: list[str] = []
    for task_id, capability in tasks:
        candidates = [
            specialist
            for specialist in specialists
            if capability.upper() in {item.upper() for item in specialist.capabilities}
            and len(assignments[specialist.specialist_id]) < specialist.max_parallel_tasks
        ]
        if not candidates:
            unassigned.append(task_id)
            continue
        chosen = min(
            candidates,
            key=lambda row: (
                len(assignments[row.specialist_id]),
                row.cost_weight,
                row.specialist_id,
            ),
        )
        assignments[chosen.specialist_id].append(task_id)
    return {
        "schema": SCHEMA,
        "state": "READY" if not unassigned else "PARTIAL",
        "mechanism": "DYNAMIC_SPECIALIST_MODEL_AND_AGENT_SYNTHESIS",
        "assignments": {key: value for key, value in assignments.items() if value},
        "unassigned_task_ids": unassigned,
        "authority_granted": False,
    }


def recursive_research_cycle(
    hypotheses: Sequence[ResearchHypothesis],
    results: Sequence[ResearchResult],
    *,
    max_next_hypotheses: int = 8,
) -> dict[str, object]:
    result_by_id = {row.hypothesis_id: row for row in results}
    accepted: list[str] = []
    falsified: list[str] = []
    unresolved: list[str] = []
    scores: list[tuple[float, str]] = []
    for hypothesis in hypotheses:
        result = result_by_id.get(hypothesis.hypothesis_id)
        if result is None:
            unresolved.append(hypothesis.hypothesis_id)
            scores.append((hypothesis.expected_information_gain, hypothesis.hypothesis_id))
            continue
        if result.falsified:
            falsified.append(hypothesis.hypothesis_id)
        elif result.evidence_strength >= 0.8 and result.reproducible:
            accepted.append(hypothesis.hypothesis_id)
        else:
            unresolved.append(hypothesis.hypothesis_id)
            scores.append((
                hypothesis.expected_information_gain * (1 - result.evidence_strength),
                hypothesis.hypothesis_id,
            ))
    next_ids = [
        hypothesis_id
        for _, hypothesis_id in sorted(scores, key=lambda row: (-row[0], row[1]))[:max_next_hypotheses]
    ]
    return {
        "schema": SCHEMA,
        "state": "READY",
        "mechanism": "EXPERIMENT_FALSIFY_LEARN_RECURSIVE_IMPROVEMENT",
        "accepted_hypothesis_ids": accepted,
        "falsified_hypothesis_ids": falsified,
        "unresolved_hypothesis_ids": unresolved,
        "next_hypothesis_ids": next_ids,
        "self_modification_authority_granted": False,
        "promotion_requires_independent_judge": True,
    }


def compile_cross_system_automation(
    *,
    intent: str,
    systems: Sequence[str],
    data_classes: Mapping[str, str],
) -> dict[str, object]:
    if not intent.strip():
        return {"schema": SCHEMA, "state": "HOLD", "reason": "INTENT_REQUIRED"}
    normalized = [system.upper() for system in systems if system.strip()]
    if not normalized:
        return {"schema": SCHEMA, "state": "HOLD", "reason": "SYSTEM_REQUIRED"}
    steps = []
    for index, system in enumerate(normalized, start=1):
        data_class = data_classes.get(system, "UNKNOWN")
        steps.append({
            "step_id": f"xsys-{index:03d}",
            "system": system,
            "data_class": data_class,
            "effect_state": "UNAUTHORIZED_UNTIL_PREFLIGHT",
            "semantic_readback_required": True,
            "idempotency_required": True,
        })
    return {
        "schema": SCHEMA,
        "state": "READY",
        "mechanism": "UNSTRUCTURED_INPUT_TO_MULTI_SYSTEM_WEB_EXECUTION",
        "intent": intent,
        "steps": steps,
        "effect_authority_granted": False,
        "truth_boundary": "CROSS_SYSTEM_PLAN_NE_EXTERNAL_EFFECT_NE_PROPAGATION_SUCCESS",
    }


def select_compact_private_multimodal(
    routes: Sequence[ModelRoute],
    *,
    max_cost: float,
    minimum_privacy: float,
    modalities: Sequence[str],
) -> dict[str, object]:
    required = {item.lower() for item in modalities}
    eligible = [
        route
        for route in routes
        if route.callable
        and route.local
        and route.cost <= max_cost
        and route.privacy_fit >= minimum_privacy
        and required.issubset({item.lower() for item in route.multimodalities})
    ]
    if not eligible:
        return {"schema": SCHEMA, "state": "HOLD", "reason": "NO_COMPACT_PRIVATE_MULTIMODAL_ROUTE"}
    selected = max(
        eligible,
        key=lambda route: (
            0.5 * route.reliability
            + 0.35 * route.privacy_fit
            - 0.15 * min(route.active_compute_ratio, 1.0),
            route.route_id,
        ),
    )
    return {
        "schema": SCHEMA,
        "state": "READY",
        "mechanism": "COMPACT_SINGLE_GPU_PRIVATE_DOCUMENT_VISION",
        "selected_route_id": selected.route_id,
        "provider_call_authority_granted": False,
    }


def compile_cross_device_takeover(
    *,
    mission_id: str,
    current_carrier_id: str,
    current_carrier_epoch: int,
    candidates: Sequence[DeviceCarrier],
    inflight_effect_ids: Sequence[str] = (),
) -> dict[str, object]:
    eligible = [
        carrier for carrier in candidates
        if carrier.healthy and carrier.carrier_id != current_carrier_id
    ]
    if not eligible:
        return {"schema": SCHEMA, "state": "HOLD", "reason": "NO_HEALTHY_REPLACEMENT_CARRIER"}
    selected = max(
        eligible,
        key=lambda row: (
            row.failure_domain != next(
                (c.failure_domain for c in candidates if c.carrier_id == current_carrier_id),
                "",
            ),
            row.privacy_fit,
            row.carrier_epoch,
            row.carrier_id,
        ),
    )
    return {
        "schema": SCHEMA,
        "state": "READBACK_REQUIRED" if inflight_effect_ids else "READY",
        "mechanism": "REMOTE_SESSION_TAKEOVER_WITHOUT_MISSION_RESTART",
        "mission_id": mission_id,
        "failed_or_replaced_carrier_id": current_carrier_id,
        "replacement_carrier_id": selected.carrier_id,
        "new_mission_carrier_epoch": current_carrier_epoch + 1,
        "inflight_effect_ids": list(inflight_effect_ids),
        "effect_readback_before_takeover_commit": bool(inflight_effect_ids),
        "authority_granted": False,
    }


def multimodal_surface_contract(
    *,
    modalities: Sequence[str],
    gui_actions_required: bool,
) -> dict[str, object]:
    allowed = {"text", "image", "audio", "video", "document", "screen", "gui"}
    normalized = {item.lower() for item in modalities}
    unsupported = sorted(normalized - allowed)
    if unsupported:
        return {
            "schema": SCHEMA,
            "state": "HOLD",
            "reason": "UNSUPPORTED_MODALITIES",
            "unsupported": unsupported,
        }
    if gui_actions_required:
        normalized.add("gui")
    return {
        "schema": SCHEMA,
        "state": "READY",
        "mechanism": "UNIFIED_VIDEO_IMAGE_AUDIO_TEXT_PLUS_GUI_AGENT",
        "modalities": sorted(normalized),
        "gui_effect_authority_granted": False,
        "perception_ne_effect": True,
        "post_action_readback_required": gui_actions_required,
    }


def compile_private_enterprise_dev_plane(
    routes: Sequence[ModelRoute],
    *,
    required_roles: Sequence[str],
    minimum_privacy: float = 0.9,
) -> dict[str, object]:
    required = {role.upper() for role in required_roles}
    qualified = [
        route for route in routes
        if route.callable
        and route.privacy_fit >= minimum_privacy
        and required.intersection({role.upper() for role in route.roles})
    ]
    coverage: dict[str, list[str]] = {role: [] for role in sorted(required)}
    for route in qualified:
        for role in required.intersection({item.upper() for item in route.roles}):
            coverage[role].append(route.route_id)
    missing = [role for role, ids in coverage.items() if not ids]
    return {
        "schema": SCHEMA,
        "state": "READY" if not missing else "HOLD",
        "mechanism": "MULTI_MODEL_PRIVATE_VPC_CODING_PLANE",
        "role_coverage": coverage,
        "missing_roles": missing,
        "provider_call_authority_granted": False,
    }


def plan_first_alignment(
    *,
    objective: str,
    constraints: Sequence[str],
    acceptance_predicates: Sequence[str],
    ambiguities: Sequence[str] = (),
) -> dict[str, object]:
    if not objective.strip():
        return {"schema": SCHEMA, "state": "HOLD", "reason": "OBJECTIVE_REQUIRED"}
    predicates = [item.strip() for item in acceptance_predicates if item.strip()]
    if not predicates:
        return {"schema": SCHEMA, "state": "HOLD", "reason": "ACCEPTANCE_PREDICATE_REQUIRED"}
    unresolved = [item.strip() for item in ambiguities if item.strip()]
    return {
        "schema": SCHEMA,
        "state": "HOLD" if unresolved else "READY",
        "mechanism": "CLARIFY_PLAN_ALIGN_THEN_EXECUTE",
        "objective": objective,
        "constraints": [item for item in constraints if item.strip()],
        "acceptance_predicates": predicates,
        "unresolved_ambiguities": unresolved,
        "execution_allowed": not unresolved,
        "authority_granted": False,
    }


def typed_code_runtime_adapter(
    *,
    operation: str,
    cell: RuntimeCell,
    requested_network: bool,
    requested_filesystem_mode: str,
    cpu: float,
    memory_mb: int,
) -> dict[str, object]:
    operation_upper = operation.upper()
    if not cell.callable:
        return {"schema": SCHEMA, "state": "HOLD", "reason": "RUNTIME_CELL_UNCALLABLE"}
    if operation_upper not in {item.upper() for item in cell.operations}:
        return {"schema": SCHEMA, "state": "HOLD", "reason": "OPERATION_UNSUPPORTED"}
    if requested_network and not cell.network_enabled:
        return {"schema": SCHEMA, "state": "HOLD", "reason": "NETWORK_NOT_ALLOWED"}
    if requested_filesystem_mode.upper() != cell.filesystem_mode.upper():
        return {"schema": SCHEMA, "state": "HOLD", "reason": "FILESYSTEM_MODE_MISMATCH"}
    if cpu > cell.max_cpu or memory_mb > cell.max_memory_mb:
        return {"schema": SCHEMA, "state": "HOLD", "reason": "RESOURCE_LIMIT_EXCEEDED"}
    return {
        "schema": SCHEMA,
        "state": "READY",
        "mechanism": "TYPED_OPTIONAL_CODE_RUNTIME_CAPABILITY_SEAM",
        "cell_id": cell.cell_id,
        "operation": operation_upper,
        "effect_authority_granted": False,
        "sandbox_preflight_required": True,
        "semantic_readback_required": True,
    }


def select_sovereign_deployment(
    cells: Sequence[DeploymentCell],
    *,
    required_data_residency: str,
    required_operations_residency: str,
    required_technology_control: str,
    private_network_required: bool = True,
) -> dict[str, object]:
    eligible = [
        cell for cell in cells
        if cell.callable
        and cell.data_residency == required_data_residency
        and cell.operations_residency == required_operations_residency
        and cell.technology_control == required_technology_control
        and (not private_network_required or cell.private_network)
        and cell.portable_exit
    ]
    if not eligible:
        return {"schema": SCHEMA, "state": "HOLD", "reason": "NO_SOVEREIGN_DEPLOYMENT_CELL"}
    selected = sorted(eligible, key=lambda row: row.cell_id)[0]
    return {
        "schema": SCHEMA,
        "state": "READY",
        "mechanism": "DATA_OPERATION_AND_TECHNOLOGY_SOVEREIGNTY_CELL",
        "selected_cell_id": selected.cell_id,
        "portable_exit": selected.portable_exit,
        "deployment_authority_granted": False,
    }


def evaluate_regional_models(
    results: Sequence[RegionalModelResult],
    *,
    language: str,
    minimum_samples: int = 12,
) -> dict[str, object]:
    eligible = [
        row for row in results
        if row.language.lower() == language.lower()
        and row.matched_samples >= minimum_samples
        and row.critical_regressions == 0
    ]
    if not eligible:
        return {
            "schema": SCHEMA,
            "state": "UNPROVEN",
            "mechanism": "REGIONAL_MODEL_MATCHED_EVALUATION",
            "language": language,
            "selected_model_id": None,
        }

    def score(row: RegionalModelResult) -> tuple[float, str]:
        value = (
            0.28 * row.quality
            + 0.22 * row.code_quality
            + 0.20 * row.document_quality
            + 0.20 * row.safety
            - 0.05 * min(row.latency_ms / 30_000.0, 1.0)
            - 0.05 * min(row.cost / 10.0, 1.0)
        )
        return value, row.model_id

    selected = max(eligible, key=score)
    return {
        "schema": SCHEMA,
        "state": "MEASURED",
        "mechanism": "JAPANESE_OPTIMIZED_OPEN_MOE_CODE_AND_DOCUMENT_MODEL_EVALUATION",
        "language": language,
        "selected_model_id": selected.model_id,
        "score": score(selected)[0],
        "market_superiority_proven": False,
    }


P1_GENES: tuple[dict[str, object], ...] = (
    {"gene_id": "AF-CHN-KIMI-002", "mechanism": "ultra_long_context_with_externalized_working_set"},
    {"gene_id": "AF-CHN-KIMI-004", "mechanism": "task_risk_scaled_thinking_effort"},
    {"gene_id": "AF-CHN-SEED-002", "mechanism": "requirement_to_code_debug_validate_end_to_end"},
    {"gene_id": "AF-CHN-QWEN-001", "mechanism": "terminal_agent_bugfix_refactor_complex_task_loop"},
    {"gene_id": "AF-CHN-BAIDU-002", "mechanism": "web_search_fetch_skill_mcp_exploration"},
    {"gene_id": "AF-CHN-TENCENT-001", "mechanism": "hybrid_fast_and_slow_thinking_route"},
    {"gene_id": "AF-CHN-TENCENT-002", "mechanism": "moe_active_parameter_cost_performance_optimization"},
    {"gene_id": "AF-JPN-SAKANA-002", "mechanism": "dynamic_specialist_model_and_agent_synthesis"},
    {"gene_id": "AF-JPN-SAKANA-003", "mechanism": "experiment_falsify_learn_recursive_improvement"},
    {"gene_id": "AF-JPN-NEC-002", "mechanism": "unstructured_input_to_multi_system_web_execution"},
    {"gene_id": "AF-JPN-NTT-001", "mechanism": "compact_single_gpu_private_document_vision"},
)

P2_GENES: tuple[dict[str, object], ...] = (
    {"gene_id": "AF-CHN-KIMI-003", "mechanism": "remote_session_takeover_without_mission_restart"},
    {"gene_id": "AF-CHN-SEED-003", "mechanism": "unified_video_image_audio_text_plus_gui_agent"},
    {"gene_id": "AF-CHN-QODER-001", "mechanism": "multi_model_private_vpc_coding_plane"},
    {"gene_id": "AF-CHN-BAIDU-001", "mechanism": "clarify_plan_align_then_execute"},
    {"gene_id": "AF-CHN-DEEPSEEK-002", "mechanism": "typed_optional_code_runtime_capability_seam"},
    {"gene_id": "AF-JPN-SB-001", "mechanism": "data_operation_and_technology_sovereignty_cell"},
    {"gene_id": "AF-JPN-RAKUTEN-001", "mechanism": "japanese_optimized_open_moe_code_and_document_model"},
)


def compile_p1_p2_plan(*, objective: str, reason: str) -> dict[str, object]:
    semantic = f"{objective} {reason}".lower()
    keywords = {
        "ultra_long_context_with_externalized_working_set": ("context", "memory", "long", "continuity"),
        "task_risk_scaled_thinking_effort": ("reason", "risk", "uncertain", "complex"),
        "requirement_to_code_debug_validate_end_to_end": ("code", "build", "software", "debug"),
        "terminal_agent_bugfix_refactor_complex_task_loop": ("terminal", "bug", "refactor", "test"),
        "web_search_fetch_skill_mcp_exploration": ("search", "research", "mcp", "retrieval"),
        "hybrid_fast_and_slow_thinking_route": ("fast", "deep", "reason", "latency"),
        "moe_active_parameter_cost_performance_optimization": ("cost", "model", "compute", "latency"),
        "dynamic_specialist_model_and_agent_synthesis": ("specialist", "agent", "model", "collective"),
        "experiment_falsify_learn_recursive_improvement": ("research", "experiment", "falsify", "learn"),
        "unstructured_input_to_multi_system_web_execution": ("system", "web", "workflow", "automation"),
        "compact_single_gpu_private_document_vision": ("private", "local", "document", "vision"),
        "remote_session_takeover_without_mission_restart": ("remote", "device", "handoff", "session"),
        "unified_video_image_audio_text_plus_gui_agent": ("video", "image", "audio", "gui", "multimodal"),
        "multi_model_private_vpc_coding_plane": ("private", "enterprise", "coding", "vpc"),
        "clarify_plan_align_then_execute": ("plan", "clarify", "align", "requirement"),
        "typed_optional_code_runtime_capability_seam": ("runtime", "code", "sandbox", "tool"),
        "data_operation_and_technology_sovereignty_cell": ("sovereign", "residency", "private", "control"),
        "japanese_optimized_open_moe_code_and_document_model": ("japanese", "regional", "language", "document"),
    }

    def rank(rows: Sequence[dict[str, object]]) -> list[dict[str, object]]:
        scored = []
        for row in rows:
            mechanism = str(row["mechanism"])
            score = sum(1 for key in keywords[mechanism] if key in semantic)
            scored.append((-score, mechanism, row))
        return [row for _, _, row in sorted(scored)]

    return {
        "schema": SCHEMA,
        "state": "P1_P2_RUNTIME_MECHANISMS_AVAILABLE",
        "p1": rank(P1_GENES),
        "p2": rank(P2_GENES),
        "p1_count": len(P1_GENES),
        "p2_count": len(P2_GENES),
        "source_mutation_authority_granted": False,
        "provider_effect_authority_granted": False,
        "market_superiority_proven": False,
        "truth_boundary": (
            "P1_P2_SOURCE_IMPLEMENTED_NE_RUNTIME_CALLED_NE_NATURAL_EVIDENCE_"
            "NE_MATCHED_FRONTIER_PASS_NE_JUDGE_ACK_NE_SOURCE_ADMITTED_NE_MARKET_SUPERIORITY"
        ),
    }
