from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


DEFAULT_SCORECARD = Path(__file__).resolve().parent / "PILOT_SCORECARD.json"


class PilotScorecard:
    def __init__(self, payload: Mapping[str, Any]):
        self.payload = dict(payload)
        metrics = [dict(item) for item in payload["mandatory_metrics"]]
        self.metrics = {str(item["metric"]): item for item in metrics}
        if len(self.metrics) != len(metrics):
            raise ValueError("mandatory metric names must be unique")

    @classmethod
    def load(cls, path: str | Path = DEFAULT_SCORECARD) -> "PilotScorecard":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def evaluate(self, observed: Mapping[str, Any]) -> dict[str, Any]:
        missing = [name for name in self.metrics if name not in observed or observed[name] is None]
        failures: list[str] = []
        for name, spec in self.metrics.items():
            if name in missing:
                continue
            value = observed[name]
            target = spec["target"]
            direction = spec["direction"]
            if direction == "higher_is_better" and float(value) < float(target):
                failures.append(name)
            elif direction == "lower_is_better" and float(value) > float(target):
                failures.append(name)
            elif direction == "must_equal" and value != target:
                failures.append(name)
        complete = not missing
        success = complete and not failures
        return {
            "pilot_result_available": complete,
            "pilot_success": success,
            "missing_metrics": missing,
            "failed_metrics": failures,
            "safe_public_claim": self.payload["safe_public_claim"],
            "truth_boundary": self.payload["truth_boundary"],
        }

    def claim_pilot_success(self, observed: Mapping[str, Any]) -> str:
        result = self.evaluate(observed)
        if not result["pilot_result_available"]:
            raise ValueError("PILOT_RESULT_UNAVAILABLE_MISSING_METRICS")
        if not result["pilot_success"]:
            raise ValueError("PILOT_ACCEPTANCE_NOT_MET")
        return "PILOT_ACCEPTANCE_MET"
