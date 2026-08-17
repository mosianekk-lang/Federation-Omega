from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Callable, Mapping


MAX_DIRECTIVE_SECONDS = 20 * 60
SPLIT_TRIGGER_SECONDS = 12 * 60
EXPANSION_CUTOFF_SECONDS = 15 * 60
FORCE_RELEASE_SECONDS = 18 * 60
MAX_ACTIVE_PATHS = 3
MAX_ACTIVE_STREAMS = 6


class TimeboxState(str, Enum):
    GREEN = "GREEN"
    SPLIT_REQUIRED = "SPLIT_REQUIRED"
    CONVERGENCE_ONLY = "CONVERGENCE_ONLY"
    RELEASE_ONLY = "RELEASE_ONLY"
    DEADLINE_REACHED = "DEADLINE_REACHED"


@dataclass(frozen=True)
class PhaseBudget:
    id: str
    max_seconds: int
    terminal_fruit: str


@dataclass(frozen=True)
class ExecutionPath:
    id: str
    path_class: str
    objective: str
    streams: tuple[str, ...]
    exit_condition: str


@dataclass(frozen=True)
class ExecutionPolicy:
    id: str
    max_directive_seconds: int
    split_trigger_seconds: int
    expansion_cutoff_seconds: int
    force_release_seconds: int
    max_active_paths: int
    max_active_streams: int
    completion_states: tuple[str, ...]
    quality_gates: tuple[str, ...]
    guarantee_scope: str
    external_limit: str


class TwentyMinuteGovernor:
    """Alpha–Omega execution governor for bounded, proof-bearing delivery.

    It cannot make an external provider respond faster. It does guarantee that a
    single JARVIS execution attempt stops expanding, converges and emits an
    honest terminal receipt inside the configured envelope.
    """

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self.policy = ExecutionPolicy(
            id="T20-AO-OMEGA-SCIENTIST-1.0",
            max_directive_seconds=MAX_DIRECTIVE_SECONDS,
            split_trigger_seconds=SPLIT_TRIGGER_SECONDS,
            expansion_cutoff_seconds=EXPANSION_CUTOFF_SECONDS,
            force_release_seconds=FORCE_RELEASE_SECONDS,
            max_active_paths=MAX_ACTIVE_PATHS,
            max_active_streams=MAX_ACTIVE_STREAMS,
            completion_states=(
                "COMPLETE_VERIFIED",
                "BOUNDED_COMPLETE",
                "BLOCKED_WITH_EXECUTABLE_NEXT_ROUTE",
            ),
            quality_gates=(
                "SOURCE_FIDELITY",
                "IMPLEMENTATION_OR_RESULT",
                "TEST_OR_VALIDATION",
                "ADVERSARIAL_CHECK",
                "SEMANTIC_READBACK",
                "TRUTHFUL_COMPLETION_CLAIM",
            ),
            guarantee_scope="ONE_BOUNDED_JARVIS_EXECUTION_ATTEMPT",
            external_limit="EXTERNAL_PROVIDER_LATENCY_OR_APPROVAL_CANNOT_BE_FORCED; BLOCKERS_MUST_BE_BOUNDED_AND_RELEASED_HONESTLY",
        )

    def describe(self) -> dict[str, Any]:
        return asdict(self.policy)

    def build_plan(self, mission_id: str, objective: str) -> dict[str, Any]:
        objective = objective.strip()
        if not mission_id.strip():
            raise ValueError("MISSION_REQUIRED")
        if not objective:
            raise ValueError("OBJECTIVE_REQUIRED")

        started_at = self._clock()
        phases = (
            PhaseBudget("PREFLIGHT", 120, "bounded objective, dependencies and proof target"),
            PhaseBudget("PARALLEL_EXECUTION", 600, "minimum sufficient implementation or answer"),
            PhaseBudget("FAN_IN_AND_ASSURANCE", 300, "integrated tests, countercase and semantic QA"),
            PhaseBudget("READBACK_AND_RELEASE", 180, "terminal receipt and next route"),
        )
        if sum(p.max_seconds for p in phases) != self.policy.max_directive_seconds:
            raise RuntimeError("INVALID_PHASE_BUDGET")

        streams = (
            "ST_SOURCE_TRUTH",
            "ST_IMPLEMENTATION",
            "ST_TEST_VALIDATION",
            "ST_ADVERSARIAL_RISK",
            "ST_SEMANTIC_READBACK",
            "ST_METHOD_LEARNING",
        )
        paths = (
            ExecutionPath(
                "PATH_PRIMARY",
                "PRIMARY",
                "Reach the requested Omega through the shortest verified route.",
                ("ST_SOURCE_TRUTH", "ST_IMPLEMENTATION", "ST_TEST_VALIDATION"),
                "Requested result exists and its decisive claims are verified.",
            ),
            ExecutionPath(
                "PATH_PROTECTIVE",
                "PROTECTIVE",
                "Preserve quality, authority, reversibility and continuity.",
                ("ST_ADVERSARIAL_RISK", "ST_SEMANTIC_READBACK"),
                "Material risks are repaired, bounded or disclosed.",
            ),
            ExecutionPath(
                "PATH_FALLBACK",
                "FAILURE_RECOVERY",
                "Isolate a blocker and deliver the highest-value bounded result without freezing independent work.",
                ("ST_IMPLEMENTATION", "ST_SEMANTIC_READBACK", "ST_METHOD_LEARNING"),
                "A usable bounded result and executable next route are released.",
            ),
        )
        return {
            "missionId": mission_id,
            "objective": objective,
            "alpha": {
                "startingState": "LIVE_REQUEST_AND_CURRENT_VERIFIED_SOURCES",
                "assumptionPolicy": "NOTHING_MATERIAL_ASSUMED",
            },
            "omega": {
                "primary": "REQUESTED_RESULT_COMPLETE_AND_VERIFIED",
                "protective": "QUALITY_AND_AUTHORITY_PRESERVED",
                "fallback": "BOUNDED_RESULT_PLUS_EXECUTABLE_NEXT_ROUTE",
            },
            "startedAt": started_at,
            "deadlineAt": started_at + self.policy.max_directive_seconds,
            "phases": [asdict(p) for p in phases],
            "paths": [asdict(p) for p in paths],
            "streams": list(streams),
            "controls": {
                "fanOut": "ONLY_INDEPENDENT_WORK",
                "fanIn": "MANDATORY_BEFORE_COMPLETION_CLAIM",
                "splitAtSeconds": self.policy.split_trigger_seconds,
                "stopExpansionAtSeconds": self.policy.expansion_cutoff_seconds,
                "forceReleaseAtSeconds": self.policy.force_release_seconds,
                "deadlineAction": "EMIT_TERMINAL_RECEIPT; NEVER_REPORT_FALSE_COMPLETION",
            },
            "qualityGates": list(self.policy.quality_gates),
            "allowedCompletionStates": list(self.policy.completion_states),
        }

    def control_state(self, started_at: float, now: float | None = None) -> dict[str, Any]:
        current = self._clock() if now is None else now
        elapsed = max(0, int(current - started_at))
        if elapsed >= self.policy.max_directive_seconds:
            state = TimeboxState.DEADLINE_REACHED
            action = "TERMINATE_ATTEMPT_AND_EMIT_HONEST_TERMINAL_RECEIPT"
        elif elapsed >= self.policy.force_release_seconds:
            state = TimeboxState.RELEASE_ONLY
            action = "NO_NEW_WORK; VERIFY_READBACK_AND_RELEASE"
        elif elapsed >= self.policy.expansion_cutoff_seconds:
            state = TimeboxState.CONVERGENCE_ONLY
            action = "STOP_SCOPE_EXPANSION; FAN_IN_AND_REPAIR"
        elif elapsed >= self.policy.split_trigger_seconds:
            state = TimeboxState.SPLIT_REQUIRED
            action = "SPLIT_MONOLITH; CONTINUE_ONLY_INDEPENDENT_HIGH_VALUE_LANES"
        else:
            state = TimeboxState.GREEN
            action = "EXECUTE_HIGHEST_INFORMATION_AND_DECISION_VALUE_LANES"
        return {
            "state": state.value,
            "elapsedSeconds": elapsed,
            "remainingSeconds": max(0, self.policy.max_directive_seconds - elapsed),
            "requiredAction": action,
        }

    def review_cycle(
        self,
        elapsed_seconds: int,
        quality_gates: Mapping[str, bool],
        retries: int = 0,
    ) -> dict[str, Any]:
        if elapsed_seconds < 0:
            raise ValueError("ELAPSED_SECONDS_INVALID")
        missing = [gate for gate in self.policy.quality_gates if gate not in quality_gates]
        if missing:
            raise ValueError("MISSING_QUALITY_GATES:" + ",".join(missing))

        failed = [gate for gate in self.policy.quality_gates if not quality_gates[gate]]
        deadline_pass = elapsed_seconds <= self.policy.max_directive_seconds
        quality_pass = not failed
        cycle_pass = deadline_pass and quality_pass

        if cycle_pass:
            candidate = max(300, int(elapsed_seconds * 0.95))
            promotion = "SHADOW_CANDIDATE"
            repair = "NONE"
        elif not quality_pass:
            candidate = self.policy.max_directive_seconds
            promotion = "REJECTED"
            repair = "REPAIR_FAILED_QUALITY_GATES_BEFORE_SPEED_OPTIMISATION"
        else:
            candidate = self.policy.max_directive_seconds
            promotion = "REJECTED"
            repair = "DECOMPOSE_EARLIER_AND_REDUCE_ACTIVE_DEPENDENCIES"

        return {
            "cyclePass": cycle_pass,
            "deadlinePass": deadline_pass,
            "qualityPass": quality_pass,
            "failedQualityGates": failed,
            "retries": max(0, retries),
            "omegaScientist": {
                "promotionState": promotion,
                "candidateNextTargetSeconds": candidate,
                "rule": "PROMOTE_SPEED_GAIN_ONLY_AFTER_REGRESSION_WITH_NO_QUALITY_LOSS",
                "repair": repair,
            },
        }
