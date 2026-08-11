from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .federation_evolution_program import AUTHORITY_CEILING, SYSTEM_PROFILES, StrategyMode
from .federation_evolution_runtime import COMMON_RUNTIME_STAGES


@dataclass(frozen=True)
class SpecializedPathContract:
    system_id: str
    optimization_objective: str
    algorithm_chain: tuple[str, ...]
    vetoes: tuple[str, ...]
    common_runtime_stages: tuple[int, ...] = COMMON_RUNTIME_STAGES
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect: bool = False
    stronger_or_equal_to_common: bool = True

    def validate(self) -> "SpecializedPathContract":
        if self.system_id not in SYSTEM_PROFILES:
            raise ValueError(f"unregistered system: {self.system_id}")
        if not self.optimization_objective.strip():
            raise ValueError("optimization_objective required")
        if not self.algorithm_chain:
            raise ValueError("specialized path requires algorithm_chain")
        if tuple(self.common_runtime_stages) != COMMON_RUNTIME_STAGES:
            raise ValueError("specialized path may not skip common runtime stages 3-15")
        if self.authority_ceiling != AUTHORITY_CEILING or self.external_effect:
            raise ValueError("specialized path cannot expand authority or create default external effects")
        if not self.stronger_or_equal_to_common:
            raise ValueError("specialized path must be stronger than or equal to common invariants")
        return self


@dataclass(frozen=True)
class SpecializedExecutionContext:
    system_id: str
    optimization_objective: str
    mandatory_algorithm_chain: tuple[str, ...]
    vetoes: tuple[str, ...]
    common_runtime_stages: tuple[int, ...]
    proof_required: bool = True
    rollback_required_for_mutation: bool = True
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect: bool = False


class SpecializedPathResolver:
    """Resolve the stronger system-native path without weakening the common spine."""

    def resolve(self, system_id: str) -> SpecializedPathContract:
        profile = SYSTEM_PROFILES[system_id]
        algorithms = profile.specialized_algorithms
        if profile.strategy_mode is StrategyMode.INHERIT_CORE and not algorithms:
            algorithms = ("COMMON_FEDERATION_EVOLUTION_RUNTIME",)
        return SpecializedPathContract(
            system_id=system_id,
            optimization_objective=profile.optimization_objective,
            algorithm_chain=tuple(algorithms),
            vetoes=tuple(profile.vetoes),
        ).validate()

    def execution_context(self, system_id: str) -> SpecializedExecutionContext:
        contract = self.resolve(system_id)
        return SpecializedExecutionContext(
            system_id=contract.system_id,
            optimization_objective=contract.optimization_objective,
            mandatory_algorithm_chain=contract.algorithm_chain,
            vetoes=contract.vetoes,
            common_runtime_stages=contract.common_runtime_stages,
        )

    def resolve_all(self) -> Mapping[str, SpecializedPathContract]:
        return {system_id: self.resolve(system_id) for system_id in SYSTEM_PROFILES}


__all__ = [
    "SpecializedExecutionContext",
    "SpecializedPathContract",
    "SpecializedPathResolver",
]
