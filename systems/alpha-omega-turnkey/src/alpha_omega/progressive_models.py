from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any


class PathKind(StrEnum):
    REUSE_OPTIMISE = "REUSE_OPTIMISE"
    COMPOSE_EXTEND = "COMPOSE_EXTEND"
    MATERIAL_NEW = "MATERIAL_NEW"
    REVERSIBLE_EXPERIMENT = "REVERSIBLE_EXPERIMENT"


class EffectClass(StrEnum):
    INTERNAL = "INTERNAL"
    READ_ONLY = "READ_ONLY"
    PRIVATE_REVERSIBLE = "PRIVATE_REVERSIBLE"
    PROVIDER_EFFECT = "PROVIDER_EFFECT"
    CONSEQUENTIAL = "CONSEQUENTIAL"


class UnitState(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    HELD = "HELD"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    SKIPPED = "SKIPPED"


_TERMINAL_STATES = {
    UnitState.SUCCEEDED,
    UnitState.FAILED,
    UnitState.BLOCKED,
    UnitState.HELD,
    UnitState.CIRCUIT_OPEN,
    UnitState.SKIPPED,
}
_SAFE_EFFECTS = {
    EffectClass.INTERNAL,
    EffectClass.READ_ONLY,
    EffectClass.PRIVATE_REVERSIBLE,
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _stable_id(prefix: str, *parts: str) -> str:
    canonical = "|".join(" ".join(str(part).strip().split()).lower() for part in parts)
    return f"{prefix}-{sha256(canonical.encode('utf-8')).hexdigest()[:14].upper()}"


def _slug(value: str) -> str:
    collapsed = "-".join(value.lower().split())
    return "".join(ch for ch in collapsed if ch.isalnum() or ch == "-")[:48] or "work"


@dataclass(frozen=True)
class RouteCandidate:
    path_id: str
    kind: PathKind
    title: str
    rationale: str
    reuse_refs: tuple[str, ...]
    assumptions: tuple[str, ...]
    mission_fidelity: float
    proof_strength: float
    reversibility: float
    information_gain: float
    speed: float
    cost_efficiency: float
    owner_burden: float
    risk: float
    eligible: bool = True
    rejection_reasons: tuple[str, ...] = ()

    @property
    def score(self) -> float:
        # Higher is better. Proof, mission fidelity and reversibility dominate.
        positive = (
            0.24 * self.mission_fidelity
            + 0.20 * self.proof_strength
            + 0.16 * self.reversibility
            + 0.12 * self.information_gain
            + 0.12 * self.speed
            + 0.08 * self.cost_efficiency
            + 0.08 * (1.0 - self.owner_burden)
        )
        return round(positive - 0.15 * self.risk, 6)


@dataclass
class StreamUnit:
    unit_id: str
    stream_id: str
    path_id: str
    stage: str
    objective: str
    dependencies: tuple[str, ...] = ()
    collision_keys: tuple[str, ...] = ()
    effect_class: EffectClass = EffectClass.INTERNAL
    authority_required: str = "A1_INTERNAL"
    proof_gate: str = "INTERNAL_READBACK"
    priority: int = 50
    information_gain: float = 0.5
    reusable_key: str | None = None
    state: UnitState = UnitState.PENDING
    attempts: int = 0
    output_refs: tuple[str, ...] = ()
    proof_refs: tuple[str, ...] = ()
    failure_fingerprint: str | None = None
    duration_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["effect_class"] = self.effect_class.value
        data["state"] = self.state.value
        return data


@dataclass
class ProgressivePlan:
    mission_id: str
    cycle_id: str
    objective: str
    selected_path_id: str
    routes: tuple[RouteCandidate, ...]
    units: dict[str, StreamUnit]
    truth_boundary: dict[str, Any]
    created_from: dict[str, Any] = field(default_factory=dict)

    def unit(self, unit_id: str) -> StreamUnit:
        return self.units[unit_id]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "cycle_id": self.cycle_id,
            "objective": self.objective,
            "selected_path_id": self.selected_path_id,
            "routes": [
                asdict(route) | {"kind": route.kind.value, "score": route.score}
                for route in self.routes
            ],
            "units": [unit.to_dict() for unit in self.units.values()],
            "truth_boundary": self.truth_boundary,
            "created_from": self.created_from,
        }


@dataclass(frozen=True)
class WaveDecision:
    wave_id: str
    runnable: tuple[str, ...]
    held: tuple[str, ...]
    blocked: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class WaveExecutionReceipt:
    wave_id: str
    runnable: tuple[str, ...]
    succeeded: tuple[str, ...]
    failed: tuple[str, ...]
    held: tuple[str, ...]
    blocked: tuple[str, ...]
    wall_duration_ms: float
    summed_unit_duration_ms: float
    measured_parallelism_ratio: float | None
    ledger_verified: bool
    measurement_scope: str = "LOCAL_WAVE_ONLY"


@dataclass(frozen=True)
class AccelerationProfile:
    reusable_output_count: int
    verified_reuse_hits: int
    work_units_avoided: int
    measured_baseline_samples: int
    measured_reuse_samples: int
    measured_speedup_ratio: float | None
    confidence: str
