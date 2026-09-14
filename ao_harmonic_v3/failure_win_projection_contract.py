from __future__ import annotations

"""Canonical behavior-proof contract for source and Google Sheets projection.

The source compiler and the live provider projection must enforce the same
behavioral proof boundary. These helpers emit the exact formula shape exercised
by the provider-native parity canary; they do not mutate Sheets or grant maturity.
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
PROOF_BOOLEAN_FIRST_COLUMN = EVENT_COLUMNS[PROOF_BOOLEAN_COLUMNS[0]]
PROOF_BOOLEAN_LAST_COLUMN = EVENT_COLUMNS[PROOF_BOOLEAN_COLUMNS[-1]]
PROOF_BOOLEAN_COUNT = len(PROOF_BOOLEAN_COLUMNS)


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


def behavior_projection_formula(*, sheet_name: str = EVENT_SHEET) -> str:
    """Provider-proven formula: full proof graph plus invocation/readback/current/refs."""
    sheet = _sheet_ref(sheet_name)
    return (
        '=MAP(E2:E,G2:G,LAMBDA(e,ver,IF(e="","",IF(ver<>"2.0.0",FALSE,'
        f'IFNA(LET(r,FILTER({sheet}!G$2:Y,{sheet}!A$2:A=e),'
        'AND(INDEX(r,1,1),INDEX(r,1,2),INDEX(r,1,3),INDEX(r,1,4),INDEX(r,1,5)<>"",'
        f'COUNTIF(FILTER({sheet}!L$2:W,{sheet}!A$2:A=e),TRUE)={PROOF_BOOLEAN_COUNT},'
        f'INDEX(r,1,18)>={REQUIRED_REPEATED_SUCCESSES},INDEX(r,1,19)>={REQUIRED_SOAK_SECONDS})),FALSE)))))'
    )


def receiver_state_formula(*, sheet_name: str = EVENT_SHEET) -> str:
    """Provider-proven state projection; incomplete raw claims cannot self-promote."""
    sheet = _sheet_ref(sheet_name)
    return (
        '=MAP(A2:A,E2:E,G2:G,H2:H,I2:I,J2:J,K2:K,L2:L,LAMBDA(s,e,ver,ki,bp,ir,cur,refs,'
        'IF(s="","",IF(e="","REGISTERED_V2_BEHAVIOR_PENDING",IF(ver="2.0.0",'
        'IF(AND(ki,bp,ir,cur,refs<>""),"V2_BEHAVIOR_PROVEN",'
        f'IF(AND(IFNA(XLOOKUP(e,{sheet}!A$2:A,{sheet}!H$2:H,FALSE),FALSE),'
        f'IFNA(AND(COUNTIF(FILTER({sheet}!L$2:W,{sheet}!A$2:A=e),TRUE)={PROOF_BOOLEAN_COUNT},'
        f'XLOOKUP(e,{sheet}!A$2:A,{sheet}!X$2:X,0)>={REQUIRED_REPEATED_SUCCESSES},'
        f'XLOOKUP(e,{sheet}!A$2:A,{sheet}!Y$2:Y,0)>={REQUIRED_SOAK_SECONDS}),FALSE)=FALSE),'
        '"V2_BEHAVIOR_CLAIM_PROOF_INCOMPLETE",'
        'IF(ki,"V2_INVOKED_PROOF_OPEN","V2_EVENT_PRESENT_INVOCATION_OPEN"))),'
        f'IF(ver="1.0.0",IF(IFNA(XLOOKUP(e,{sheet}!A$2:A,{sheet}!H$2:H,FALSE),FALSE),'
        '"V1_BEHAVIOR_PROVEN_V2_PENDING","HISTORICAL_EVENT_V2_PENDING"),'
        '"HISTORICAL_EVENT_V2_PENDING"))))))'
    )


def truth_boundary_formula() -> str:
    return '=ARRAYFORMULA(IF(A2:A="","","Receiver registration or a raw behavior flag is not behavioral proof. V2 promotion requires the complete receiver-local proof graph, current independent readback, evidence refs, at least 3 distinct successes and at least 300 seconds soak."))'
