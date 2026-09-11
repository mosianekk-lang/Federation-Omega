from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum

from .epistemic import ClaimStatus


class RiskLevel(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class Decision(str, Enum):
    PROCEED = "PROCEED"
    SHADOW_ONLY = "SHADOW_ONLY"
    SEEK_EVIDENCE = "SEEK_EVIDENCE"
    RUN_EXPERIMENT = "RUN_EXPERIMENT"
    HOLD = "HOLD"


@dataclass(frozen=True)
class ActionRisk:
    failure_cost: float
    irreversibility: float
    external_effect: float
    safety_impact: float

    @staticmethod
    def _bounded(value: float) -> float:
        return max(0.0, min(1.0, value))

    @property
    def level(self) -> RiskLevel:
        peak = max(
            self._bounded(self.failure_cost),
            self._bounded(self.irreversibility),
            self._bounded(self.external_effect),
            self._bounded(self.safety_impact),
        )
        if peak >= 0.85:
            return RiskLevel.CRITICAL
        if peak >= 0.60:
            return RiskLevel.HIGH
        if peak >= 0.30:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW


@dataclass(frozen=True)
class DecisionAdvice:
    decision: Decision
    risk_level: RiskLevel
    reason: str


class MetacognitionGovernor:
    """Convert epistemic state and action risk into an execution posture.

    More reasoning tokens never upgrade evidence by themselves. High/critical
    actions require stronger epistemic state, and critical actions additionally
    require an independent verifier. Contested claims route to experiment rather
    than forced model consensus.
    """

    _ORDER = {
        ClaimStatus.UNKNOWN: 0,
        ClaimStatus.POSSIBLE: 1,
        ClaimStatus.LIKELY: 2,
        ClaimStatus.KNOWN: 3,
    }

    _REQUIRED = {
        RiskLevel.LOW: ClaimStatus.POSSIBLE,
        RiskLevel.MEDIUM: ClaimStatus.LIKELY,
        RiskLevel.HIGH: ClaimStatus.KNOWN,
        RiskLevel.CRITICAL: ClaimStatus.KNOWN,
    }

    def advise(
        self,
        claim_status: ClaimStatus,
        risk: ActionRisk,
        *,
        independent_verifier: bool = False,
        experiment_available: bool = True,
    ) -> DecisionAdvice:
        level = risk.level

        if claim_status == ClaimStatus.STALE:
            return DecisionAdvice(Decision.SEEK_EVIDENCE, level, "evidence is stale")
        if claim_status == ClaimStatus.CONTESTED:
            if experiment_available:
                return DecisionAdvice(
                    Decision.RUN_EXPERIMENT,
                    level,
                    "material counterevidence exists; discriminate experimentally",
                )
            return DecisionAdvice(Decision.HOLD, level, "contested claim without qualified experiment")
        if claim_status == ClaimStatus.UNKNOWN:
            return DecisionAdvice(Decision.SEEK_EVIDENCE, level, "claim is unknown")

        required = self._REQUIRED[level]
        if self._ORDER[claim_status] < self._ORDER[required]:
            # Low-impact reversible work may be exercised only in shadow when it
            # is close to the floor; external effect is still forbidden.
            if (
                level == RiskLevel.LOW
                and claim_status == ClaimStatus.POSSIBLE
                and risk.irreversibility < 0.25
                and risk.external_effect < 0.25
            ):
                return DecisionAdvice(Decision.SHADOW_ONLY, level, "insufficient evidence for real effect")
            return DecisionAdvice(
                Decision.SEEK_EVIDENCE,
                level,
                f"{claim_status.value} is below required {required.value}",
            )

        if level == RiskLevel.CRITICAL and not independent_verifier:
            return DecisionAdvice(
                Decision.HOLD,
                level,
                "critical action requires independent verification",
            )

        return DecisionAdvice(Decision.PROCEED, level, "epistemic and verification floor satisfied")
