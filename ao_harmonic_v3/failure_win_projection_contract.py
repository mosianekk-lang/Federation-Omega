from __future__ import annotations

"""Canonical Google Sheets projection formulas for Failure-Win v2.

The source compiler and the live provider projection must enforce the same
behavioral proof boundary. These helpers generate formulas only; they do not
mutate Google Sheets or grant receiver maturity.
"""

EVENT_SHEET = "Failure-Win Events v2"
REQUIRED_REPEATED_SUCCESSES = 3
REQUIRED_SOAK_SECONDS = 300

# Event-ledger columns. Column H is the raw behavior claim; L:Y are proof fruit.
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

PROOF_BOOLEAN_COLUMNS = (
    "failure_fact_preserved",
    "causal_falsification",
    "different_route",
    "vector_gate",
    "failure_first",
    "healthy_path",
    "rollback",
    "forward_canary",
    "semantic_readback",
    "positive_value",
    "no_regression",
    "no_burden_increase",
)


def _sheet_ref(sheet_name: str) -> str:
    return "'" + sheet_name.replace("'", "''") + "'"


def _lookup(event_expr: str, column: str, *, sheet_name: str, default: str) -> str:
    sheet = _sheet_ref(sheet_name)
    return (
        f"IFNA(XLOOKUP({event_expr},{sheet}!A$2:A,"
        f"{sheet}!{column}$2:{column},{default}),{default})"
    )


def behavior_projection_formula(*, sheet_name: str = EVENT_SHEET) -> str:
    """Project Behavior Proven only when raw claim + every hard gate is true."""

    bindings = [
        ("rawbp", _lookup("e", EVENT_COLUMNS["behavior_claim"], sheet_name=sheet_name, default="FALSE")),
    ]
    for index, key in enumerate(PROOF_BOOLEAN_COLUMNS, start=1):
        bindings.append(
            (
                f"g{index}",
                _lookup("e", EVENT_COLUMNS[key], sheet_name=sheet_name, default="FALSE"),
            )
        )
    bindings.extend(
        [
            (
                "repeats",
                _lookup("e", EVENT_COLUMNS["repeated_successes"], sheet_name=sheet_name, default="0"),
            ),
            (
                "soak",
                _lookup("e", EVENT_COLUMNS["soak_seconds"], sheet_name=sheet_name, default="0"),
            ),
        ]
    )
    let_bindings = ",".join(f"{name},{value}" for name, value in bindings)
    boolean_names = ["rawbp", *[f"g{index}" for index in range(1, len(PROOF_BOOLEAN_COLUMNS) + 1)]]
    all_terms = ",".join(
        [*boolean_names, f"repeats>={REQUIRED_REPEATED_SUCCESSES}", f"soak>={REQUIRED_SOAK_SECONDS}"]
    )
    return (
        "=MAP(E2:E,G2:G,LAMBDA(e,ver,"
        "IF(e=\"\",\"\","
        f"IF(ver=\"2.0.0\",LET({let_bindings},AND({all_terms})),FALSE))))"
    )


def receiver_state_formula(*, sheet_name: str = EVENT_SHEET) -> str:
    """Expose incomplete raw claims without promoting them."""

    raw_behavior = _lookup("e", EVENT_COLUMNS["behavior_claim"], sheet_name=sheet_name, default="FALSE")
    return (
        "=MAP(A2:A,E2:E,G2:G,H2:H,I2:I,J2:J,K2:K,L2:L,"
        "LAMBDA(s,e,ver,ki,bp,ir,cur,refs,"
        "IF(s=\"\",\"\","
        "IF(e=\"\",\"REGISTERED_V2_BEHAVIOR_PENDING\","
        "IF(ver=\"2.0.0\","
        f"LET(rawbp,{raw_behavior},"
        "IF(AND(ki,bp,ir,cur,refs<>\"\"),\"V2_BEHAVIOR_PROVEN\","
        "IF(AND(rawbp,bp=FALSE),\"V2_BEHAVIOR_CLAIM_PROOF_INCOMPLETE\","
        "IF(ki,\"V2_INVOKED_PROOF_OPEN\",\"V2_EVENT_PRESENT_INVOCATION_OPEN\")))),"
        "IF(ver=\"1.0.0\","
        f"IF({_lookup('e', EVENT_COLUMNS['behavior_claim'], sheet_name=sheet_name, default='FALSE')},"
        "\"V1_BEHAVIOR_PROVEN_V2_PENDING\",\"HISTORICAL_EVENT_V2_PENDING\"),"
        "\"HISTORICAL_EVENT_V2_PENDING\")))))))"
    )


def truth_boundary_formula() -> str:
    return (
        '=ARRAYFORMULA(IF(A2:A="","",'
        '"Receiver registration or a raw behavior flag is not behavioral proof. "&'
        '"V2 promotion requires the complete receiver-local proof graph, current independent readback, "&'
        '"evidence refs, at least 3 distinct successes and at least 300 seconds soak."))'
    )
