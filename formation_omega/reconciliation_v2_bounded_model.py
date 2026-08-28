"""Bounded exhaustive safety oracle for Formation Ω Reconciliation Fabric v2.

This is not a substitute for TLC/Apalache. It is a deterministic CI oracle that
mirrors the small constitutional admission state machine and exhaustively explores
its reachable bounded states. It creates no provider effect.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from typing import Iterable


@dataclass(frozen=True)
class AdmissionModelState:
    main: str = "MAIN_A"
    head: str = "HEAD_A"
    checked_head: str = "HEAD_A"
    permit_main: str = "MAIN_A"
    permit_head: str = "HEAD_A"
    semantic_conflict: bool = False
    rollback_available: bool = True
    external_effect: bool = False
    authority: str = "A1_INTERNAL"
    merged: bool = False
    closed: bool = False


@dataclass(frozen=True)
class ModelCheckResult:
    reachable_state_count: int
    transition_count: int
    violations: tuple[str, ...]

    @property
    def safe(self) -> bool:
        return not self.violations


def invariants(state: AdmissionModelState) -> tuple[str, ...]:
    violations: list[str] = []
    if state.semantic_conflict and state.merged:
        violations.append("NO_MERGE_ON_SEMANTIC_CONFLICT")
    if state.merged and not (
        state.main == state.permit_main
        and state.head == state.permit_head
        and state.checked_head == state.head
    ):
        violations.append("NO_STALE_PERMIT_MERGE")
    if state.authority == "A1_INTERNAL" and state.external_effect and state.merged:
        violations.append("NO_A1_EXTERNAL_EFFECT_AT_MERGE")
    if state.merged and not state.rollback_available:
        violations.append("ROLLBACK_REQUIRED_FOR_MERGE")
    if state.closed and not state.merged:
        violations.append("CLOSURE_REQUIRES_MERGE")
    if state.closed and not state.rollback_available:
        violations.append("CLOSURE_REQUIRES_ROLLBACK")
    if state.closed and state.semantic_conflict:
        violations.append("CLOSURE_EXCLUDES_CONFLICT")
    return tuple(violations)


def next_states(state: AdmissionModelState) -> Iterable[tuple[str, AdmissionModelState]]:
    if state.merged:
        if not state.closed and state.rollback_available and not state.semantic_conflict:
            yield "CLOSE", replace(state, closed=True)
        return

    next_main = "MAIN_B" if state.main == "MAIN_A" else "MAIN_A"
    next_head = "HEAD_B" if state.head == "HEAD_A" else "HEAD_A"
    yield "REFRESH_MAIN", replace(state, main=next_main)
    yield "MOVE_HEAD", replace(state, head=next_head)
    yield "RECHECK", replace(
        state,
        checked_head=state.head,
        permit_main=state.main,
        permit_head=state.head,
    )
    if not state.semantic_conflict:
        yield "SET_CONFLICT", replace(state, semantic_conflict=True)
    if state.rollback_available:
        yield "LOSE_ROLLBACK", replace(state, rollback_available=False)
    if not state.external_effect:
        yield "ATTEMPT_EXTERNAL_EFFECT", replace(state, external_effect=True)

    merge_allowed = all(
        (
            not state.semantic_conflict,
            state.rollback_available,
            state.main == state.permit_main,
            state.head == state.permit_head,
            state.checked_head == state.head,
            not state.external_effect,
        )
    )
    if merge_allowed:
        yield "MERGE", replace(state, merged=True)


def exhaustive_check(initial: AdmissionModelState | None = None) -> ModelCheckResult:
    start = initial or AdmissionModelState()
    queue = deque([start])
    seen = {start}
    violations: set[str] = set(invariants(start))
    transitions = 0

    while queue:
        state = queue.popleft()
        for action, candidate in next_states(state):
            transitions += 1
            for violation in invariants(candidate):
                violations.add(f"{violation}@{action}:{candidate}")
            if candidate not in seen:
                seen.add(candidate)
                queue.append(candidate)

    return ModelCheckResult(
        reachable_state_count=len(seen),
        transition_count=transitions,
        violations=tuple(sorted(violations)),
    )


__all__ = [
    "AdmissionModelState",
    "ModelCheckResult",
    "exhaustive_check",
    "invariants",
    "next_states",
]
