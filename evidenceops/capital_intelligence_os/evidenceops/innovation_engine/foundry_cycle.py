from __future__ import annotations

from typing import Any, Mapping

from .algorithms import sha256
from .foundry_finalize import finalize_foundry_cycle
from .foundry_inputs import build_foundry_results
from .foundry_model import FoundryCycleResult


def execute_foundry_cycle(self: Any, payload: Mapping[str, Any]) -> FoundryCycleResult:
    cycle_id = str(payload.get("cycle_id") or f"ALG-CYCLE-{sha256(payload)[:16].upper()}")
    evidence_refs = [str(item) for item in payload.get("evidence_refs", [])]
    results, learning_events, opportunity_result = build_foundry_results(self, payload, cycle_id, evidence_refs)
    return finalize_foundry_cycle(self, payload, cycle_id, evidence_refs, results, learning_events, opportunity_result)
