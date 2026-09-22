from __future__ import annotations

from typing import Iterable

from .progressive_models import (
    EffectClass,
    ProgressivePlan,
    StreamUnit,
    UnitState,
    WaveDecision,
    _SAFE_EFFECTS,
    _stable_id,
)


class MultiStreamScheduler:
    """Dependency-, collision-, authority- and circuit-aware wave scheduler."""

    def __init__(self, max_parallel_safe: int = 8, failure_threshold: int = 2) -> None:
        if max_parallel_safe < 1:
            raise ValueError("max_parallel_safe must be >= 1")
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        self.max_parallel_safe = max_parallel_safe
        self.failure_threshold = failure_threshold
        self._failure_counts: dict[str, int] = {}

    @staticmethod
    def _dependency_state(
        plan: ProgressivePlan,
        unit: StreamUnit,
    ) -> tuple[bool, bool]:
        dependencies = [plan.units[dep].state for dep in unit.dependencies]
        failed = any(
            state in {UnitState.FAILED, UnitState.BLOCKED, UnitState.CIRCUIT_OPEN}
            for state in dependencies
        )
        complete = all(
            state in {UnitState.SUCCEEDED, UnitState.SKIPPED}
            for state in dependencies
        )
        return complete, failed

    def next_wave(
        self,
        plan: ProgressivePlan,
        *,
        allow_provider_effects: bool = False,
        authorised_effect_classes: Iterable[EffectClass] = (),
    ) -> WaveDecision:
        authorised = set(authorised_effect_classes)

        # Compute fail/hold closure without mutating the plan. This makes every
        # downstream dependency disposition explicit instead of leaving hidden
        # PENDING chains behind an authority or failure gate.
        blocked_set: set[str] = set()
        held_set: set[str] = {
            unit.unit_id
            for unit in plan.units.values()
            if unit.state is UnitState.PENDING
            and unit.effect_class not in _SAFE_EFFECTS
            and (
                not allow_provider_effects
                or unit.effect_class not in authorised
            )
        }
        changed = True
        while changed:
            changed = False
            for unit in plan.units.values():
                if unit.state is not UnitState.PENDING:
                    continue
                dependency_states = [
                    plan.units[dep].state for dep in unit.dependencies
                ]
                if any(
                    state
                    in {
                        UnitState.FAILED,
                        UnitState.BLOCKED,
                        UnitState.CIRCUIT_OPEN,
                    }
                    for state in dependency_states
                ) or any(dep in blocked_set for dep in unit.dependencies):
                    if unit.unit_id not in blocked_set:
                        blocked_set.add(unit.unit_id)
                        held_set.discard(unit.unit_id)
                        changed = True
                    continue
                if any(
                    state is UnitState.HELD for state in dependency_states
                ) or any(dep in held_set for dep in unit.dependencies):
                    if (
                        unit.unit_id not in held_set
                        and unit.unit_id not in blocked_set
                    ):
                        held_set.add(unit.unit_id)
                        changed = True

        ready: list[StreamUnit] = []
        for unit in plan.units.values():
            if unit.state is not UnitState.PENDING:
                continue
            if unit.unit_id in blocked_set or unit.unit_id in held_set:
                continue
            dependencies_complete, dependency_failed = self._dependency_state(
                plan,
                unit,
            )
            if dependency_failed:
                blocked_set.add(unit.unit_id)
                continue
            if not dependencies_complete:
                continue
            ready.append(unit)

        # Downstream fan-out approximates criticality while stable ids make the
        # decision deterministic. It is not a duration claim.
        downstream_count: dict[str, int] = {
            unit_id: 0 for unit_id in plan.units
        }
        for unit in plan.units.values():
            for dependency in unit.dependencies:
                downstream_count[dependency] += 1
        ready.sort(
            key=lambda unit: (
                -unit.priority,
                -downstream_count[unit.unit_id],
                -unit.information_gain,
                unit.stream_id,
                unit.unit_id,
            )
        )

        selected: list[str] = []
        used_collision_keys: set[str] = set()
        effectful_selected = False
        stream_counts: dict[str, int] = {}

        # First pass enforces fair stream diversity.
        for unit in ready:
            if len(selected) >= self.max_parallel_safe:
                break
            if stream_counts.get(unit.stream_id, 0) >= 1:
                continue
            if set(unit.collision_keys) & used_collision_keys:
                continue
            if unit.effect_class not in _SAFE_EFFECTS:
                if effectful_selected:
                    continue
                effectful_selected = True
            selected.append(unit.unit_id)
            used_collision_keys.update(unit.collision_keys)
            stream_counts[unit.stream_id] = 1

        # Second pass fills remaining capacity without violating collisions or
        # the one-effect-lane invariant.
        for unit in ready:
            if len(selected) >= self.max_parallel_safe:
                break
            if unit.unit_id in selected:
                continue
            if set(unit.collision_keys) & used_collision_keys:
                continue
            if unit.effect_class not in _SAFE_EFFECTS:
                if effectful_selected:
                    continue
                effectful_selected = True
            selected.append(unit.unit_id)
            used_collision_keys.update(unit.collision_keys)

        held = tuple(sorted(held_set))
        blocked = tuple(sorted(blocked_set))
        wave_id = _stable_id(
            "WAVE",
            plan.mission_id,
            *selected,
            *held,
            *blocked,
        )
        reason = (
            "RUNNABLE_SAFE_PARALLEL_WAVE"
            if selected
            else "NO_SAFE_RUNNABLE_UNIT"
        )
        return WaveDecision(
            wave_id=wave_id,
            runnable=tuple(selected),
            held=held,
            blocked=blocked,
            reason=reason,
        )

    def register_failure(self, fingerprint: str) -> bool:
        normalised = fingerprint.strip()
        if not normalised:
            raise ValueError("failure fingerprint is required")
        self._failure_counts[normalised] = (
            self._failure_counts.get(normalised, 0) + 1
        )
        return self._failure_counts[normalised] >= self.failure_threshold
