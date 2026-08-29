from __future__ import annotations

import json
from pathlib import Path


CONTRACT_PATH = Path(__file__).with_name("cycle_preflight_v1.json")


def load_cycle_preflight() -> dict[str, object]:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if contract.get("schema") != "CFBE-CYCLE-PREFLIGHT-1":
        raise ValueError("CFBE_CYCLE_PREFLIGHT_SCHEMA_MISMATCH")
    order = contract.get("preflight_order")
    if not isinstance(order, list) or not order:
        raise ValueError("CFBE_CYCLE_PREFLIGHT_ORDER_REQUIRED")
    if order[0] != "FRESH_READ_CURRENT_MAIN":
        raise ValueError("CFBE_CYCLE_PREFLIGHT_MUST_START_FRESH")
    if order[-1] != "ONLY_THEN_CONSIDER_NEW_ARCHITECTURE":
        raise ValueError("CFBE_CYCLE_PREFLIGHT_ARCHITECTURE_ORDER_VIOLATION")
    gates = contract.get("gates")
    if not isinstance(gates, dict):
        raise ValueError("CFBE_CYCLE_PREFLIGHT_GATES_REQUIRED")
    required_true = (
        "critical_current_regression_blocks_new_architecture",
        "historical_green_tranche_is_not_current_terminal_truth",
        "stale_state_fencing_required",
        "source_readiness_without_real_evidence_is_non_promoting",
        "pr_open_requires_stable_self_reviewed_branch",
    )
    if any(gates.get(key) is not True for key in required_true):
        raise ValueError("CFBE_CYCLE_PREFLIGHT_REQUIRED_GATE_DISABLED")
    return contract


__all__ = ["CONTRACT_PATH", "load_cycle_preflight"]
