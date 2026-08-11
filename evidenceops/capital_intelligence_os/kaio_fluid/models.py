from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class EvidenceState(str, Enum):
    VERIFIED = "VERIFIED"
    SUPPORTED = "SUPPORTED"
    USER_SUPPLIED = "USER_SUPPLIED"
    INFERENCE = "INFERENCE"
    UNVERIFIED = "UNVERIFIED"


class CognitiveMode(str, Enum):
    REFLEX = "REFLEX"
    ANALYTICAL = "ANALYTICAL"
    INVESTIGATIVE = "INVESTIGATIVE"
    ADVERSARIAL = "ADVERSARIAL"
    DISCOVERY = "DISCOVERY"
    DEEP_SYNTHESIS = "DEEP_SYNTHESIS"


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    state: EvidenceState
    source_identity: str
    independent_lineage: str
    reliability: float = 0.5
    materiality: float = 0.5


@dataclass(frozen=True)
class Hypothesis:
    id: str
    statement: str
    confidence: float
    expected_observations: tuple[str, ...] = ()
    falsifiers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProblemContext:
    objective: str
    stakes: float
    uncertainty: float
    novelty: float
    irreversibility: float
    evidence: tuple[EvidenceItem, ...] = ()
    constraints: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()

    def bounded(self) -> "ProblemContext":
        def clip(value: float) -> float:
            return max(0.0, min(1.0, value))

        return ProblemContext(
            objective=self.objective,
            stakes=clip(self.stakes),
            uncertainty=clip(self.uncertainty),
            novelty=clip(self.novelty),
            irreversibility=clip(self.irreversibility),
            evidence=self.evidence,
            constraints=self.constraints,
            assumptions=self.assumptions,
        )


@dataclass(frozen=True)
class ReasoningPlan:
    mode: CognitiveMode
    specialists: tuple[str, ...]
    primitives: tuple[str, ...]
    verification_depth: int
    simulation_depth: int
    stop_threshold: float
    authority_ceiling: str = "A1_INTERNAL"
    external_effect: bool = False
    notes: tuple[str, ...] = ()


@dataclass
class PredictionLedger:
    predictions: list[dict] = field(default_factory=list)

    def record(self, prediction: str, probability: float, outcome: str | None = None) -> None:
        self.predictions.append(
            {
                "prediction": prediction,
                "probability": max(0.0, min(1.0, probability)),
                "outcome": outcome,
            }
        )

    def calibration_error(self) -> float | None:
        scored = [p for p in self.predictions if p["outcome"] in {"true", "false"}]
        if not scored:
            return None
        errors = []
        for item in scored:
            observed = 1.0 if item["outcome"] == "true" else 0.0
            errors.append(abs(item["probability"] - observed))
        return sum(errors) / len(errors)


def independent_source_count(items: Iterable[EvidenceItem]) -> int:
    return len({item.independent_lineage for item in items})
