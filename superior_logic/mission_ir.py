from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

from .convergence import MissionIntentContract


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


class MissionCompileError(ValueError):
    pass


class EffectClass(str, Enum):
    READ_ONLY = "READ_ONLY"
    REVERSIBLE_EFFECT = "REVERSIBLE_EFFECT"
    IRREVERSIBLE_EFFECT = "IRREVERSIBLE_EFFECT"


@dataclass(frozen=True)
class TransitionSpec:
    transition_id: str
    description: str
    dependencies: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    effect_class: EffectClass = EffectClass.READ_ONLY
    risk: float = 0.0
    expected_value: float = 0.0
    uncertainty_reduction: float = 0.0
    estimated_latency_ms: float = 1000.0
    estimated_cost: float = 0.0
    conflict_domains: tuple[str, ...] = ()
    proof_obligations: tuple[str, ...] = ()
    speculative_allowed: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def mutating(self) -> bool:
        return self.effect_class is not EffectClass.READ_ONLY

    @property
    def reversible(self) -> bool:
        return self.effect_class in {EffectClass.READ_ONLY, EffectClass.REVERSIBLE_EFFECT}

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "description": self.description,
            "dependencies": list(self.dependencies),
            "required_capabilities": list(self.required_capabilities),
            "effect_class": self.effect_class.value,
            "risk": self.risk,
            "expected_value": self.expected_value,
            "uncertainty_reduction": self.uncertainty_reduction,
            "estimated_latency_ms": self.estimated_latency_ms,
            "estimated_cost": self.estimated_cost,
            "conflict_domains": list(self.conflict_domains),
            "proof_obligations": list(self.proof_obligations),
            "speculative_allowed": self.speculative_allowed,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class MissionIR:
    mission_id: str
    objective: str
    source_version: str
    initial_state: Mapping[str, Any]
    target_state: Mapping[str, Any]
    constraints: tuple[str, ...]
    authority_ceiling: str
    transitions: tuple[TransitionSpec, ...]
    budgets: Mapping[str, float]
    compiled_sha256: str

    def transition_map(self) -> dict[str, TransitionSpec]:
        return {item.transition_id: item for item in self.transitions}

    def topological_order(self) -> tuple[str, ...]:
        nodes = self.transition_map()
        incoming = {node_id: set(item.dependencies) for node_id, item in nodes.items()}
        ready = sorted(node_id for node_id, deps in incoming.items() if not deps)
        result: list[str] = []
        while ready:
            node_id = ready.pop(0)
            result.append(node_id)
            for other_id in sorted(incoming):
                if node_id in incoming[other_id]:
                    incoming[other_id].remove(node_id)
                    if not incoming[other_id] and other_id not in result and other_id not in ready:
                        ready.append(other_id)
                        ready.sort()
        if len(result) != len(nodes):
            raise MissionCompileError("MISSION_IR_CYCLE_DETECTED")
        return tuple(result)

    def ready_transitions(self, terminal_ids: Sequence[str] = ()) -> tuple[TransitionSpec, ...]:
        completed = set(terminal_ids)
        return tuple(
            item
            for item in self.transitions
            if item.transition_id not in completed and set(item.dependencies).issubset(completed)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "objective": self.objective,
            "source_version": self.source_version,
            "initial_state": dict(self.initial_state),
            "target_state": dict(self.target_state),
            "constraints": list(self.constraints),
            "authority_ceiling": self.authority_ceiling,
            "transitions": [item.to_dict() for item in self.transitions],
            "budgets": dict(self.budgets),
            "compiled_sha256": self.compiled_sha256,
        }


class MissionIRCompiler:
    """Compiles SLOS mission intent into a deterministic execution IR.

    The compiler does not execute effects. It validates dependency topology,
    speculative safety, budgets and transition identity so downstream planners
    can parallelise aggressively without weakening the SOL 6.2 transaction
    kernel or SOVARA provider-effect boundary.
    """

    @staticmethod
    def _transition(raw: TransitionSpec | Mapping[str, Any]) -> TransitionSpec:
        if isinstance(raw, TransitionSpec):
            item = raw
        else:
            effect_raw = raw.get("effect_class", EffectClass.READ_ONLY.value)
            effect_class = effect_raw if isinstance(effect_raw, EffectClass) else EffectClass(str(effect_raw))
            item = TransitionSpec(
                transition_id=str(raw.get("transition_id", "")).strip(),
                description=str(raw.get("description", "")).strip(),
                dependencies=tuple(str(value).strip() for value in raw.get("dependencies", ()) if str(value).strip()),
                required_capabilities=tuple(
                    sorted({str(value).strip().upper() for value in raw.get("required_capabilities", ()) if str(value).strip()})
                ),
                effect_class=effect_class,
                risk=float(raw.get("risk", 0.0)),
                expected_value=float(raw.get("expected_value", 0.0)),
                uncertainty_reduction=float(raw.get("uncertainty_reduction", 0.0)),
                estimated_latency_ms=float(raw.get("estimated_latency_ms", 1000.0)),
                estimated_cost=float(raw.get("estimated_cost", 0.0)),
                conflict_domains=tuple(sorted({str(value).strip() for value in raw.get("conflict_domains", ()) if str(value).strip()})),
                proof_obligations=tuple(str(value).strip() for value in raw.get("proof_obligations", ()) if str(value).strip()),
                speculative_allowed=bool(raw.get("speculative_allowed", False)),
                metadata=dict(raw.get("metadata", {})),
            )
        if not item.transition_id or not item.description:
            raise MissionCompileError("TRANSITION_ID_AND_DESCRIPTION_REQUIRED")
        if not 0.0 <= item.risk <= 1.0:
            raise MissionCompileError(f"RISK_OUT_OF_RANGE:{item.transition_id}")
        if not 0.0 <= item.uncertainty_reduction <= 1.0:
            raise MissionCompileError(f"UNCERTAINTY_REDUCTION_OUT_OF_RANGE:{item.transition_id}")
        if item.estimated_latency_ms <= 0 or item.estimated_cost < 0:
            raise MissionCompileError(f"INVALID_COST_OR_LATENCY:{item.transition_id}")
        if item.mutating and item.speculative_allowed:
            raise MissionCompileError(f"SPECULATIVE_MUTATION_FORBIDDEN:{item.transition_id}")
        return item

    def compile(
        self,
        contract: MissionIntentContract,
        transitions: Sequence[TransitionSpec | Mapping[str, Any]],
        *,
        authority_ceiling: str = "MISSION_SCOPED",
        budgets: Mapping[str, float] | None = None,
    ) -> MissionIR:
        compiled = tuple(self._transition(item) for item in transitions)
        if not compiled:
            raise MissionCompileError("MISSION_REQUIRES_AT_LEAST_ONE_TRANSITION")
        ids = [item.transition_id for item in compiled]
        if len(set(ids)) != len(ids):
            raise MissionCompileError("DUPLICATE_TRANSITION_ID")
        known = set(ids)
        for item in compiled:
            unknown = sorted(set(item.dependencies).difference(known))
            if unknown:
                raise MissionCompileError(
                    f"UNKNOWN_DEPENDENCY:{item.transition_id}:" + ",".join(unknown)
                )
            if item.transition_id in item.dependencies:
                raise MissionCompileError(f"SELF_DEPENDENCY:{item.transition_id}")
        normalized_budgets = {
            str(key): float(value) for key, value in dict(budgets or {}).items()
        }
        if any(value < 0 for value in normalized_budgets.values()):
            raise MissionCompileError("NEGATIVE_BUDGET_FORBIDDEN")
        if not authority_ceiling.strip():
            raise MissionCompileError("AUTHORITY_CEILING_REQUIRED")

        body = {
            "schema": "SLOS_MISSION_IR_V1",
            "mission_id": contract.mission_id,
            "objective": contract.objective,
            "source_version": contract.source_version,
            "initial_state": dict(contract.initial_state),
            "target_state": dict(contract.target_state),
            "constraints": list(contract.constraints),
            "authority_ceiling": authority_ceiling,
            "transitions": [item.to_dict() for item in compiled],
            "budgets": normalized_budgets,
        }
        mission = MissionIR(
            mission_id=contract.mission_id,
            objective=contract.objective,
            source_version=contract.source_version,
            initial_state=dict(contract.initial_state),
            target_state=dict(contract.target_state),
            constraints=tuple(contract.constraints),
            authority_ceiling=authority_ceiling,
            transitions=compiled,
            budgets=normalized_budgets,
            compiled_sha256=_digest(body),
        )
        mission.topological_order()
        return mission


__all__ = [
    "EffectClass",
    "MissionCompileError",
    "MissionIR",
    "MissionIRCompiler",
    "TransitionSpec",
]
