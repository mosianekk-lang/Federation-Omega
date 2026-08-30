from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence

from federation.bubbles_frontier_hyperperformance import (
    CellAllocationDecision,
    WorkCell,
    WorkCellAllocator,
)

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


@dataclass(frozen=True, slots=True)
class BubblesCellShadowReceipt:
    """Shadow-only capacity/failure-domain placements for a CFBE-selected work wave."""

    state: str
    selected_work_ids: tuple[str, ...]
    placements: tuple[CellAllocationDecision, ...]
    placement_digest: str
    cell_occupancy: tuple[tuple[str, int], ...] = ()
    remaining_capacity: tuple[tuple[str, int], ...] = ()
    saturated_cell_ids: tuple[str, ...] = ()
    backpressure_work_ids: tuple[str, ...] = ()
    serving_route_changed: bool = False
    provider_effect_authorized: bool = False
    financial_effect_authorized: bool = False


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


def shadow_place_bubbles_work(
    nodes: Sequence[BubblesWorkNode],
    cells: Sequence[WorkCell],
    *,
    shard_width: int = 1,
    excluded_failure_domains: Iterable[str] = (),
    initial_occupancy: Mapping[str, int] | None = None,
    active_ids: Iterable[str] = (),
    completed_ids: Iterable[str] = (),
    critical_regression_ids: Iterable[str] = (),
    live_ready_ids: Iterable[str] = (),
    readiness_blockers: Mapping[str, Iterable[str]] | None = None,
) -> BubblesCellShadowReceipt:
    """Place only the already-selected CFBE work wave into bounded work cells.

    CFBE still owns work selection. Bubbles consumes that immutable selection and
    computes capacity/failure-domain placement in shadow mode. Backpressure never
    rewrites the serving CFBE wave, changes a route or grants an external effect.
    """

    wave = plan_bubbles_work_graph(
        nodes,
        active_ids=active_ids,
        completed_ids=completed_ids,
        critical_regression_ids=critical_regression_ids,
        live_ready_ids=live_ready_ids,
        readiness_blockers=readiness_blockers,
    )
    selected_ids = tuple(item.capability_id for item in wave.selected)
    if not selected_ids:
        # Preserve the pre-capacity adapter's neutral no-op behavior. An empty
        # CFBE wave has nothing for Bubbles to place, so cell/capacity validation
        # must not manufacture a failure or alter the serving scheduler result.
        digest_payload = {
            "selected_work_ids": selected_ids,
            "placement_digests": [],
            "state": "SHADOW_READY",
            "serving_route_changed": False,
        }
        placement_digest = sha256(
            json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return BubblesCellShadowReceipt(
            state="SHADOW_READY",
            selected_work_ids=selected_ids,
            placements=(),
            placement_digest=placement_digest,
        )

    allocation = WorkCellAllocator().allocate_wave(
        selected_ids,
        cells,
        shard_width=shard_width,
        excluded_failure_domains=excluded_failure_domains,
        require_distinct_failure_domains=True,
        initial_occupancy=initial_occupancy,
    )
    if allocation.state == "WAVE_ALLOCATED":
        state = "SHADOW_READY"
    elif allocation.state == "WAVE_BACKPRESSURE":
        state = "SHADOW_BACKPRESSURE"
    else:
        state = "SHADOW_HELD"
    digest_payload = {
        "selected_work_ids": selected_ids,
        "wave_allocation_digest": allocation.allocation_digest,
        "state": state,
        "serving_route_changed": False,
    }
    placement_digest = sha256(
        json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return BubblesCellShadowReceipt(
        state=state,
        selected_work_ids=selected_ids,
        placements=allocation.placements,
        placement_digest=placement_digest,
        cell_occupancy=allocation.occupancy,
        remaining_capacity=allocation.remaining_capacity,
        saturated_cell_ids=allocation.saturated_cell_ids,
        backpressure_work_ids=allocation.backpressure_work_ids,
    )
