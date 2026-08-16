from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from .models import ArchitectureComponent, PerformanceVector


def fitness(p: PerformanceVector) -> float:
    positive = (
        p.quality
        + p.reliability
        + p.proof
        + p.speed
        + p.owner_time_recovered
        + p.privacy_gain
        + p.recovery_gain
        + p.simplicity_gain
    )
    negative = (
        p.false_blocks
        + p.error_cost
        + p.latency_cost
        + p.owner_burden
        + p.privacy_risk
        + p.complexity
        + p.maintenance_cost
        + p.regression_risk
    )
    return positive - negative


class PolicyEvolution:
    """Promote candidate behavior only when measured fitness improves."""

    def compare(self, incumbent: PerformanceVector, candidate: PerformanceVector) -> dict[str, Any]:
        incumbent_score = fitness(incumbent)
        candidate_score = fitness(candidate)
        return {
            "incumbent": incumbent_score,
            "candidate": candidate_score,
            "promote": candidate_score > incumbent_score,
            "delta": candidate_score - incumbent_score,
        }


class EntropyController:
    def classify(self, component: ArchitectureComponent) -> str:
        if component.owner_value <= 0.1 and component.usage <= 0.1:
            return "RETIRE"
        if component.overlap >= 0.8 and not component.unique_function:
            return "MERGE"
        if component.overlap >= 0.5 and not component.unique_function:
            return "ABSORB"
        if component.usage < 0.2 and component.owner_value < 0.3:
            return "PAUSE"
        return "KEEP"


class HumanAttentionGovernor:
    EPSILON = 1e-9

    def score(
        self,
        *,
        urgency: float,
        consequence: float,
        decision_necessity: float,
        owner_exclusivity: float,
        self_resolution_capability: float,
    ) -> float:
        return (
            urgency
            * consequence
            * decision_necessity
            * owner_exclusivity
        ) / (self_resolution_capability + self.EPSILON)

    def should_interrupt(self, score: float, threshold: float = 1.0) -> bool:
        return score >= threshold


class MarginalInformationGainGate:
    EPSILON = 1e-9

    def score(
        self,
        *,
        expected_information_gain: float,
        decision_impact: float,
        latency: float,
        owner_burden: float,
        duplication_cost: float,
    ) -> float:
        return (expected_information_gain * decision_impact) / (
            latency + owner_burden + duplication_cost + self.EPSILON
        )

    def should_verify(
        self,
        score: float,
        *,
        consequential: bool,
        threshold: float = 0.5,
    ) -> bool:
        return consequential or score >= threshold


@dataclass(frozen=True)
class LearningEvent:
    cycle_id: str
    objective: str
    terminal_state: str
    actual_result: str
    proof_refs: tuple[str, ...] = ()
    proposed_patch: str | None = None
    fitness_score: float = 0.0


class LearningLedger:
    """Append-only in-memory hash chain for deterministic learning tests.

    Durable learning belongs in the approved external evidence plane, not source.
    """

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    @property
    def records(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._records)

    def append(self, event: LearningEvent) -> dict[str, Any]:
        previous_hash = self._records[-1]["hash"] if self._records else "GENESIS"
        payload = asdict(event)
        canonical = json.dumps(
            {"previous_hash": previous_hash, "event": payload},
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        record = {"previous_hash": previous_hash, "event": payload, "hash": digest}
        self._records.append(record)
        return record

    def verify(self) -> bool:
        previous_hash = "GENESIS"
        for record in self._records:
            canonical = json.dumps(
                {"previous_hash": previous_hash, "event": record["event"]},
                sort_keys=True,
                separators=(",", ":"),
            )
            expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if record["previous_hash"] != previous_hash or record["hash"] != expected:
                return False
            previous_hash = record["hash"]
        return True
