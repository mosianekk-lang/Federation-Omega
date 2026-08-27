"""Deterministic experiment identity helpers for the Federation LONA Quant Node.

This module deliberately contains no broker execution. It fingerprints the complete
research contract so results cannot be compared as equivalent when code, data,
fees, leverage, dates, frequency, or parameters differ.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ExperimentContract:
    strategy_code_sha256: str
    data_ids: Sequence[str]
    frequency: str
    start_date: str
    end_date: str
    initial_cash: float
    commission: float
    leverage: float
    buy_on_close: bool
    parameters: Mapping[str, Any]

    def canonical_payload(self) -> str:
        payload = asdict(self)
        payload["data_ids"] = sorted(payload["data_ids"])
        payload["parameters"] = dict(sorted(payload["parameters"].items()))
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_payload().encode("utf-8")).hexdigest()


def admission_state(*, report_status: str, source_readback_match: bool, full_report_read: bool) -> str:
    """Return a proof-bound capability state; never equate dispatch with completion."""
    if report_status == "FAILED":
        return "FAILED"
    if report_status != "COMPLETED":
        return "DISPATCHED_NOT_VERIFIED"
    if not source_readback_match or not full_report_read:
        return "COMPLETED_UNVERIFIED"
    return "CANARY_EXECUTION_VERIFIED"
