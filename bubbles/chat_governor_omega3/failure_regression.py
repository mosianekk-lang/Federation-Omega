"""Observed-failure to regression-case compiler for ChatGov.

This is a local deterministic capture layer inspired by trajectory-evaluation
systems. It converts real PRE_FINAL_RESPONSE failures into replayable fixtures.
It does not claim an external Braintrust, Weave or other eval platform binding.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any

from .pre_final import FinalizationDecision, MissionClosureState


_FAILURE_CLASS_BY_PREFIX = {
    "KNOWN_ACTIONABLE_GAP_REMAINS": "F19_KNOWN_ACTIONABLE_GAP_PREMATURE_TERMINATION",
    "CLAIM_PROOF_GATE_BLOCK": "F20_SOURCE_RUNTIME_OR_CLAIM_PROOF_CONFLATION",
    "MATERIAL_MATURITY_CLAIM_SCAN_REQUIRED": "F24_MATURITY_CLAIM_WITHOUT_CLAIM_PROOF_SCAN",
    "MANDATORY_CONTROL_ORPHANED_OR_UNTESTED": "F22_ORPHAN_MANDATORY_CONTROL_ENFORCEMENT",
    "RECOVERABLE_ISSUE_REQUIRES_CONTINUED_RECOVERY": "F23_PROBLEM_REPORTED_BEFORE_AVAILABLE_RECOVERY",
}


@dataclass(frozen=True)
class PreFinalRegressionCase:
    case_id: str
    mission_id: str
    objective: str
    candidate_response: str
    terminal_state: str
    observed_decision_mode: str
    expected_allow_final: bool
    expected_continue_work: bool
    failure_classes: tuple[str, ...]
    source_decision_id: str
    mission_sha256: str
    candidate_sha256: str

    def as_dataset_record(self) -> dict[str, Any]:
        return asdict(self)


def _hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def classify_failure_reasons(reasons: tuple[str, ...]) -> tuple[str, ...]:
    classes: list[str] = []
    for reason in reasons:
        for prefix, failure_class in _FAILURE_CLASS_BY_PREFIX.items():
            if reason == prefix or reason.startswith(prefix + ":"):
                classes.append(failure_class)
                break
    return tuple(dict.fromkeys(classes))


def compile_prefinal_regression(
    *,
    mission: MissionClosureState,
    candidate_response: str,
    decision: FinalizationDecision,
) -> PreFinalRegressionCase:
    mission_payload = asdict(mission)
    mission_sha = _hash(mission_payload)
    candidate_sha = _hash(candidate_response)
    classes = classify_failure_reasons(decision.reasons)
    material = {
        "mission_sha256": mission_sha,
        "candidate_sha256": candidate_sha,
        "decision_id": decision.decision_id,
        "failure_classes": classes,
    }
    return PreFinalRegressionCase(
        case_id="pfr_" + _hash(material)[:24],
        mission_id=mission.mission_id,
        objective=mission.objective,
        candidate_response=candidate_response,
        terminal_state=mission.terminal_state.value,
        observed_decision_mode=decision.mode,
        expected_allow_final=decision.allow_final,
        expected_continue_work=decision.continue_work,
        failure_classes=classes,
        source_decision_id=decision.decision_id,
        mission_sha256=mission_sha,
        candidate_sha256=candidate_sha,
    )


__all__ = [
    "PreFinalRegressionCase",
    "classify_failure_reasons",
    "compile_prefinal_regression",
]
