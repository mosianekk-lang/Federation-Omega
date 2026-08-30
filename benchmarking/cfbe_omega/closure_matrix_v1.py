from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .cycle_preflight_v1 import load_cycle_preflight


MATRIX_PATH = Path(__file__).with_name("convergence_fabric_v2_capability_closure_matrix_v1.json")
ACTIONABLE_STATES = frozenset({"REUSE_NOW", "INTEGRATE", "EXTEND", "BUILD"})
HELD_STATES = frozenset({"DATA_NEEDED", "PROVIDER_GATED", "VALUE_GATED", "HOLD"})


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ClosureDecision:
    capability_id: str
    capability: str
    rail: str
    closure_state: str
    next_action: str
    dependencies: tuple[str, ...]
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "capability": self.capability,
            "rail": self.rail,
            "closure_state": self.closure_state,
            "next_action": self.next_action,
            "dependencies": list(self.dependencies),
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True, slots=True)
class ClosureWaveReceipt:
    schema: str
    matrix_sha256: str
    selected: tuple[ClosureDecision, ...]
    held: tuple[ClosureDecision, ...]
    selected_per_rail: Mapping[str, int]
    wip_limit_per_rail: int
    provider_effect_authorized: bool
    financial_effect_authorized: bool
    receipt_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "matrix_sha256": self.matrix_sha256,
            "selected": [x.to_dict() for x in self.selected],
            "held": [x.to_dict() for x in self.held],
            "selected_per_rail": dict(self.selected_per_rail),
            "wip_limit_per_rail": self.wip_limit_per_rail,
            "provider_effect_authorized": self.provider_effect_authorized,
            "financial_effect_authorized": self.financial_effect_authorized,
            "receipt_sha256": self.receipt_sha256,
        }


def load_matrix(path: str | Path = MATRIX_PATH) -> dict[str, Any]:
    load_cycle_preflight()
    matrix = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_matrix(matrix)
    return matrix


def validate_matrix(matrix: Mapping[str, Any]) -> None:
    if matrix.get("schema") != "CFBE-OMEGA-CONVERGENCE-CAPABILITY-CLOSURE-MATRIX-V1":
        raise ValueError("CFBE_CLOSURE_MATRIX_SCHEMA_MISMATCH")
    rows = matrix.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("CFBE_CLOSURE_MATRIX_ROWS_REQUIRED")
    ids = [str(row.get("id", "")) for row in rows]
    if any(not item for item in ids) or len(set(ids)) != len(ids):
        raise ValueError("CFBE_CLOSURE_MATRIX_CAPABILITY_IDS_INVALID")
    known = set(ids)
    rails = set((matrix.get("rails") or {}).keys())
    allowed_states = set(matrix.get("closure_states") or [])
    if not rails or not allowed_states:
        raise ValueError("CFBE_CLOSURE_MATRIX_ENUMS_REQUIRED")
    for row in rows:
        if row.get("rail") not in rails:
            raise ValueError(f"CFBE_CLOSURE_MATRIX_UNKNOWN_RAIL:{row.get('id')}")
        if row.get("closure_state") not in allowed_states:
            raise ValueError(f"CFBE_CLOSURE_MATRIX_UNKNOWN_STATE:{row.get('id')}")
        deps = row.get("dependencies") or []
        if not isinstance(deps, list) or any(dep not in known for dep in deps):
            raise ValueError(f"CFBE_CLOSURE_MATRIX_UNKNOWN_DEPENDENCY:{row.get('id')}")
        if row.get("id") in deps:
            raise ValueError(f"CFBE_CLOSURE_MATRIX_SELF_DEPENDENCY:{row.get('id')}")
        if not str(row.get("next_action", "")).strip():
            raise ValueError(f"CFBE_CLOSURE_MATRIX_NEXT_ACTION_REQUIRED:{row.get('id')}")
    _assert_acyclic(rows)
    scheduler = matrix.get("scheduler_policy") or {}
    if int(scheduler.get("wip_limit_per_rail", 0)) != 2:
        raise ValueError("CFBE_CLOSURE_MATRIX_WIP_LIMIT_MUST_BE_TWO")
    if int(scheduler.get("primary_build_limit_per_rail", 0)) != 1:
        raise ValueError("CFBE_CLOSURE_MATRIX_PRIMARY_LIMIT_MUST_BE_ONE")
    if int(scheduler.get("challenger_limit_per_rail", 0)) != 1:
        raise ValueError("CFBE_CLOSURE_MATRIX_CHALLENGER_LIMIT_MUST_BE_ONE")
    if scheduler.get("blocked_lane_isolation") is not True:
        raise ValueError("CFBE_CLOSURE_MATRIX_BLOCKED_LANE_ISOLATION_REQUIRED")
    truth = matrix.get("truth_boundary") or {}
    if truth.get("live_financial_effect_requires_separate_explicit_authority") is not True:
        raise ValueError("CFBE_CLOSURE_MATRIX_FINANCIAL_AUTHORITY_BOUNDARY_REQUIRED")


def _assert_acyclic(rows: Iterable[Mapping[str, Any]]) -> None:
    graph = {str(row["id"]): tuple(row.get("dependencies") or ()) for row in rows}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ValueError("CFBE_CLOSURE_MATRIX_DEPENDENCY_CYCLE")
        if node in visited:
            return
        visiting.add(node)
        for dep in graph[node]:
            visit(dep)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def _decision(row: Mapping[str, Any], blockers: Iterable[str] = ()) -> ClosureDecision:
    return ClosureDecision(
        capability_id=str(row["id"]),
        capability=str(row["capability"]),
        rail=str(row["rail"]),
        closure_state=str(row["closure_state"]),
        next_action=str(row["next_action"]),
        dependencies=tuple(str(x) for x in row.get("dependencies") or ()),
        blockers=tuple(sorted(set(str(x) for x in blockers))),
    )


def first_closure(matrix: Mapping[str, Any]) -> ClosureDecision:
    validate_matrix(matrix)
    target = str((matrix.get("first_closure_slice") or {}).get("target", ""))
    rows = {str(row["id"]): row for row in matrix["rows"]}
    if target not in rows:
        raise ValueError("CFBE_CLOSURE_MATRIX_FIRST_TARGET_UNKNOWN")
    row = rows[target]
    if row["closure_state"] not in ACTIONABLE_STATES:
        raise ValueError("CFBE_CLOSURE_MATRIX_FIRST_TARGET_NOT_ACTIONABLE")
    return _decision(row)


def plan_wave(matrix: Mapping[str, Any], *, active_ids: Iterable[str] = ()) -> ClosureWaveReceipt:
    validate_matrix(matrix)
    active = set(str(x) for x in active_ids)
    rows = list(matrix["rows"])
    priority = list(matrix.get("highest_leverage_red_cells") or [])
    priority_rank = {item: index for index, item in enumerate(priority)}
    rows.sort(key=lambda row: (priority_rank.get(str(row["id"]), 10_000), str(row["rail"]), str(row["id"])))
    wip_limit = int(matrix["scheduler_policy"]["wip_limit_per_rail"])
    selected: list[ClosureDecision] = []
    held: list[ClosureDecision] = []
    counts = {rail: 0 for rail in matrix["rails"]}

    for row in rows:
        cid = str(row["id"])
        rail = str(row["rail"])
        state = str(row["closure_state"])
        blockers: list[str] = []
        if cid in active:
            blockers.append("ALREADY_ACTIVE")
        if state in HELD_STATES:
            blockers.append(state)
        if state == "RETIRE_DUPLICATE":
            blockers.append("MORTALITY_DECISION_ONLY")
        if counts[rail] >= wip_limit:
            blockers.append("RAIL_WIP_LIMIT")
        decision = _decision(row, blockers)
        if blockers or state not in ACTIONABLE_STATES:
            held.append(decision)
            continue
        selected.append(decision)
        counts[rail] += 1

    body = {
        "schema": "CFBE-OMEGA-CLOSURE-WAVE-RECEIPT-V1",
        "matrix_sha256": _sha(matrix),
        "selected": [x.to_dict() for x in selected],
        "held": [x.to_dict() for x in held],
        "selected_per_rail": counts,
        "wip_limit_per_rail": wip_limit,
        "provider_effect_authorized": False,
        "financial_effect_authorized": False,
    }
    return ClosureWaveReceipt(
        schema=body["schema"],
        matrix_sha256=body["matrix_sha256"],
        selected=tuple(selected),
        held=tuple(held),
        selected_per_rail=dict(counts),
        wip_limit_per_rail=wip_limit,
        provider_effect_authorized=False,
        financial_effect_authorized=False,
        receipt_sha256=_sha(body),
    )


__all__ = [
    "ACTIONABLE_STATES",
    "HELD_STATES",
    "MATRIX_PATH",
    "ClosureDecision",
    "ClosureWaveReceipt",
    "first_closure",
    "load_matrix",
    "plan_wave",
    "validate_matrix",
]
