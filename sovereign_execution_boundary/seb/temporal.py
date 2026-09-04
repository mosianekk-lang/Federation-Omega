"""Temporal-owned durable execution for SEB missions.

The workflow contains only deterministic coordination. Policy/provider/ledger I/O is
kept in an activity and therefore is never re-executed while Workflow History is
replayed by Temporal.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any, Callable

try:
    from temporalio import activity, workflow
    from temporalio.common import RetryPolicy
except ImportError as exc:  # keep the local-only SEB install usable
    raise ImportError("Temporal support requires: pip install '.[temporal]'") from exc

with workflow.unsafe.imports_passed_through():
    from .engine import SovereignEngine
    from .models import Budget, MissionIR


@dataclass(frozen=True)
class TemporalMissionInput:
    mission: dict[str, Any]
    prompt: str
    schema: dict[str, Any]
    objective_fingerprint: str

    @classmethod
    def from_mission(cls, mission: MissionIR, prompt: str, schema: dict[str, Any]) -> "TemporalMissionInput":
        return cls(asdict(mission), prompt, schema, mission.fingerprint)


def _mission_from_payload(payload: dict[str, Any]) -> MissionIR:
    value = dict(payload)
    value["requirements"] = tuple(value["requirements"])
    value["acceptance_tests"] = tuple(value["acceptance_tests"])
    value["prohibited_effects"] = tuple(value.get("prohibited_effects", ()))
    value["allowed_tools"] = tuple(value.get("allowed_tools", ()))
    value["budget"] = Budget(**value.get("budget", {}))
    return MissionIR(**value)


@workflow.defn(name="seb-mission-v1")
class SebMissionWorkflow:
    @workflow.run
    async def run(self, request: TemporalMissionInput) -> dict[str, Any]:
        # This comparison is deterministic and becomes part of Workflow History.
        # The activity repeats it before any I/O, closing payload substitution.
        result = await workflow.execute_activity(
            "seb-execute-mission-v1",
            request,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(milliseconds=100),
                maximum_interval=timedelta(seconds=10),
                maximum_attempts=5,
            ),
        )
        return result


class SebTemporalActivities:
    """Dependency-injected activity implementation suitable for a Worker."""

    def __init__(self, engine: SovereignEngine, verifier: Callable[[dict[str, Any]], bool],
                 before_execute: Callable[[], None] | None = None):
        self.engine = engine
        self.verifier = verifier
        self.before_execute = before_execute

    @activity.defn(name="seb-execute-mission-v1")
    async def execute_mission(self, request: TemporalMissionInput) -> dict[str, Any]:
        if self.before_execute is not None:
            self.before_execute()
        mission = _mission_from_payload(request.mission)
        if mission.fingerprint != request.objective_fingerprint:
            # Non-retryable: altered mission data must not reach policy or provider I/O.
            from temporalio.exceptions import ApplicationError
            raise ApplicationError("objective fingerprint mismatch", non_retryable=True)
        result = self.engine.execute(mission, request.prompt, request.schema, self.verifier)
        value = asdict(result)
        value["state"] = result.state.value
        value["failure_class"] = result.failure_class.value if result.failure_class else None
        return value
