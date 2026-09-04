"""Independent, generation-scoped five-phase canary controller."""

from __future__ import annotations

import statistics
from typing import Any, Mapping, Sequence

PHASES = ("B1", "C1", "B2", "C2", "C3_STABILITY")
REQUIRED_METRICS = ("duration_ms", "external_attempts", "proof_success", "invariant_failures", "harm_signals")


def evaluate_canary(
    observations: Sequence[Mapping[str, Any]],
    *,
    generation: int,
    duration_ratio_limit: float = 0.5,
    call_ratio_limit: float = 0.5,
) -> dict[str, Any]:
    issues: list[str] = []
    if [o.get("phase") for o in observations] != list(PHASES):
        issues.append("PHASE_SEQUENCE_INVALID")
    if len({o.get("slot") for o in observations}) != len(observations):
        issues.append("SLOT_NOT_UNIQUE")
    for index, observation in enumerate(observations):
        if observation.get("generation") != generation:
            issues.append(f"GENERATION_MISMATCH:{index}")
        if observation.get("directly_observed") is not True:
            issues.append(f"METRIC_NOT_DIRECT:{index}")
        for metric in REQUIRED_METRICS:
            if metric not in observation:
                issues.append(f"METRIC_MISSING:{index}:{metric}")
    baseline = [o for o in observations if str(o.get("phase", "")).startswith("B")]
    candidate = [o for o in observations if str(o.get("phase", "")).startswith("C")]
    metrics: dict[str, Any] = {}
    if baseline and candidate and not any("METRIC_MISSING" in issue for issue in issues):
        b_duration = statistics.median(float(o["duration_ms"]) for o in baseline)
        c_duration = statistics.median(float(o["duration_ms"]) for o in candidate)
        b_calls = statistics.median(float(o["external_attempts"]) for o in baseline)
        c_calls = statistics.median(float(o["external_attempts"]) for o in candidate)
        metrics = {
            "baseline_duration_ms": b_duration,
            "candidate_duration_ms": c_duration,
            "duration_ratio": c_duration / b_duration if b_duration else None,
            "baseline_external_attempts": b_calls,
            "candidate_external_attempts": c_calls,
            "call_ratio": c_calls / b_calls if b_calls else None,
        }
        if not b_duration or metrics["duration_ratio"] > duration_ratio_limit:
            issues.append("DURATION_TARGET_MISSED")
        if not b_calls or metrics["call_ratio"] > call_ratio_limit:
            issues.append("CALL_TARGET_MISSED")
        if any(not bool(o["proof_success"]) for o in observations):
            issues.append("PROOF_PARITY_LOST")
        if any(int(o["invariant_failures"]) for o in observations):
            issues.append("INVARIANT_REGRESSION")
        if any(int(o["harm_signals"]) for o in observations):
            issues.append("HARM_SIGNAL")
    decision = "PROMOTE" if not issues else "HOLD"
    return {
        "decision": decision,
        "issues": sorted(set(issues)),
        "metrics": metrics,
        "generation": generation,
        "deinstrument": decision in {"PROMOTE", "HOLD"},
        "proof_state": "CANARY_VALIDATED" if decision == "PROMOTE" else "TESTED_NOT_PROMOTED",
    }
