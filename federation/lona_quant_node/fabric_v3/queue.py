"""Deterministic experiment queue state for the Quant Evidence Fabric v3.

Research-only. No state in this module authorizes broker or capital execution.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import json
from typing import Any, Mapping


class ExperimentState(str, Enum):
    PLANNED = "PLANNED"
    DISPATCHED = "DISPATCHED"
    EXECUTING = "EXECUTING"
    COMPLETED_UNVERIFIED = "COMPLETED_UNVERIFIED"
    EVIDENCE_VERIFIED = "EVIDENCE_VERIFIED"
    REJECTED = "REJECTED"
    REVISE = "REVISE"
    RESEARCH_ADMITTED = "RESEARCH_ADMITTED"
    FAILED = "FAILED"


_ALLOWED = {
    ExperimentState.PLANNED: {ExperimentState.DISPATCHED, ExperimentState.FAILED},
    ExperimentState.DISPATCHED: {ExperimentState.EXECUTING, ExperimentState.COMPLETED_UNVERIFIED, ExperimentState.FAILED},
    ExperimentState.EXECUTING: {ExperimentState.COMPLETED_UNVERIFIED, ExperimentState.FAILED},
    ExperimentState.COMPLETED_UNVERIFIED: {ExperimentState.EVIDENCE_VERIFIED, ExperimentState.FAILED},
    ExperimentState.EVIDENCE_VERIFIED: {ExperimentState.REJECTED, ExperimentState.REVISE, ExperimentState.RESEARCH_ADMITTED},
    ExperimentState.REJECTED: set(),
    ExperimentState.REVISE: set(),
    ExperimentState.RESEARCH_ADMITTED: set(),
    ExperimentState.FAILED: set(),
}


@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    fingerprint: str
    state: ExperimentState
    provider_ref: str | None = None
    evidence_ref: str | None = None

    def transition(self, target: ExperimentState, *, evidence_ref: str | None = None) -> "Experiment":
        if target not in _ALLOWED[self.state]:
            raise ValueError(f"illegal transition {self.state.value}->{target.value}")
        if target in {ExperimentState.EVIDENCE_VERIFIED, ExperimentState.REJECTED, ExperimentState.REVISE, ExperimentState.RESEARCH_ADMITTED} and not (evidence_ref or self.evidence_ref):
            raise ValueError("evidence_ref required for evidence-bearing state")
        return replace(self, state=target, evidence_ref=evidence_ref or self.evidence_ref)


def deterministic_experiment_id(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def deduplicate(experiments: list[Experiment]) -> list[Experiment]:
    seen: set[str] = set()
    out: list[Experiment] = []
    for item in experiments:
        if item.fingerprint not in seen:
            seen.add(item.fingerprint)
            out.append(item)
    return out
