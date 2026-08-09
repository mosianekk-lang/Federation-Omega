from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CognitiveHealth:
    unsupported_assertion_rate: float
    provenance_coverage: float
    calibration_error: float
    duplicate_function_ratio: float
    reasoning_debt: float
    completion_readback_rate: float

    def score(self) -> float:
        positive = (
            self.provenance_coverage * 0.30
            + (1.0 - self.calibration_error) * 0.20
            + self.completion_readback_rate * 0.20
            + (1.0 - self.unsupported_assertion_rate) * 0.15
            + (1.0 - self.duplicate_function_ratio) * 0.10
            + (1.0 - self.reasoning_debt) * 0.05
        )
        return round(max(0.0, min(1.0, positive)), 6)

    def unhealthy_dimensions(self, threshold: float = 0.75) -> tuple[str, ...]:
        dimensions = {
            "unsupported_assertion_rate": 1.0 - self.unsupported_assertion_rate,
            "provenance_coverage": self.provenance_coverage,
            "calibration": 1.0 - self.calibration_error,
            "semantic_compaction": 1.0 - self.duplicate_function_ratio,
            "reasoning_debt": 1.0 - self.reasoning_debt,
            "completion_readback": self.completion_readback_rate,
        }
        return tuple(sorted(name for name, value in dimensions.items() if value < threshold))
