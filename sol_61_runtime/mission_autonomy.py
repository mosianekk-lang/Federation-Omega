from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class MissionGoal:
    mission_id: str
    objective: str
    success_receipts: tuple[str, ...]
    constraints: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkUnit:
    work_id: str
    objective: str
    dependencies: tuple[str, ...] = ()
    required_receipts: tuple[str, ...] = ()
    priority: int = 50
    cost: float = 1.0
    risk: float = 0.0
    blocked: bool = False
    substitute_for: str | None = None


@dataclass
class MissionPlan:
    mission_id: str
    revision: int
    units: dict[str, dict[str, Any]] = field(default_factory=dict)
    receipts: dict[str, dict[str, Any]] = field(default_factory=dict)
    closure_state: str = "OPEN"


class MissionAutonomyEngine:
    """Provider-neutral mission planner with proof-based closure.

    The engine decomposes goals, orders independent workstreams, substitutes
    blocked paths, inherits completion contracts, replans deterministically,
    and refuses mission closure until every required receipt is present.
    """

    def __init__(self, goal: MissionGoal) -> None:
        self.goal = goal
        self.plan = MissionPlan(goal.mission_id, revision=1)
        self.history: list[dict[str, Any]] = []

    def decompose(self, units: list[WorkUnit]) -> MissionPlan:
        seen: set[str] = set()
        for unit in units:
            if unit.work_id in seen:
                raise ValueError("duplicate work unit")
            seen.add(unit.work_id)
            inherited = tuple(sorted(set(unit.required_receipts) | set(self.goal.success_receipts if not unit.dependencies else ())))
            row = asdict(unit)
            row.update({"required_receipts": inherited, "status": "BLOCKED" if unit.blocked else "QUEUED"})
            self.plan.units[unit.work_id] = row
        unknown = sorted({dep for unit in units for dep in unit.dependencies if dep not in seen})
        if unknown:
            raise ValueError(f"unknown dependencies:{','.join(unknown)}")
        self._record("PLAN_DECOMPOSED", {"work_units": sorted(seen)})
        return self.plan

    def ready(self) -> list[dict[str, Any]]:
        completed = {wid for wid, row in self.plan.units.items() if row["status"] == "VERIFIED"}
        rows = [
            row for row in self.plan.units.values()
            if row["status"] == "QUEUED" and set(row["dependencies"]) <= completed
        ]
        return sorted(rows, key=lambda row: (-int(row["priority"]), float(row["cost"]), float(row["risk"]), row["work_id"]))

    def optimise(self, capacity: int) -> list[str]:
        if capacity < 1:
            return []
        selected: list[str] = []
        used_dependencies: set[str] = set()
        for row in self.ready():
            if len(selected) >= capacity:
                break
            affinity = set(row["dependencies"])
            penalty = len(affinity & used_dependencies)
            if penalty and len(selected) + 1 < capacity:
                continue
            selected.append(row["work_id"])
            used_dependencies |= affinity
        return selected

    def substitute_blocked(self, blocked_work_id: str, substitute: WorkUnit) -> dict[str, Any]:
        blocked = self.plan.units[blocked_work_id]
        if blocked["status"] != "BLOCKED":
            raise ValueError("target path is not blocked")
        if substitute.substitute_for != blocked_work_id:
            raise ValueError("substitution linkage required")
        inherited = tuple(sorted(set(substitute.required_receipts) | set(blocked["required_receipts"])))
        row = asdict(substitute)
        row.update({"required_receipts": inherited, "status": "QUEUED"})
        self.plan.units[substitute.work_id] = row
        blocked["status"] = "SUBSTITUTED"
        self._replan("BLOCKED_PATH_SUBSTITUTED", {"blocked": blocked_work_id, "substitute": substitute.work_id})
        return row

    def mark_verified(self, work_id: str, receipts: dict[str, Any]) -> dict[str, Any]:
        row = self.plan.units[work_id]
        missing = sorted(set(row["required_receipts"]) - set(receipts))
        if missing:
            row["status"] = "PARTIALLY_VERIFIED"
            return {"work_id": work_id, "status": row["status"], "missing": missing}
        row["status"] = "VERIFIED"
        for receipt_type, body in receipts.items():
            receipt_id = f"{work_id}:{receipt_type}"
            receipt = {"receipt_id": receipt_id, "work_id": work_id, "type": receipt_type, "body": body}
            receipt["sha256"] = digest(receipt)
            self.plan.receipts[receipt_id] = receipt
        self._record("WORK_VERIFIED", {"work_id": work_id, "receipts": sorted(receipts)})
        return {"work_id": work_id, "status": "VERIFIED", "missing": []}

    def replan_failed(self, work_id: str, repair_work: WorkUnit) -> dict[str, Any]:
        failed = self.plan.units[work_id]
        failed["status"] = "FAILED"
        inherited = tuple(sorted(set(repair_work.required_receipts) | set(failed["required_receipts"])))
        row = asdict(repair_work)
        row.update({"required_receipts": inherited, "status": "QUEUED"})
        self.plan.units[repair_work.work_id] = row
        self._replan("FAILED_PATH_REPLANNED", {"failed": work_id, "repair": repair_work.work_id})
        return row

    def evaluate_closure(self) -> dict[str, Any]:
        active = [row for row in self.plan.units.values() if row["status"] not in {"SUBSTITUTED"}]
        incomplete = sorted(row["work_id"] for row in active if row["status"] != "VERIFIED")
        present_types = {receipt["type"] for receipt in self.plan.receipts.values()}
        missing_mission_receipts = sorted(set(self.goal.success_receipts) - present_types)
        closed = not incomplete and not missing_mission_receipts
        self.plan.closure_state = "PROOF_CLOSED" if closed else "OPEN"
        result = {
            "mission_id": self.goal.mission_id,
            "state": self.plan.closure_state,
            "incomplete_work": incomplete,
            "missing_receipts": missing_mission_receipts,
            "plan_revision": self.plan.revision,
        }
        result["closure_hash"] = digest(result)
        self._record("MISSION_CLOSURE_EVALUATED", result)
        return result

    def _replan(self, event_type: str, payload: dict[str, Any]) -> None:
        self.plan.revision += 1
        self._record(event_type, payload | {"revision": self.plan.revision})

    def _record(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {"event_type": event_type, "payload": payload, "sequence": len(self.history) + 1}
        event["event_hash"] = digest(event)
        self.history.append(event)
