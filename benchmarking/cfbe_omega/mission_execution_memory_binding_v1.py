from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from benchmarking.cfbe_omega.bible_memory_capture_adapter_v1 import (
    BibleMemoryCaptureAdapter,
    MissionResultCapture,
)
from benchmarking.cfbe_omega.bible_memory_fabric_v1 import MemoryEvent
from benchmarking.cfbe_omega.bubbles_work_graph_adapter_v1 import BubblesWorkNode
from benchmarking.cfbe_omega.mission_execution_adapter_v1 import (
    MissionExecutionShadowReceipt,
    shadow_compile_mission_execution,
)
from federation.bubbles_frontier_hyperperformance import WorkCell
from federation.mission_ir import MissionIR


@dataclass(frozen=True, slots=True)
class MissionExecutionMemoryShadowReceipt:
    """Existing shadow execution receipt plus non-persisted BMF capture events."""

    schema: str
    execution: MissionExecutionShadowReceipt
    memory_events: tuple[MemoryEvent, MemoryEvent]
    memory_state: str = "SHADOW_EMITTED_NOT_PERSISTED"
    provider_persisted: bool = False
    provider_effect_authorized: bool = False
    publication_authorized: bool = False


def shadow_compile_mission_execution_with_memory(
    mission: MissionIR,
    nodes: Sequence[BubblesWorkNode],
    cells: Sequence[WorkCell],
    *,
    observed_at: str,
    source_refs: Iterable[str],
    stream_start_version: int = 1,
    cell_provider_aliases: Mapping[str, str] | None = None,
    shard_width: int = 1,
    active_ids: Iterable[str] = (),
    completed_ids: Iterable[str] = (),
    critical_regression_ids: Iterable[str] = (),
    live_ready_ids: Iterable[str] = (),
    readiness_blockers: Mapping[str, Iterable[str]] | None = None,
) -> MissionExecutionMemoryShadowReceipt:
    """Compile existing CFBE/Bubbles shadow execution and emit BMF memory events.

    This wrapper does not persist anything. The caller decides whether an admitted
    shadow provider adapter should store the returned events. Existing execution
    semantics and authority boundaries remain owned by shadow_compile_mission_execution.
    """

    normalized = mission.normalized()
    normalized.validate()
    if stream_start_version < 1:
        raise ValueError("BMF_EXECUTION_BINDING_STREAM_VERSION_INVALID")
    sources = tuple(sorted({str(item).strip() for item in source_refs if str(item).strip()}))
    if not sources:
        raise ValueError("BMF_EXECUTION_BINDING_SOURCE_REF_REQUIRED")

    execution = shadow_compile_mission_execution(
        normalized,
        nodes,
        cells,
        cell_provider_aliases=cell_provider_aliases,
        shard_width=shard_width,
        active_ids=active_ids,
        completed_ids=completed_ids,
        critical_regression_ids=critical_regression_ids,
        live_ready_ids=live_ready_ids,
        readiness_blockers=readiness_blockers,
    )

    compiled = BibleMemoryCaptureAdapter.capture_mission_compiled(
        normalized,
        stream_version=stream_start_version,
        recorded_at=observed_at,
        source_refs=sources,
    )

    shadow_ref = f"shadow://mission-execution/{execution.execution_digest}"
    result_sources = tuple(sorted(set(sources).union({shadow_ref})))
    if execution.cell_shadow_state == "SHADOW_READY":
        result = MissionResultCapture(
            state="IN_PROGRESS",
            observed_at=observed_at,
            source_refs=result_sources,
            result_ref=shadow_ref,
            result_sha256=execution.execution_digest,
            next_action="execute_selected_shadow_work",
            metadata={
                "cell_shadow_state": execution.cell_shadow_state,
                "selected_work_ids": ",".join(execution.selected_work_ids),
                "cell_placement_digest": execution.cell_placement_digest,
            },
        )
    else:
        result = MissionResultCapture(
            state="BLOCKED",
            observed_at=observed_at,
            source_refs=result_sources,
            result_ref=shadow_ref,
            result_sha256=execution.execution_digest,
            blocker_code=execution.cell_shadow_state,
            next_action="resolve_shadow_execution_hold",
            metadata={
                "cell_shadow_state": execution.cell_shadow_state,
                "selected_work_ids": ",".join(execution.selected_work_ids),
                "provider_policy_excluded_cell_ids": ",".join(execution.provider_policy_excluded_cell_ids),
                "provider_policy_unmapped_cell_ids": ",".join(execution.provider_policy_unmapped_cell_ids),
            },
        )

    observed = BibleMemoryCaptureAdapter.capture_result(
        normalized,
        result,
        stream_version=stream_start_version + 1,
    )
    return MissionExecutionMemoryShadowReceipt(
        schema="CFBE-MISSION-EXECUTION-BMF-SHADOW-BINDING-V1",
        execution=execution,
        memory_events=(compiled, observed),
    )


__all__ = ["MissionExecutionMemoryShadowReceipt", "shadow_compile_mission_execution_with_memory"]
