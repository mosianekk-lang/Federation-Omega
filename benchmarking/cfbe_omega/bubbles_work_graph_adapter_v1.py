from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .closure_matrix_v1 import ClosureWaveReceipt, plan_wave


@dataclass(frozen=True, slots=True)
class BubblesWorkNode:
    work_id: str
    capability: str
    rail: str
    next_action: str
    dependencies: tuple[str, ...] = ()
    closure_state: str = "INTEGRATE"
    priority: int = 100
    role: str = "PRIMARY"


_CLOSURE_STATES = (
    "REUSE_NOW",
    "INTEGRATE",
    "EXTEND",
    "BUILD",
    "DATA_NEEDED",
    "PROVIDER_GATED",
    "VALUE_GATED",
    "HOLD",
    "RETIRE_DUPLICATE",
)


def compile_work_graph(nodes: Sequence[BubblesWorkNode]) -> dict[str, object]:
    """Translate Bubbles work into the admitted CFBE closure-matrix contract.

    This adapter creates no second scheduler and grants no provider or financial
    authority. Scheduling behavior remains owned by CFBE ``plan_wave``.
    """

    if not nodes:
        raise ValueError("BUBBLES_WORK_GRAPH_NODES_REQUIRED")
    ids = [node.work_id for node in nodes]
    if any(not item for item in ids) or len(set(ids)) != len(ids):
        raise ValueError("BUBBLES_WORK_GRAPH_IDS_INVALID")
    known = set(ids)
    for node in nodes:
        if not node.capability or not node.rail or not node.next_action:
            raise ValueError(f"BUBBLES_WORK_GRAPH_NODE_INCOMPLETE:{node.work_id}")
        if node.closure_state not in _CLOSURE_STATES:
            raise ValueError(f"BUBBLES_WORK_GRAPH_STATE_INVALID:{node.work_id}")
        if node.role not in {"PRIMARY", "CHALLENGER"}:
            raise ValueError(f"BUBBLES_WORK_GRAPH_ROLE_INVALID:{node.work_id}")
        if any(dep not in known for dep in node.dependencies):
            raise ValueError(f"BUBBLES_WORK_GRAPH_UNKNOWN_DEPENDENCY:{node.work_id}")
        if node.work_id in node.dependencies:
            raise ValueError(f"BUBBLES_WORK_GRAPH_SELF_DEPENDENCY:{node.work_id}")

    ranked = sorted(nodes, key=lambda item: (item.priority, item.rail, item.work_id))
    rails = {node.rail: {"owner": "BUBBLES_CFBE_ADAPTER"} for node in nodes}
    rows = [
        {
            "id": node.work_id,
            "capability": node.capability,
            "rail": node.rail,
            "closure_state": node.closure_state,
            "dependencies": list(node.dependencies),
            "next_action": node.next_action,
        }
        for node in nodes
    ]
    return {
        "schema": "CFBE-OMEGA-CONVERGENCE-CAPABILITY-CLOSURE-MATRIX-V1",
        "rails": rails,
        "closure_states": list(_CLOSURE_STATES),
        "rows": rows,
        "highest_leverage_red_cells": [node.work_id for node in ranked],
        "first_closure_slice": {"target": ranked[0].work_id},
        "scheduler_policy": {
            "wip_limit_per_rail": 2,
            "primary_build_limit_per_rail": 1,
            "challenger_limit_per_rail": 1,
            "blocked_lane_isolation": True,
        },
        "truth_boundary": {
            "live_financial_effect_requires_separate_explicit_authority": True,
            "provider_effect_authorized_by_schedule": False,
            "financial_effect_authorized_by_schedule": False,
        },
    }


def plan_bubbles_work_graph(
    nodes: Sequence[BubblesWorkNode],
    *,
    active_ids: Iterable[str] = (),
    completed_ids: Iterable[str] = (),
    critical_regression_ids: Iterable[str] = (),
    live_ready_ids: Iterable[str] = (),
    readiness_blockers: Mapping[str, Iterable[str]] | None = None,
) -> ClosureWaveReceipt:
    matrix = compile_work_graph(nodes)
    roles = {node.work_id: node.role for node in nodes}
    return plan_wave(
        matrix,
        active_ids=active_ids,
        completed_ids=completed_ids,
        roles=roles,
        live_ready_ids=live_ready_ids,
        critical_regression_ids=critical_regression_ids,
        readiness_blockers=readiness_blockers,
    )
