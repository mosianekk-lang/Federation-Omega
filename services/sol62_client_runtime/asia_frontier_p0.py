from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from math import ceil
from typing import Iterable, Mapping, Sequence


SCHEMA = "SOL62_ASIA_FRONTIER_P0_RUNTIME_V1"


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    HOLD = "HOLD"


@dataclass(frozen=True)
class SwarmTask:
    task_id: str
    capability: str
    estimated_tool_calls: int = 1
    dependency_ids: tuple[str, ...] = ()
    privacy_class: str = "INTERNAL"
    authority_scope: str = "READ_ONLY"


@dataclass(frozen=True)
class SwarmShard:
    shard_id: str
    task_ids: tuple[str, ...]
    tool_call_budget: int
    privacy_class: str
    authority_scope: str


@dataclass(frozen=True)
class WorkflowEpisode:
    episode_id: str
    accepted: bool
    completed: bool
    owner_interventions: int
    tool_calls: int
    wall_time_ms: int
    critical_regressions: int = 0


@dataclass(frozen=True)
class SandboxRequest:
    operation: str
    requested_capabilities: tuple[str, ...]
    command_fingerprint: str
    network_domains: tuple[str, ...] = ()
    filesystem_roots: tuple[str, ...] = ()


@dataclass(frozen=True)
class SandboxGrant:
    allowed_capabilities: tuple[str, ...]
    allowed_network_domains: tuple[str, ...] = ()
    allowed_filesystem_roots: tuple[str, ...] = ()
    exact_command_fingerprint: str = ""


@dataclass(frozen=True)
class RouteCandidate:
    route_id: str
    capability_fit: float
    reliability: float
    privacy: float
    portability: float
    latency_ms: float
    cost: float
    energy_units: float
    authority_valid: bool = True
    callable: bool = True


@dataclass(frozen=True)
class DemonstrationStep:
    operation: str
    semantic_target: Mapping[str, str]
    value: str = ""
    origin: str = "https://chatgpt.com"
    effect_class: str = "READ_ONLY"


@dataclass(frozen=True)
class SpecialistModelCell:
    cell_id: str
    roles: tuple[str, ...]
    provider: str
    locality: str
    callable: bool
    privacy_fit: float
    reliability: float
    cost: float
    latency_ms: float


def compile_bounded_swarm(
    tasks: Sequence[SwarmTask],
    *,
    max_subagents: int = 32,
    max_tool_calls: int = 512,
    max_tasks_per_agent: int = 16,
) -> dict[str, object]:
    """Compile a bounded, dependency-aware swarm plan.

    The compiler never creates authority. Tasks with different privacy or authority
    envelopes are never co-sharded. Dependency cycles are held rather than guessed.
    """
    if max_subagents < 1 or max_tool_calls < 1 or max_tasks_per_agent < 1:
        raise ValueError("INVALID_SWARM_BOUNDS")
    task_by_id = {task.task_id: task for task in tasks}
    if len(task_by_id) != len(tasks):
        raise ValueError("DUPLICATE_TASK_ID")

    indegree = {task.task_id: 0 for task in tasks}
    children: dict[str, list[str]] = {task.task_id: [] for task in tasks}
    missing_dependencies: list[str] = []
    for task in tasks:
        for dependency in task.dependency_ids:
            if dependency not in task_by_id:
                missing_dependencies.append(f"{task.task_id}:{dependency}")
                continue
            indegree[task.task_id] += 1
            children[dependency].append(task.task_id)

    if missing_dependencies:
        return {
            "schema": SCHEMA,
            "state": "HOLD",
            "reason": "MISSING_DEPENDENCIES",
            "missing_dependencies": sorted(missing_dependencies),
            "authority_granted": False,
            "shards": [],
        }

    ready = sorted(task_id for task_id, degree in indegree.items() if degree == 0)
    ordered: list[str] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for child in sorted(children[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()

    if len(ordered) != len(tasks):
        return {
            "schema": SCHEMA,
            "state": "HOLD",
            "reason": "DEPENDENCY_CYCLE",
            "authority_granted": False,
            "shards": [],
        }

    requested_calls = sum(max(1, task.estimated_tool_calls) for task in tasks)
    if requested_calls > max_tool_calls:
        return {
            "schema": SCHEMA,
            "state": "HOLD",
            "reason": "TOOL_CALL_BUDGET_EXCEEDED",
            "requested_tool_calls": requested_calls,
            "max_tool_calls": max_tool_calls,
            "authority_granted": False,
            "shards": [],
        }

    groups: dict[tuple[str, str], list[SwarmTask]] = {}
    for task_id in ordered:
        task = task_by_id[task_id]
        groups.setdefault((task.privacy_class, task.authority_scope), []).append(task)

    shards: list[SwarmShard] = []
    shard_index = 1
    for (privacy_class, authority_scope), group in sorted(groups.items()):
        for offset in range(0, len(group), max_tasks_per_agent):
            rows = group[offset : offset + max_tasks_per_agent]
            shards.append(
                SwarmShard(
                    shard_id=f"swarm-{shard_index:03d}",
                    task_ids=tuple(task.task_id for task in rows),
                    tool_call_budget=sum(max(1, task.estimated_tool_calls) for task in rows),
                    privacy_class=privacy_class,
                    authority_scope=authority_scope,
                )
            )
            shard_index += 1

    if len(shards) > max_subagents:
        return {
            "schema": SCHEMA,
            "state": "HOLD",
            "reason": "SUBAGENT_BUDGET_EXCEEDED",
            "requested_subagents": len(shards),
            "max_subagents": max_subagents,
            "authority_granted": False,
            "shards": [asdict(shard) for shard in shards[:max_subagents]],
        }

    return {
        "schema": SCHEMA,
        "state": "READY",
        "mechanism": "DYNAMIC_BOUNDED_SUBAGENT_SWARM",
        "task_count": len(tasks),
        "subagent_count": len(shards),
        "tool_call_budget": requested_calls,
        "authority_granted": False,
        "shards": [asdict(shard) for shard in shards],
        "truth_boundary": "SWARM_PLAN_READY_NE_TASK_EXECUTED_NE_EFFECT_AUTHORIZED_NE_OWNER_VALUE",
    }


def evaluate_real_workflow(episodes: Sequence[WorkflowEpisode]) -> dict[str, object]:
    """Evaluate real workflow episodes without converting synthetic success into value."""
    if not episodes:
        return {
            "schema": SCHEMA,
            "state": "UNPROVEN",
            "episode_count": 0,
            "acceptance_rate": 0.0,
            "completion_rate": 0.0,
            "critical_regressions": 0,
        }
    count = len(episodes)
    accepted = sum(1 for row in episodes if row.accepted)
    completed = sum(1 for row in episodes if row.completed)
    interventions = sum(max(0, row.owner_interventions) for row in episodes)
    tool_calls = sum(max(0, row.tool_calls) for row in episodes)
    wall = sum(max(0, row.wall_time_ms) for row in episodes)
    critical = sum(max(0, row.critical_regressions) for row in episodes)
    return {
        "schema": SCHEMA,
        "state": "MEASURED" if critical == 0 else "REGRESSION_HOLD",
        "episode_count": count,
        "acceptance_rate": accepted / count,
        "completion_rate": completed / count,
        "owner_interventions_per_episode": interventions / count,
        "tool_calls_per_episode": tool_calls / count,
        "wall_time_ms_per_episode": wall / count,
        "critical_regressions": critical,
        "promotion_allowed": False,
        "truth_boundary": "WORKFLOW_MEASURED_NE_MATCHED_MARKET_WIN_NE_OWNER_VALUE_VERIFIED",
    }


def sandbox_preflight(request: SandboxRequest, grant: SandboxGrant | None) -> dict[str, object]:
    """Deny first; permit only the exact granted residual capability envelope."""
    if grant is None:
        return {
            "schema": SCHEMA,
            "decision": Decision.DENY.value,
            "reason": "NO_SCOPED_GRANT",
            "authority_granted": False,
        }
    requested = set(request.requested_capabilities)
    allowed = set(grant.allowed_capabilities)
    if not requested.issubset(allowed):
        return {
            "schema": SCHEMA,
            "decision": Decision.DENY.value,
            "reason": "CAPABILITY_SCOPE_EXCEEDED",
            "denied_capabilities": sorted(requested - allowed),
            "authority_granted": False,
        }
    if grant.exact_command_fingerprint and request.command_fingerprint != grant.exact_command_fingerprint:
        return {
            "schema": SCHEMA,
            "decision": Decision.DENY.value,
            "reason": "COMMAND_FINGERPRINT_MISMATCH",
            "authority_granted": False,
        }
    if not set(request.network_domains).issubset(set(grant.allowed_network_domains)):
        return {
            "schema": SCHEMA,
            "decision": Decision.DENY.value,
            "reason": "NETWORK_SCOPE_EXCEEDED",
            "authority_granted": False,
        }
    if not set(request.filesystem_roots).issubset(set(grant.allowed_filesystem_roots)):
        return {
            "schema": SCHEMA,
            "decision": Decision.DENY.value,
            "reason": "FILESYSTEM_SCOPE_EXCEEDED",
            "authority_granted": False,
        }
    return {
        "schema": SCHEMA,
        "decision": Decision.ALLOW.value,
        "reason": "EXACT_SCOPED_GRANT_MATCH",
        "authority_granted": False,
        "execution_authority_must_be_revalidated_at_effect_time": True,
    }


def _dominates(left: RouteCandidate, right: RouteCandidate) -> bool:
    left_benefit = (left.capability_fit, left.reliability, left.privacy, left.portability)
    right_benefit = (right.capability_fit, right.reliability, right.privacy, right.portability)
    left_cost = (left.latency_ms, left.cost, left.energy_units)
    right_cost = (right.latency_ms, right.cost, right.energy_units)
    no_worse = all(a >= b for a, b in zip(left_benefit, right_benefit)) and all(
        a <= b for a, b in zip(left_cost, right_cost)
    )
    strictly_better = any(a > b for a, b in zip(left_benefit, right_benefit)) or any(
        a < b for a, b in zip(left_cost, right_cost)
    )
    return no_worse and strictly_better


def pareto_route_portfolio(routes: Sequence[RouteCandidate]) -> tuple[RouteCandidate, ...]:
    eligible = [
        route
        for route in routes
        if route.callable
        and route.authority_valid
        and 0 <= route.capability_fit <= 1
        and 0 <= route.reliability <= 1
        and 0 <= route.privacy <= 1
        and 0 <= route.portability <= 1
        and route.latency_ms >= 0
        and route.cost >= 0
        and route.energy_units >= 0
    ]
    frontier = [
        route
        for route in eligible
        if not any(_dominates(other, route) for other in eligible if other.route_id != route.route_id)
    ]
    return tuple(sorted(frontier, key=lambda row: row.route_id))


def select_pareto_route(routes: Sequence[RouteCandidate]) -> dict[str, object]:
    frontier = pareto_route_portfolio(routes)
    if not frontier:
        return {
            "schema": SCHEMA,
            "state": "HOLD",
            "reason": "NO_ELIGIBLE_PARETO_ROUTE",
            "selected_route_id": None,
        }

    def score(route: RouteCandidate) -> tuple[float, float, str]:
        benefit = (
            0.28 * route.capability_fit
            + 0.24 * route.reliability
            + 0.20 * route.privacy
            + 0.12 * route.portability
        )
        normalized_penalty = (
            0.07 * min(route.latency_ms / 30_000.0, 1.0)
            + 0.05 * min(route.cost / 10.0, 1.0)
            + 0.04 * min(route.energy_units / 10.0, 1.0)
        )
        return (benefit - normalized_penalty, route.reliability, route.route_id)

    selected = max(frontier, key=score)
    return {
        "schema": SCHEMA,
        "state": "READY",
        "mechanism": "PARETO_CAPABILITY_COST_ORCHESTRATION",
        "selected_route_id": selected.route_id,
        "frontier_route_ids": [row.route_id for row in frontier],
        "score": score(selected)[0],
        "authority_granted": False,
        "truth_boundary": "ROUTE_SELECTED_NE_PROVIDER_EFFECT_NE_VERIFIED_REALITY",
    }


def compile_demonstration_workflow(
    steps: Sequence[DemonstrationStep],
    *,
    allowed_origins: Iterable[str] = ("https://chatgpt.com",),
) -> dict[str, object]:
    """Turn a demonstration into typed semantic commands; never record raw JS/coordinates."""
    origins = set(allowed_origins)
    commands: list[dict[str, object]] = []
    supported = {"FOCUS_ELEMENT", "SCROLL_ELEMENT", "CLICK_ELEMENT", "FILL_ELEMENT", "SEMANTIC_SNAPSHOT"}
    for index, step in enumerate(steps, start=1):
        operation = step.operation.upper()
        if operation not in supported:
            return {
                "schema": SCHEMA,
                "state": "HOLD",
                "reason": "UNSUPPORTED_DEMONSTRATION_OPERATION",
                "step": index,
                "operation": operation,
            }
        if step.origin not in origins:
            return {
                "schema": SCHEMA,
                "state": "HOLD",
                "reason": "ORIGIN_NOT_ADMITTED",
                "step": index,
                "origin": step.origin,
            }
        if not step.semantic_target and operation != "SEMANTIC_SNAPSHOT":
            return {
                "schema": SCHEMA,
                "state": "HOLD",
                "reason": "SEMANTIC_TARGET_REQUIRED",
                "step": index,
            }
        if any(key.lower() in {"x", "y", "selector", "javascript", "eval"} for key in step.semantic_target):
            return {
                "schema": SCHEMA,
                "state": "HOLD",
                "reason": "UNSAFE_OR_BRITTLE_TARGET_ENCODING",
                "step": index,
            }
        mutating = operation in {"CLICK_ELEMENT", "FILL_ELEMENT"}
        if mutating and step.effect_class != "WEBSITE_STATE":
            return {
                "schema": SCHEMA,
                "state": "HOLD",
                "reason": "MUTATION_EFFECT_CLASS_REQUIRED",
                "step": index,
            }
        commands.append(
            {
                "step_id": f"demo-{index:03d}",
                "operation": operation,
                "origin": step.origin,
                "effect_class": step.effect_class,
                "semantic_target": dict(step.semantic_target),
                "value": step.value if operation == "FILL_ELEMENT" else "",
                "requires_action_bound_authority": mutating,
                "requires_semantic_readback": True,
                "idempotency_required": True,
            }
        )
    return {
        "schema": SCHEMA,
        "state": "READY",
        "mechanism": "DEMONSTRATION_TO_SAFE_REPLAYABLE_BROWSER_WORKFLOW",
        "command_count": len(commands),
        "commands": commands,
        "authority_granted": False,
        "truth_boundary": "DEMONSTRATION_COMPILED_NE_BROWSER_EFFECT_NE_WORKFLOW_VALUE_VERIFIED",
    }


class SpecialistRegistry:
    def __init__(self, cells: Sequence[SpecialistModelCell]) -> None:
        ids = [cell.cell_id for cell in cells]
        if len(ids) != len(set(ids)):
            raise ValueError("DUPLICATE_SPECIALIST_CELL")
        self.cells = tuple(cells)

    def select(self, role: str, *, minimum_privacy: float = 0.0) -> dict[str, object]:
        role_upper = role.upper()
        eligible = [
            cell
            for cell in self.cells
            if cell.callable
            and role_upper in {item.upper() for item in cell.roles}
            and cell.privacy_fit >= minimum_privacy
        ]
        if not eligible:
            return {
                "schema": SCHEMA,
                "state": "HOLD",
                "reason": "NO_QUALIFIED_SPECIALIST",
                "role": role_upper,
                "selected_cell_id": None,
            }

        def score(cell: SpecialistModelCell) -> tuple[float, str]:
            value = (
                0.42 * cell.reliability
                + 0.38 * cell.privacy_fit
                - 0.10 * min(cell.cost / 10.0, 1.0)
                - 0.10 * min(cell.latency_ms / 30_000.0, 1.0)
            )
            return value, cell.cell_id

        selected = max(eligible, key=score)
        return {
            "schema": SCHEMA,
            "state": "READY",
            "mechanism": "SPECIALIST_MODEL_REGISTRY",
            "role": role_upper,
            "selected_cell_id": selected.cell_id,
            "provider": selected.provider,
            "locality": selected.locality,
            "score": score(selected)[0],
            "authority_granted": False,
            "truth_boundary": "SPECIALIST_SELECTED_NE_PROVIDER_CALL_NE_RESULT_ACCEPTED",
        }


def compile_p0_plan(*, objective: str, reason: str) -> dict[str, object]:
    """Expose the six P0 mechanisms to SOL's existing harvester without self-certification."""
    semantic = f"{objective} {reason}".lower()
    mechanisms = (
        {
            "gene_id": "AF-CHN-KIMI-001",
            "mechanism": "dynamic_large_scale_subagent_swarm",
            "target_organs": ["ALPHA_OMEGA", "FUSE_SOVEREIGN_PLANE", "WORK_PLANE", "PORTFOLIO_V2"],
        },
        {
            "gene_id": "AF-CHN-SEED-001",
            "mechanism": "live_workflow_over_static_benchmark_evaluation",
            "target_organs": ["CFBE", "PROOFOS", "REALITY_JUDGE"],
        },
        {
            "gene_id": "AF-CHN-DEEPSEEK-001",
            "mechanism": "deny_first_subprocess_sandbox_then_scoped_escalation",
            "target_organs": ["SANDBOX_EXECUTION", "FDOF", "SICF"],
        },
        {
            "gene_id": "AF-JPN-SAKANA-001",
            "mechanism": "pareto_capability_cost_model_orchestration",
            "target_organs": ["PORTFOLIO_V2", "FUSE_ECOSYSTEM", "CAPABILITY_REGISTRY"],
        },
        {
            "gene_id": "AF-JPN-NEC-001",
            "mechanism": "demonstration_to_safe_replayable_browser_workflow",
            "target_organs": ["BROWSER_CONTROL_PLANE", "FUSE_WORKSPACE", "PROOFOS"],
        },
        {
            "gene_id": "AF-JPN-SB-002",
            "mechanism": "guard_embedding_rerank_generation_specialists",
            "target_organs": ["CAPABILITY_REGISTRY", "RETRIEVAL", "REALITY_GUARD", "PORTFOLIO_V2"],
        },
    )
    keywords = {
        "dynamic_large_scale_subagent_swarm": ("parallel", "swarm", "subagent", "throughput"),
        "live_workflow_over_static_benchmark_evaluation": ("benchmark", "workflow", "evaluation", "value"),
        "deny_first_subprocess_sandbox_then_scoped_escalation": ("sandbox", "code", "execute", "security"),
        "pareto_capability_cost_model_orchestration": ("route", "cost", "latency", "model", "provider"),
        "demonstration_to_safe_replayable_browser_workflow": ("browser", "gui", "workflow", "demonstration"),
        "guard_embedding_rerank_generation_specialists": ("retrieval", "guard", "rerank", "embedding", "model"),
    }
    scored: list[tuple[int, str, dict[str, object]]] = []
    for item in mechanisms:
        mechanism = str(item["mechanism"])
        score = sum(1 for key in keywords[mechanism] if key in semantic)
        scored.append((-score, mechanism, item))
    selected = [item for _, _, item in sorted(scored)]
    return {
        "schema": SCHEMA,
        "state": "P0_RUNTIME_MECHANISMS_AVAILABLE",
        "mechanism_count": len(selected),
        "selected": selected,
        "source_mutation_authority_granted": False,
        "provider_effect_authority_granted": False,
        "market_superiority_proven": False,
        "truth_boundary": (
            "P0_SOURCE_IMPLEMENTED_NE_RUNTIME_CALLED_NE_MATCHED_BENCHMARK_PASS_"
            "NE_JUDGE_ACK_NE_SOURCE_ADMITTED_NE_OWNER_VALUE_NE_MARKET_SUPERIORITY"
        ),
    }
