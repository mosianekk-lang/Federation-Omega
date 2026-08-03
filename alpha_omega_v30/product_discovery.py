from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .sandbox_fleet import ReceiptLedger


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class PainSignal:
    signal_id: str
    segment: str
    problem: str
    frequency: float
    annual_cost: float
    urgency: float
    confidence: float
    evidence_ref: str

    def validate(self) -> None:
        if not self.signal_id or not self.segment or not self.problem or not self.evidence_ref:
            raise ValueError("signal identity, segment, problem and evidence are required")
        if self.frequency < 0 or self.annual_cost < 0:
            raise ValueError("frequency and annual cost cannot be negative")
        if not 0 <= self.urgency <= 1 or not 0 <= self.confidence <= 1:
            raise ValueError("urgency and confidence must be within [0, 1]")


@dataclass(frozen=True)
class ProductHypothesis:
    hypothesis_id: str
    segment: str
    problem: str
    value_score: float
    evidence_refs: tuple[str, ...]
    signal_ids: tuple[str, ...]


@dataclass(frozen=True)
class ExperimentContract:
    experiment_id: str
    hypothesis_id: str
    metric: str
    threshold: float
    max_cost: float
    reversible: bool
    authority: str

    def validate(self) -> None:
        if self.max_cost < 0 or not self.metric or not self.authority:
            raise ValueError("invalid experiment contract")
        if not self.reversible:
            raise ValueError("autonomous experiments must be reversible")


class ProductDiscoveryEngine:
    def discover(self, signals: Iterable[PainSignal]) -> list[ProductHypothesis]:
        groups: dict[tuple[str, str], list[PainSignal]] = {}
        for signal in signals:
            signal.validate()
            key = (signal.segment.strip().casefold(), signal.problem.strip().casefold())
            groups.setdefault(key, []).append(signal)

        hypotheses: list[ProductHypothesis] = []
        for (segment, problem), group in groups.items():
            expected_value = sum(
                item.frequency * item.annual_cost * item.urgency * item.confidence for item in group
            )
            identity = {
                "segment": segment,
                "problem": problem,
                "signals": sorted(item.signal_id for item in group),
            }
            hypotheses.append(
                ProductHypothesis(
                    hypothesis_id=f"HYP-{_digest(identity)[:16]}",
                    segment=segment,
                    problem=problem,
                    value_score=expected_value,
                    evidence_refs=tuple(sorted({item.evidence_ref for item in group})),
                    signal_ids=tuple(sorted(item.signal_id for item in group)),
                )
            )
        return sorted(hypotheses, key=lambda item: (-item.value_score, item.hypothesis_id))


class ExperimentEvaluator:
    def __init__(self, ledger_path: str | Path):
        self.ledger = ReceiptLedger(ledger_path)

    def evaluate(
        self,
        contract: ExperimentContract,
        observed_metric: float,
        actual_cost: float,
        evidence: Mapping[str, Any],
    ) -> dict[str, Any]:
        contract.validate()
        if actual_cost < 0:
            raise ValueError("actual_cost cannot be negative")
        within_budget = actual_cost <= contract.max_cost
        evidence_present = bool(evidence)
        passed = within_budget and evidence_present and observed_metric >= contract.threshold
        result = {
            "contract": asdict(contract),
            "observed_metric": observed_metric,
            "actual_cost": actual_cost,
            "within_budget": within_budget,
            "evidence_present": evidence_present,
            "validated": passed,
            "evidence": dict(evidence),
            "market_proof": "EXTERNAL_EVIDENCE_REQUIRED" if evidence.get("source") == "synthetic" else "OBSERVED",
        }
        result["result_hash"] = _digest(result)
        result["ledger_entry"] = self.ledger.append(result)["entry_hash"]
        result["persistence_verified"] = self.ledger.verify()["valid"]
        return result
