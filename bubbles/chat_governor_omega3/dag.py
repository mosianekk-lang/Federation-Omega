from __future__ import annotations

import hashlib
import json
from concurrent.futures import Future, ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Sequence, Set

from .state import DurableState


class LaneState(str, Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class Lane:
    lane_id: str
    action: str
    dependencies: List[str] = field(default_factory=list)
    connector: str = ""
    target: str = ""
    proof_gap: str = ""
    source_version: str = ""
    state: LaneState = LaneState.READY
    result: Any = None
    error: str = ""


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


class DAGExecutor:
    """Bounded concurrency with failed-lane isolation.

    A failed dependency blocks only its descendants. Independent lanes continue.
    """

    def __init__(self, state: DurableState, max_workers: int = 4) -> None:
        self.state = state
        self.max_workers = max_workers

    def run(
        self,
        mission_id: str,
        lanes: Sequence[Lane],
        handlers: Dict[str, Callable[[Lane], Any]],
    ) -> Dict[str, Any]:
        lane_map = {lane.lane_id: lane for lane in lanes}
        for lane in lanes:
            missing = [dep for dep in lane.dependencies if dep not in lane_map]
            if missing:
                raise ValueError(f"Lane {lane.lane_id} has unknown dependencies: {missing}")

        pending: Set[str] = set(lane_map)
        running: Dict[Future, str] = {}

        def deps_complete(lane: Lane) -> bool:
            return all(lane_map[d].state == LaneState.COMPLETE for d in lane.dependencies)

        def deps_failed(lane: Lane) -> bool:
            return any(
                lane_map[d].state in {LaneState.FAILED, LaneState.BLOCKED, LaneState.SKIPPED}
                for d in lane.dependencies
            )

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            while pending or running:
                made_progress = False

                for lane_id in list(pending):
                    lane = lane_map[lane_id]
                    if deps_failed(lane):
                        lane.state = LaneState.BLOCKED
                        lane.error = "Dependency did not complete"
                        pending.remove(lane_id)
                        self.state.checkpoint(
                            mission_id,
                            {"lane_id": lane_id, "state": lane.state.value, "error": lane.error},
                            proof_bearing=False,
                        )
                        made_progress = True
                        continue

                    if deps_complete(lane) and len(running) < self.max_workers:
                        handler = handlers.get(lane_id)
                        if handler is None:
                            lane.state = LaneState.FAILED
                            lane.error = "No handler registered"
                            pending.remove(lane_id)
                            self.state.checkpoint(
                                mission_id,
                                {"lane_id": lane_id, "state": lane.state.value, "error": lane.error},
                                proof_bearing=False,
                            )
                            made_progress = True
                            continue
                        lane.state = LaneState.RUNNING
                        running[pool.submit(handler, lane)] = lane_id
                        pending.remove(lane_id)
                        made_progress = True

                if running:
                    completed, _ = wait(list(running), timeout=0.05, return_when=FIRST_COMPLETED)
                    for future in completed:
                        lane_id = running.pop(future)
                        lane = lane_map[lane_id]
                        try:
                            lane.result = future.result()
                            lane.state = LaneState.COMPLETE
                            self.state.checkpoint(
                                mission_id,
                                {
                                    "lane_id": lane_id,
                                    "state": lane.state.value,
                                    "result_sha256": _sha(lane.result),
                                },
                                proof_bearing=True,
                            )
                        except Exception as exc:
                            lane.state = LaneState.FAILED
                            lane.error = f"{type(exc).__name__}: {exc}"
                            self.state.checkpoint(
                                mission_id,
                                {"lane_id": lane_id, "state": lane.state.value, "error": lane.error},
                                proof_bearing=False,
                            )
                        made_progress = True

                if not made_progress and pending and not running:
                    # dependency cycle or otherwise unsatisfied graph; terminate safely
                    for lane_id in list(pending):
                        lane = lane_map[lane_id]
                        lane.state = LaneState.BLOCKED
                        lane.error = "Dependency cycle or unsatisfied dependency"
                        pending.remove(lane_id)
                        self.state.checkpoint(
                            mission_id,
                            {"lane_id": lane_id, "state": lane.state.value, "error": lane.error},
                            proof_bearing=False,
                        )

        compact = {
            lane_id: {
                "state": lane.state.value,
                "error": lane.error,
                "dependencies": lane.dependencies,
                "result": lane.result,
            }
            for lane_id, lane in lane_map.items()
        }
        return {
            "mission_id": mission_id,
            "lanes": compact,
            "receipt_sha256": _sha(compact),
        }
