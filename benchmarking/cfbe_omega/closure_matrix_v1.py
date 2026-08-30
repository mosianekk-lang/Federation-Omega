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
    role: str = "PRIMARY"
    effective_state: str = ""
    rank_score: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "capability": self.capability,
            "rail": self.rail,
            "closure_state": self.closure_state,
            "next_action": self.next_action,
            "dependencies": list(self.dependencies),
            "blockers": list(self.blockers),
            "role": self.role,
            "effective_state": self.effective_state or self.closure_state,
            "rank_score": self.rank_score,
        }


@dataclass(frozen=True, slots=True)
class ClosureWaveReceipt:
    schema: str
    matrix_sha256: str
    selected: tuple[ClosureDecision, ...]
    held: tuple[ClosureDecision, ...]
    selected_per_rail: Mapping[str, int]
    selected_roles_per_rail: Mapping[str, Mapping[str, int]]
    active_per_rail: Mapping[str, int]
    completed_ids: tuple[str, ...]
    critical_regression_ids: tuple[str, ...]
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
            "selected_roles_per_rail": {
                rail: dict(counts) for rail, counts in self.selected_roles_per_rail.items()
            },
            "active_per_rail": dict(self.active_per_rail),
            "completed_ids": list(self.completed_ids),
            "critical_regression_ids": list(self.critical_regression_ids),
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


def _decision(
    row: Mapping[str, Any],
    blockers: Iterable[str] = (),
    *,
    role: str = "PRIMARY",
    effective_state: str | None = None,
    rank_score: float = 0.0,
) -> ClosureDecision:
    return ClosureDecision(
        capability_id=str(row["id"]),
        capability=str(row["capability"]),
        rail=str(row["rail"]),
        closure_state=str(row["closure_state"]),
        next_action=str(row["next_action"]),
        dependencies=tuple(str(x) for x in row.get("dependencies") or ()),
        blockers=tuple(sorted(set(str(x) for x in blockers))),
        role=role,
        effective_state=effective_state or str(row["closure_state"]),
        rank_score=round(float(rank_score), 9),
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


def _rank_scores(matrix: Mapping[str, Any]) -> dict[str, float]:
    rows = {str(row["id"]): row for row in matrix["rows"]}
    downstream = {
        cid: {other for other, row in rows.items() if cid in (row.get("dependencies") or ())}
        for cid in rows
    }

    def descendants(cid: str) -> set[str]:
        found: set[str] = set()
        pending = list(downstream[cid])
        while pending:
            item = pending.pop()
            if item in found:
                continue
            found.add(item)
            pending.extend(downstream[item])
        return found

    priority = tuple(str(x) for x in matrix.get("highest_leverage_red_cells") or ())
    priority_rank = {item: index for index, item in enumerate(priority)}
    effort_by_state = {"REUSE_NOW": 1.0, "INTEGRATE": 2.0, "EXTEND": 3.0, "BUILD": 4.0}
    scores: dict[str, float] = {}
    for cid, row in rows.items():
        unlocked = len(descendants(cid))
        mission_impact = 1.0 if cid in priority_rank else 0.5
        dependency_leverage = 1.0 + unlocked
        expected_value = 1.0 / (1.0 + priority_rank[cid]) if cid in priority_rank else 0.25
        unblock_value = 1.0 + unlocked
        expected_effort = effort_by_state.get(str(row["closure_state"]), 5.0)
        scores[cid] = round(
            mission_impact * dependency_leverage * expected_value * unblock_value / expected_effort,
            9,
        )
    return scores


def plan_wave(
    matrix: Mapping[str, Any],
    *,
    active_ids: Iterable[str] = (),
    completed_ids: Iterable[str] = (),
    roles: Mapping[str, str] | None = None,
    live_ready_ids: Iterable[str] = (),
    critical_regression_ids: Iterable[str] = (),
    readiness_blockers: Mapping[str, Iterable[str]] | None = None,
) -> ClosureWaveReceipt:
    validate_matrix(matrix)
    active = set(str(x) for x in active_ids)
    completed = set(str(x) for x in completed_ids)
    live_ready = set(str(x) for x in live_ready_ids)
    critical = set(str(x) for x in critical_regression_ids)
    role_by_id = {str(key): str(value).upper() for key, value in (roles or {}).items()}
    readiness_by_id = {
        str(key): tuple(str(item) for item in values)
        for key, values in (readiness_blockers or {}).items()
    }
    rows = list(matrix["rows"])
    row_by_id = {str(row["id"]): row for row in rows}
    known = set(row_by_id)
    for label, values in (
        ("ACTIVE", active),
        ("COMPLETED", completed),
        ("LIVE_READY", live_ready),
        ("CRITICAL", critical),
        ("ROLE", set(role_by_id)),
        ("READINESS", set(readiness_by_id)),
    ):
        unknown = values - known
        if unknown:
            raise ValueError(f"CFBE_CLOSURE_MATRIX_UNKNOWN_{label}_ID:{','.join(sorted(unknown))}")
    if any(role not in {"PRIMARY", "CHALLENGER"} for role in role_by_id.values()):
        raise ValueError("CFBE_CLOSURE_MATRIX_ROLE_INVALID")

    rank_scores = _rank_scores(matrix)
    rows.sort(
        key=lambda row: (
            0 if str(row["id"]) in critical else 1,
            -rank_scores[str(row["id"])],
            str(row["rail"]),
            str(row["id"]),
        )
    )
    wip_limit = int(matrix["scheduler_policy"]["wip_limit_per_rail"])
    primary_limit = int(matrix["scheduler_policy"]["primary_build_limit_per_rail"])
    challenger_limit = int(matrix["scheduler_policy"]["challenger_limit_per_rail"])
    selected: list[ClosureDecision] = []
    held: list[ClosureDecision] = []
    occupancy = {rail: 0 for rail in matrix["rails"]}
    selected_counts = {rail: 0 for rail in matrix["rails"]}
    active_counts = {rail: 0 for rail in matrix["rails"]}
    role_occupancy = {rail: {"PRIMARY": 0, "CHALLENGER": 0} for rail in matrix["rails"]}
    selected_role_counts = {rail: {"PRIMARY": 0, "CHALLENGER": 0} for rail in matrix["rails"]}
    for cid in sorted(active):
        rail = str(row_by_id[cid]["rail"])
        role = role_by_id.get(cid, "PRIMARY")
        occupancy[rail] += 1
        active_counts[rail] += 1
        role_occupancy[rail][role] += 1

    terminal = set(completed)
    terminal.update(str(row["id"]) for row in rows if row["closure_state"] == "REUSE_NOW")
    critical_rails = {str(row_by_id[cid]["rail"]) for cid in critical}

    for row in rows:
        cid = str(row["id"])
        rail = str(row["rail"])
        state = str(row["closure_state"])
        role = role_by_id.get(cid, "PRIMARY")
        effective_state = "INTEGRATE" if state in HELD_STATES and cid in live_ready else state
        blockers: list[str] = []
        blockers.extend(readiness_by_id.get(cid, ()))
        if cid in active:
            blockers.append("ALREADY_ACTIVE")
        if cid in completed:
            blockers.append("ALREADY_TERMINAL")
        if state in HELD_STATES and cid not in live_ready:
            blockers.append(state)
        if state == "RETIRE_DUPLICATE":
            blockers.append("MORTALITY_DECISION_ONLY")
        for dependency in row.get("dependencies") or ():
            if dependency not in terminal:
                blockers.append(f"DEPENDENCY_NOT_TERMINAL:{dependency}")
        if rail in critical_rails and cid not in critical:
            blockers.append("CRITICAL_REGRESSION_PREEMPTION")
        if occupancy[rail] >= wip_limit:
            blockers.append("RAIL_WIP_LIMIT")
        role_limit = primary_limit if role == "PRIMARY" else challenger_limit
        if role_occupancy[rail][role] >= role_limit:
            blockers.append(f"RAIL_{role}_LIMIT")
        decision = _decision(
            row,
            blockers,
            role=role,
            effective_state=effective_state,
            rank_score=rank_scores[cid],
        )
        if blockers or effective_state not in ACTIONABLE_STATES:
            held.append(decision)
            continue
        selected.append(decision)
        occupancy[rail] += 1
        selected_counts[rail] += 1
        role_occupancy[rail][role] += 1
        selected_role_counts[rail][role] += 1

    body = {
        "schema": "CFBE-OMEGA-CLOSURE-WAVE-RECEIPT-V1",
        "matrix_sha256": _sha(matrix),
        "selected": [x.to_dict() for x in selected],
        "held": [x.to_dict() for x in held],
        "selected_per_rail": selected_counts,
        "selected_roles_per_rail": selected_role_counts,
        "active_per_rail": active_counts,
        "completed_ids": sorted(completed),
        "critical_regression_ids": sorted(critical),
        "wip_limit_per_rail": wip_limit,
        "provider_effect_authorized": False,
        "financial_effect_authorized": False,
    }
    return ClosureWaveReceipt(
        schema=body["schema"],
        matrix_sha256=body["matrix_sha256"],
        selected=tuple(selected),
        held=tuple(held),
        selected_per_rail=dict(selected_counts),
        selected_roles_per_rail={rail: dict(values) for rail, values in selected_role_counts.items()},
        active_per_rail=dict(active_counts),
        completed_ids=tuple(sorted(completed)),
        critical_regression_ids=tuple(sorted(critical)),
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
