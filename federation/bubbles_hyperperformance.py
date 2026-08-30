from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence


class ContextPressureError(RuntimeError):
    """Raised when a workload exceeds the bounded interactive-context envelope."""


@dataclass(frozen=True)
class ContextPressureBudget:
    max_active_sources: int = 8
    max_heavy_sources: int = 3
    max_tool_results: int = 20
    max_tool_payload_chars: int = 120_000
    max_capsule_chars: int = 24_000


@dataclass(frozen=True)
class ContextPressureObservation:
    active_sources: int
    heavy_sources: int
    tool_results: int
    tool_payload_chars: int
    estimated_capsule_chars: int


@dataclass(frozen=True)
class ContextPressureDecision:
    admitted: bool
    action: str
    reasons: tuple[str, ...] = ()


class ContextPressureGovernor:
    """Fail-small admission controller for interactive Bubbles workloads.

    The governor does not discard canonical state. It decides whether the active
    chat should continue hydrating material or checkpoint/compact first.
    """

    def __init__(self, budget: ContextPressureBudget | None = None) -> None:
        self.budget = budget or ContextPressureBudget()

    def evaluate(self, obs: ContextPressureObservation) -> ContextPressureDecision:
        reasons: list[str] = []
        if obs.active_sources > self.budget.max_active_sources:
            reasons.append("ACTIVE_SOURCE_BUDGET")
        if obs.heavy_sources > self.budget.max_heavy_sources:
            reasons.append("HEAVY_SOURCE_BUDGET")
        if obs.tool_results > self.budget.max_tool_results:
            reasons.append("TOOL_RESULT_BUDGET")
        if obs.tool_payload_chars > self.budget.max_tool_payload_chars:
            reasons.append("TOOL_PAYLOAD_BUDGET")
        if obs.estimated_capsule_chars > self.budget.max_capsule_chars:
            reasons.append("CAPSULE_SIZE_BUDGET")
        if reasons:
            return ContextPressureDecision(False, "CHECKPOINT_COMPACT_REROUTE", tuple(reasons))
        return ContextPressureDecision(True, "CONTINUE", ())

    def require_admission(self, obs: ContextPressureObservation) -> None:
        decision = self.evaluate(obs)
        if not decision.admitted:
            raise ContextPressureError(";".join(decision.reasons))


_REQUIRED_CAPSULE_FIELDS = (
    "mission_id",
    "objective",
    "verified_state",
    "source_frontier",
    "authorities",
    "active_capabilities",
    "artifacts",
    "blockers",
    "next_action",
    "proof_refs",
    "freshness",
)


@dataclass(frozen=True)
class MissionCapsule:
    mission_id: str
    objective: str
    verified_state: str
    source_frontier: str
    authorities: tuple[str, ...] = ()
    active_capabilities: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    next_action: str = ""
    proof_refs: tuple[str, ...] = ()
    freshness: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    def as_mapping(self) -> dict[str, object]:
        return {
            "mission_id": self.mission_id,
            "objective": self.objective,
            "verified_state": self.verified_state,
            "source_frontier": self.source_frontier,
            "authorities": list(self.authorities),
            "active_capabilities": list(self.active_capabilities),
            "artifacts": list(self.artifacts),
            "blockers": list(self.blockers),
            "next_action": self.next_action,
            "proof_refs": list(self.proof_refs),
            "freshness": self.freshness,
            "metadata": dict(self.metadata),
        }


class MissionCapsuleCompiler:
    """Compile a bounded working projection from canonical mission state."""

    def __init__(self, max_items_per_list: int = 12, max_text_chars: int = 4_000) -> None:
        self.max_items_per_list = max_items_per_list
        self.max_text_chars = max_text_chars

    def _text(self, value: object) -> str:
        return str(value or "")[: self.max_text_chars]

    def _items(self, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            values: Iterable[object] = (value,)
        else:
            values = value if isinstance(value, Iterable) else (value,)
        return tuple(self._text(item) for item in list(values)[: self.max_items_per_list])

    def compile(self, state: Mapping[str, object]) -> MissionCapsule:
        missing = [name for name in _REQUIRED_CAPSULE_FIELDS if name not in state]
        if missing:
            raise ValueError(f"MISSION_CAPSULE_MISSING_FIELDS:{','.join(missing)}")
        return MissionCapsule(
            mission_id=self._text(state["mission_id"]),
            objective=self._text(state["objective"]),
            verified_state=self._text(state["verified_state"]),
            source_frontier=self._text(state["source_frontier"]),
            authorities=self._items(state["authorities"]),
            active_capabilities=self._items(state["active_capabilities"]),
            artifacts=self._items(state["artifacts"]),
            blockers=self._items(state["blockers"]),
            next_action=self._text(state["next_action"]),
            proof_refs=self._items(state["proof_refs"]),
            freshness=self._text(state["freshness"]),
            metadata={str(k): self._text(v) for k, v in dict(state.get("metadata") or {}).items()},
        )


def bounded_slice(items: Sequence[str], limit: int) -> tuple[str, ...]:
    if limit < 0:
        raise ValueError("limit must be non-negative")
    return tuple(items[:limit])
