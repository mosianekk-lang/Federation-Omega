from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


class EpistemicState(str, Enum):
    VERIFIED_FACT = "VERIFIED_FACT"
    VERIFIED_LAW = "VERIFIED_LAW"
    VERIFIED_WITH_LIMITATION = "VERIFIED_WITH_LIMITATION"
    USER_SUPPLIED = "USER_SUPPLIED"
    DISPUTED = "DISPUTED"
    INFERENCE = "INFERENCE"
    UNKNOWN = "UNKNOWN"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True)
class ScientificObservation:
    observation_id: str
    statement: str
    state: EpistemicState
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    statement: str
    predictions: tuple[str, ...]
    falsifiers: tuple[str, ...]


def _digest(payload: Any) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(body.encode("utf-8")).hexdigest()


def _contains_forbidden_key(value: Any, forbidden: set[str]) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in forbidden:
                return True
            if _contains_forbidden_key(child, forbidden):
                return True
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_forbidden_key(item, forbidden) for item in value)
    return False


class ScientiaKernel:
    """Fail-closed scientific-method controls for CASEFORGE benchmark work.

    The kernel does not decide law or mutate verified evidence. It makes the
    reasoning process falsifiable, blind where required, reproducible and
    explicit about competing explanations.
    """

    forbidden_blind_keys = {
        "answer_key",
        "control_answer",
        "expected_outcome",
        "judgment_outcome",
        "ratio_answer",
    }

    def validate_case_design(
        self,
        *,
        observations: Sequence[ScientificObservation],
        hypotheses: Sequence[Hypothesis],
        require_competing_hypothesis: bool = True,
    ) -> dict[str, Any]:
        if not observations:
            raise ValueError("scientific case requires at least one observation")
        if require_competing_hypothesis and len(hypotheses) < 2:
            raise ValueError("material case requires competing hypotheses")

        observation_ids = [item.observation_id for item in observations]
        hypothesis_ids = [item.hypothesis_id for item in hypotheses]
        if len(observation_ids) != len(set(observation_ids)):
            raise ValueError("duplicate observation_id")
        if len(hypothesis_ids) != len(set(hypothesis_ids)):
            raise ValueError("duplicate hypothesis_id")

        for hypothesis in hypotheses:
            if not hypothesis.predictions:
                raise ValueError(f"{hypothesis.hypothesis_id} has no testable prediction")
            if not hypothesis.falsifiers:
                raise ValueError(f"{hypothesis.hypothesis_id} has no falsifier")

        return {
            "status": "SCIENTIFIC_DESIGN_VALID",
            "observations": len(observations),
            "hypotheses": len(hypotheses),
            "design_sha256": _digest(
                {
                    "observations": observations,
                    "hypotheses": hypotheses,
                    "require_competing_hypothesis": require_competing_hypothesis,
                }
            ),
            "authority_ceiling": "A1_INTERNAL",
            "external_effect": False,
        }

    def assert_blind_pack(self, blind_pack: Mapping[str, Any]) -> str:
        if _contains_forbidden_key(blind_pack, self.forbidden_blind_keys):
            raise ValueError("answer-key/control leakage detected in blind pack")
        return _digest(blind_pack)

    def preregister_experiment(
        self,
        *,
        experiment_id: str,
        hypothesis: str,
        primary_metric: str,
        success_threshold: float,
        failure_threshold: float,
        benchmark_ids: Sequence[str],
        rollback_condition: str,
    ) -> dict[str, Any]:
        if not experiment_id.strip() or not hypothesis.strip():
            raise ValueError("experiment_id and hypothesis are required")
        if not primary_metric.strip():
            raise ValueError("primary metric is required")
        if success_threshold <= failure_threshold:
            raise ValueError("success threshold must exceed failure threshold")
        if not benchmark_ids:
            raise ValueError("at least one benchmark is required")
        if not rollback_condition.strip():
            raise ValueError("rollback condition is required")

        plan = {
            "experiment_id": experiment_id,
            "hypothesis": hypothesis,
            "primary_metric": primary_metric,
            "success_threshold": float(success_threshold),
            "failure_threshold": float(failure_threshold),
            "benchmark_ids": tuple(benchmark_ids),
            "rollback_condition": rollback_condition,
            "authority_ceiling": "A1_INTERNAL",
            "external_effect": False,
        }
        return {**plan, "preregistration_sha256": _digest(plan)}

    def minimum_provable_conclusion(
        self,
        *,
        supporting_evidence: float,
        counter_evidence: float,
        replicated: bool,
        authority_current: bool,
    ) -> str:
        support = max(0.0, min(1.0, float(supporting_evidence)))
        counter = max(0.0, min(1.0, float(counter_evidence)))
        if not authority_current:
            return "UNRESOLVED_AUTHORITY_RECHECK_REQUIRED"
        net = support - counter
        if replicated and net >= 0.65:
            return "VERY_STRONG"
        if replicated and net >= 0.4:
            return "STRONG"
        if net >= 0.2:
            return "MODERATE"
        if net > 0:
            return "WEAK"
        return "UNRESOLVED"
