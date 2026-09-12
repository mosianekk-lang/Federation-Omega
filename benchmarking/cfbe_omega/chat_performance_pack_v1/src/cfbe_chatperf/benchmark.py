"""Evidence-state-aware CFBE weighted benchmark."""

from __future__ import annotations

from typing import Any, Mapping

VALID_STATES = {"VERIFIED", "DESIGN", "UNKNOWN"}


def score_benchmark(packet: Mapping[str, Any]) -> dict[str, Any]:
    dimensions = list(packet.get("dimensions", []))
    if not dimensions:
        raise ValueError("dimensions required")
    total_weight = sum(float(d["weight"]) for d in dimensions)
    if abs(total_weight - 1.0) > 1e-9:
        raise ValueError("weights must sum to 1")
    issues: list[str] = []
    verified_total = 0.0
    readiness_total = 0.0
    for dimension in dimensions:
        state = dimension.get("state", "UNKNOWN")
        if state not in VALID_STATES:
            raise ValueError(f"invalid evidence state: {state}")
        score = float(dimension["score"])
        if not 0 <= score <= 10:
            raise ValueError("scores must be in [0,10]")
        contribution = float(dimension["weight"]) * score
        readiness_total += contribution
        if state == "VERIFIED":
            verified_total += contribution
        else:
            issues.append(f"UNVERIFIED:{dimension['id']}:{state}")
    return {
        "verified_score": round(verified_total * 10, 2),
        "readiness_score": round(readiness_total * 10, 2),
        "decision": "ACHIEVED" if not issues else "MIXED_PROOF",
        "issues": issues,
        "scope": packet.get("scope", "unspecified"),
    }
