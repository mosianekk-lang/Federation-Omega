from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class RepairCandidate:
    repair_id: str
    incident_class: str
    change_set: tuple[str, ...]
    expected_effects: dict[str, float]
    rollback_steps: tuple[str, ...]
    risk: str = "LOW"
    controller_change: bool = False


@dataclass
class RepairReceipt:
    repair_id: str
    state: str
    gates: dict[str, bool]
    observations: dict[str, Any] = field(default_factory=dict)
    sha256: str = ""


class AutonomousRepairFabric:
    """Provider-neutral, fail-closed repair controller.

    Repairs must pass shadow execution, differential validation, rollback
    rehearsal and canary gates before promotion. Controller changes require
    independent certification and can never self-certify.
    """

    RISK_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

    def __init__(self, recurrence_threshold: int = 3) -> None:
        self.recurrence_threshold = recurrence_threshold
        self.failures: list[dict[str, Any]] = []
        self.promotions: dict[str, dict[str, Any]] = {}

    def record_failure(self, incident_class: str, signature: str) -> dict[str, Any]:
        row = {"incident_class": incident_class, "signature": signature}
        self.failures.append(row)
        count = sum(1 for x in self.failures if x == row)
        return {**row, "count": count, "recurrent": count >= self.recurrence_threshold}

    def synthesise(self, incident_class: str, signature: str, known_repairs: list[RepairCandidate]) -> list[RepairCandidate]:
        candidates = [c for c in known_repairs if c.incident_class == incident_class]
        return sorted(candidates, key=lambda c: (self.RISK_ORDER.get(c.risk, 99), -sum(c.expected_effects.values()), c.repair_id))

    def shadow_execute(self, candidate: RepairCandidate, runner: Callable[[RepairCandidate], dict[str, Any]]) -> dict[str, Any]:
        result = runner(candidate)
        return {"isolated": True, "mutated_live_state": False, "result": result, "passed": bool(result.get("passed"))}

    @staticmethod
    def differential_validate(baseline: dict[str, float], shadow: dict[str, float], tolerances: dict[str, float]) -> dict[str, Any]:
        deltas = {key: shadow.get(key, 0.0) - baseline.get(key, 0.0) for key in set(baseline) | set(shadow)}
        violations = {
            key: delta for key, delta in deltas.items()
            if key in tolerances and abs(delta) > tolerances[key]
        }
        return {"passed": not violations, "deltas": deltas, "violations": violations}

    @staticmethod
    def rehearse_rollback(candidate: RepairCandidate, runner: Callable[[tuple[str, ...]], bool]) -> dict[str, Any]:
        complete = bool(candidate.rollback_steps) and runner(candidate.rollback_steps)
        return {"passed": complete, "steps": list(candidate.rollback_steps)}

    @staticmethod
    def canary_validate(metrics: dict[str, float], thresholds: dict[str, tuple[str, float]]) -> dict[str, Any]:
        results: dict[str, bool] = {}
        for name, (op, target) in thresholds.items():
            value = metrics.get(name)
            results[name] = value is not None and ((value <= target) if op == "LTE" else (value >= target))
        return {"passed": bool(results) and all(results.values()), "results": results}

    def evaluate_promotion(
        self,
        candidate: RepairCandidate,
        *,
        shadow: dict[str, Any],
        differential: dict[str, Any],
        rollback: dict[str, Any],
        canary: dict[str, Any],
        proposer: str,
        executor: str,
        certifier: str,
        owner_authorised: bool = False,
    ) -> RepairReceipt:
        role_separation = len({proposer, executor, certifier}) == 3
        controller_gate = not candidate.controller_change or (owner_authorised and certifier not in {proposer, executor})
        gates = {
            "shadow_execution": bool(shadow.get("passed")) and not shadow.get("mutated_live_state", True),
            "differential_validation": bool(differential.get("passed")),
            "rollback_rehearsal": bool(rollback.get("passed")),
            "canary_validation": bool(canary.get("passed")),
            "role_separation": role_separation,
            "controller_change_authority": controller_gate,
        }
        state = "PROMOTION_ELIGIBLE" if all(gates.values()) else "PROMOTION_DENIED"
        receipt = RepairReceipt(candidate.repair_id, state, gates, {
            "shadow": shadow, "differential": differential, "rollback": rollback, "canary": canary
        })
        receipt.sha256 = digest(asdict(receipt) | {"sha256": ""})
        return receipt

    def promote(self, candidate: RepairCandidate, receipt: RepairReceipt) -> dict[str, Any]:
        if receipt.state != "PROMOTION_ELIGIBLE" or not all(receipt.gates.values()):
            raise RuntimeError("REPAIR_NOT_ELIGIBLE")
        if candidate.repair_id in self.promotions:
            return self.promotions[candidate.repair_id]
        row = {"repair_id": candidate.repair_id, "state": "PROMOTED", "receipt_sha256": receipt.sha256}
        self.promotions[candidate.repair_id] = row
        return row
