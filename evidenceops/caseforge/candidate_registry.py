from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


DEFAULT_REGISTER = Path(__file__).resolve().parent / "benchmarks" / "candidate_register_v1.json"


class CandidateRegistry:
    def __init__(self, payload: Mapping[str, Any]):
        self.payload = dict(payload)
        self.candidates = {str(c["candidate_id"]): dict(c) for c in payload["candidates"]}
        if len(self.candidates) != len(payload["candidates"]):
            raise ValueError("candidate IDs must be unique")
        for candidate in self.candidates.values():
            if candidate.get("state") != "HYPOTHESIS":
                raise ValueError("unbenchmarked candidates must begin as HYPOTHESIS")
            if candidate.get("provider_performance_verified"):
                raise ValueError("candidate register cannot self-verify provider performance")

    @classmethod
    def load(cls, path: str | Path = DEFAULT_REGISTER) -> "CandidateRegistry":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def promotion_decision(
        self,
        candidate_id: str,
        *,
        benchmark_receipt: Mapping[str, Any] | None = None,
        provider_readback_ref: str = "",
    ) -> dict[str, Any]:
        candidate = self.candidates[candidate_id]
        if not benchmark_receipt:
            return {"state": "HYPOTHESIS", "promoted": False, "reason": "PULSE_BENCHMARK_REQUIRED"}
        if benchmark_receipt.get("benchmark_id") != candidate["required_benchmark"]:
            return {"state": "HYPOTHESIS", "promoted": False, "reason": "WRONG_BENCHMARK"}
        if int(benchmark_receipt.get("fatal_failure_count", 1)) != 0:
            return {"state": "HYPOTHESIS", "promoted": False, "reason": "BENCHMARK_FATAL_FAILURES"}
        execution_state = benchmark_receipt.get("execution_state")
        if execution_state == "PROVIDER_VERIFIED" and not provider_readback_ref:
            return {"state": "HYPOTHESIS", "promoted": False, "reason": "PROVIDER_READBACK_REQUIRED"}
        if execution_state not in {"DETERMINISTIC_TEST_ONLY", "PROVIDER_VERIFIED"}:
            return {"state": "HYPOTHESIS", "promoted": False, "reason": "UNVERIFIED_EXECUTION_STATE"}
        return {
            "state": "BENCHMARKED_CANDIDATE",
            "promoted": True,
            "reason": "PULSE_BENCHMARK_PASSED",
            "provider_performance_verified": execution_state == "PROVIDER_VERIFIED" and bool(provider_readback_ref),
        }
