from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class WorkLaneState(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True)
class WorkLane:
    lane_id: str
    state: WorkLaneState
    blocker_scope: str | None = None
    dependencies: tuple[str, ...] = ()


def executable_lanes(lanes: Sequence[WorkLane]) -> tuple[str, ...]:
    ids = {lane.lane_id for lane in lanes}
    result = []
    state_by_id = {lane.lane_id: lane.state for lane in lanes}
    for lane in lanes:
        unknown = set(lane.dependencies) - ids
        if unknown:
            raise ValueError(f"unknown dependencies: {sorted(unknown)}")
        if lane.state != WorkLaneState.READY:
            continue
        if any(state_by_id[dependency] != WorkLaneState.COMPLETE for dependency in lane.dependencies):
            continue
        result.append(lane.lane_id)
    return tuple(sorted(result))
