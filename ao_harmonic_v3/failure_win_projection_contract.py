from __future__ import annotations

"""Canonical behavior-proof contract for source and Google Sheets projection.

The source compiler and the live provider projection must enforce the same
behavioral proof boundary. These helpers do not mutate Google Sheets or grant
receiver maturity.
"""

from typing import Any, Mapping

EVENT_SHEET = "Failure-Win Events v2"
REQUIRED_REPEATED_SUCCESSES = 3
REQUIRED_SOAK_SECONDS = 300

PROOF_BOOLEAN_GATES = (
    ("FAILURE_FACT_PRESERVED", ("failure_fact_preserved",)),
    ("CAUSAL_FALSIFICATION", ("causal_falsification", "falsification_executed")),
    ("MATERIALLY_DIFFERENT_ROUTE", ("different_route", "materially_different_route")),
    ("VECTOR_GATE", ("vector_gate", "vector_gate_passed")),
    ("FAILURE_FIRST", ("failure_first", "failure_first_test_passed")),
    ("HEALTHY_PATH", ("healthy_path", "healthy_path_test_passed")),
    ("ROLLBACK", ("rollback", "rollback_test_passed")),
    ("FORWARD_CANARY", ("forward_canary", "forward_canary_passed")),
    ("SEMANTIC_READBACK", ("semantic_readback", "independent_semantic_readback")),
    ("POSITIVE_VALUE", ("positive_value",)),
    ("NO_REGRESSION", ("no_regression",)),
    ("NO_BURDEN_INCREASE", ("no_burden_increase", "owner_burden_not_increased")),
)

EVENT_COLUMNS = {
    "event_id": "A",
    "kernel_invoked": "G",
    "behavior_claim": "H",
    "independent_readback": "I",
    "current": "J",
    "evidence_refs": "K",
    "failure_fact_preserved": "L",
    "causal_falsification": "M",
    "different_route": "N",
    "vector_gate": "O",
    "failure_first": "P",
    "healthy_path": "Q",
    "rollback": "R",
    "forward_canary": "S",
    "semantic_readback": "T",
    "positive_value": "U",
    "no_regression": "V",
    "no_burden_increase": "W",
    "repeated_successes": "X",
    "soak_seconds": "Y",
}

PROOF_BOOLEAN_COLUMNS = tuple(aliases[0] for _, aliases in PROOF_BOOLEAN_GATES)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).upper() in {"TRUE", "YES", "1", "VERIFIED"}


def _number(value: Any, default: float = 0.0) -> float:
    if value is None or _text(value) == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _first(raw: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in raw:
            return raw.get(key)
    return None


def behavior_proof_missing(event: Mapping[str, Any]) -> tuple[str, ...]:
    """Return exact v2 behavior gates missing from one persisted event."""
    missing: list[str] = []
    for label, aliases in PROOF_BOOLEAN_GATES:
        if not _truthy(_first(event, *aliases)):
            missing.append(label)
    repeated = int(_number(_first(event, "repeated_successes", "repeat_count"), 0.0))
    if repeated < REQUIRED_REPEATED_SUCCESSES:
        missing.append(f"REPEATED_SUCCESSES<{REQUIRED_REPEATED_SUCCESSES}")
    soak = _number(_first(event, "soak_seconds", "soak"), 0.0)
    if soak < REQUIRED_SOAK_SECONDS:
        missing.append(f"SOAK_SECONDS<{REQUIRED_SOAK_SECONDS}")
    return tuple(missing)


def _sheet_ref(sheet_name: str) -> str:
    return "'" + sheet_name.replace("'", "''") + "'"


def _lookup(event_expr: str, column: str, *, sheet_name: str, default: str) -> str:
    sheet = _sheet_ref(sheet_name)
    return f"IFNA(XLOOKUP({event_expr},{sheet}!A$2:A,{sheet}!{column}$2:{column},{default}),{default})"


def _proof_complete_expression(event_expr: str, *, sheet_name: str) -> str:
    bindings = [
        ("raw_claim_ok", _lookup(event_expr, EVENT_COLUMNS["behavior_claim"], sheet_name=sheet_name, default="FALSE")),
    ]
    for index, key in enumerate(PROOF_BOOLEAN_COLUMNS, start=1):
        bindings.append(
            (
                f"gate_{index}_ok",
                _lookup(event_expr, EVENT_COLUMNS[key], sheet_name=sheet_name, default="FALSE"),
            )
        )
    bindings.extend(
        [
            ("repeat_count_ok", _lookup(event_expr, EVENT_COLUMNS["repeated_successes"], sheet_name=sheet_name, default="0")),
            ("soak_seconds_ok", _lookup(event_expr, EVENT_COLUMNS["soak_seconds"], sheet_name=sheet_name, default="0")),
        ]
    )
    let_bindings = ",".join(f"{name},{value}" for name, value in bindings)
    boolean_names = [
        "raw_claim_ok",
        *[f"gate_{index}_ok" for index in range(1, len(PROOF_BOOLEAN_COLUMNS) + 1)],
    ]
    all_terms = ",".join(
        [
            *boolean_names,
            f"repeat_count_ok>={REQUIRED_REPEATED_SUCCESSES}",
            f"soak_seconds_ok>={REQUIRED_SOAK_SECONDS}",
        ]
    )
    return f"LET({let_bindings},AND({all_terms}))"


def behavior_projection_formula(*, sheet_name: str = EVENT_SHEET) -> str:
    """Project Behavior Proven only when proof graph and outer gates all pass."""
    proof_complete = _proof_complete_expression("e", sheet_name=sheet_name)
    invoked = _lookup("e", EVENT_COLUMNS["kernel_invoked"], sheet_name=sheet_name, default="FALSE")
    readback = _lookup("e", EVENT_COLUMNS["independent_readback"], sheet_name=sheet_name, default="FALSE")
    current = _lookup("e", EVENT_COLUMNS["current"], sheet_name=sheet_name, default="FALSE")
    refs = _lookup("e", EVENT_COLUMNS["evidence_refs"], sheet_name=sheet_name, default='""')
    return (
        '=MAP(E2:E,G2:G,LAMBDA(e,ver,IF(e="","",IF(ver="2.0.0",'
        f'LET(proof_graph_ok,{proof_complete},invocation_ok,{invoked},readback_ok,{readback},'
        f'current_ok,{current},evidence_ref_ok,{refs},'
        'AND(proof_graph_ok,invocation_ok,readback_ok,current_ok,evidence_ref_ok<>"")),FALSE))))'
    )


def receiver_state_formula(*, sheet_name: str = EVENT_SHEET) -> str:
    """Expose incomplete raw claims without misclassifying outer-gate holds."""
    raw_behavior = _lookup("e", EVENT_COLUMNS["behavior_claim"], sheet_name=sheet_name, default="FALSE")
    proof_complete = _proof_complete_expression("e", sheet_name=sheet_name)
    v1_behavior = _lookup("e", EVENT_COLUMNS["behavior_claim"], sheet_name=sheet_name, default="FALSE")
    return (
        '=MAP(A2:A,E2:E,G2:G,H2:H,I2:I,J2:J,K2:K,L2:L,LAMBDA(s,e,ver,ki,bp,ir,cur,refs,'
        'IF(s="","",IF(e="","REGISTERED_V2_BEHAVIOR_PENDING",IF(ver="2.0.0",'
        f'LET(raw_claim,{raw_behavior},proof_graph_ok,{proof_complete},'
        'IF(AND(ki,bp,ir,cur,refs<>""),"V2_BEHAVIOR_PROVEN",'
        'IF(AND(raw_claim,proof_graph_ok=FALSE),"V2_BEHAVIOR_CLAIM_PROOF_INCOMPLETE",'
        'IF(ki,"V2_INVOKED_PROOF_OPEN","V2_EVENT_PRESENT_INVOCATION_OPEN")))),'
        f'IF(ver="1.0.0",IF({v1_behavior},"V1_BEHAVIOR_PROVEN_V2_PENDING","HISTORICAL_EVENT_V2_PENDING"),'
        '"HISTORICAL_EVENT_V2_PENDING"))))))'
    )


def truth_boundary_formula() -> str:
    return '=ARRAYFORMULA(IF(A2:A="","","Receiver registration or a raw behavior flag is not behavioral proof. V2 promotion requires the complete receiver-local proof graph, current independent readback, evidence refs, at least 3 distinct successes and at least 300 seconds soak."))'
