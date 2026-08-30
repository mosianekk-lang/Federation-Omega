from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence

from federation.bubbles_frontier_hyperperformance import CellAllocationDecision, WorkCell
from federation.bubbles_hyperperformance import ContextPressureBudget
from federation.mission_ir import MissionIR

from .bubbles_work_graph_adapter_v1 import (
    BubblesCellShadowReceipt,
    BubblesWorkNode,
    shadow_place_bubbles_work,
)


@dataclass(frozen=True, slots=True)
class MissionExecutionShadowReceipt:
    schema: str
    mission_id: str
    mission_ir_sha256: str
    selected_work_ids: tuple[str, ...]
    cell_shadow_state: str
    cell_placements: tuple[CellAllocationDecision, ...]
    cell_placement_digest: str
    context_budget: ContextPressureBudget
    proof_requirements: tuple[str, ...]
    authority_requirements: tuple[str, ...]
    effect_class: str
    execution_digest: str
    serving_route_changed: bool = False
    provider_effect_authorized: bool = False
    financial_effect_authorized: bool = False
    publication_authorized: bool = False


def _digest(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _context_budget(ir: MissionIR) -> ContextPressureBudget:
    budget = ir.normalized().context_budget
    return ContextPressureBudget(
        max_active_sources=budget.max_active_sources,
        max_heavy_sources=budget.max_heavy_sources,
        max_tool_results=budget.max_tool_results,
        max_tool_payload_chars=budget.max_tool_payload_chars,
        max_capsule_chars=budget.max_capsule_chars,
    )


def shadow_compile_mission_execution(
    mission: MissionIR,
    nodes: Sequence[BubblesWorkNode],
    cells: Sequence[WorkCell],
    *,
    shard_width: int = 1,
    active_ids: Iterable[str] = (),
    completed_ids: Iterable[str] = (),
    critical_regression_ids: Iterable[str] = (),
    live_ready_ids: Iterable[str] = (),
    readiness_blockers: Mapping[str, Iterable[str]] | None = None,
) -> MissionExecutionShadowReceipt:
    """Compile one MissionIR into the existing CFBE/Bubbles shadow execution path.

    CFBE remains the work scheduler. MissionIR supplies shared mission/resource/
    proof constraints. Bubbles cell placement remains shadow-only and cannot
    authorize provider, financial or publication effects.
    """

    normalized = mission.normalized()
    normalized.validate()
    if not nodes:
        raise ValueError("MISSION_EXECUTION_WORK_NODES_REQUIRED")

    shadow: BubblesCellShadowReceipt = shadow_place_bubbles_work(
        nodes,
        cells,
        shard_width=shard_width,
        excluded_failure_domains=normalized.failure_domain_exclusions,
        active_ids=active_ids,
        completed_ids=completed_ids,
        critical_regression_ids=critical_regression_ids,
        live_ready_ids=live_ready_ids,
        readiness_blockers=readiness_blockers,
    )
    mission_sha = normalized.digest()
    payload = {
        "schema": "FEDERATION-MISSION-EXECUTION-SHADOW-V1",
        "mission_id": normalized.mission_id,
        "mission_ir_sha256": mission_sha,
        "selected_work_ids": list(shadow.selected_work_ids),
        "cell_shadow_state": shadow.state,
        "cell_placement_digests": [item.allocation_digest for item in shadow.placements],
        "cell_placement_digest": shadow.placement_digest,
        "context_budget": normalized.canonical_mapping()["context_budget"],
        "proof_requirements": list(normalized.proof_requirements),
        "authority_requirements": list(normalized.authority_requirements),
        "effect_class": normalized.effect_class,
        "serving_route_changed": False,
        "provider_effect_authorized": False,
        "financial_effect_authorized": False,
        "publication_authorized": False,
    }
    return MissionExecutionShadowReceipt(
        schema="FEDERATION-MISSION-EXECUTION-SHADOW-V1",
        mission_id=normalized.mission_id,
        mission_ir_sha256=mission_sha,
        selected_work_ids=shadow.selected_work_ids,
        cell_shadow_state=shadow.state,
        cell_placements=shadow.placements,
        cell_placement_digest=shadow.placement_digest,
        context_budget=_context_budget(normalized),
        proof_requirements=normalized.proof_requirements,
        authority_requirements=normalized.authority_requirements,
        effect_class=normalized.effect_class,
        execution_digest=_digest(payload),
    )
