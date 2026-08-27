from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Mapping

from .models import stable_sha256


ADMITTED_RESEARCH_STATE = "RESEARCH_ADMITTED"


@dataclass(frozen=True)
class QuantResearchEvidence:
    strategy_id: str
    instrument_id: str
    evidence_ref: str
    research_state: str
    expected_return_pct: float
    benchmark_return_pct: float
    maximum_drawdown_pct: float
    sharpe_ratio: float
    sample_trades: int
    robustness_score: float
    regime_fit: float
    liquidity_quality: float
    uncertainty: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def excess_return_pct(self) -> float:
        return float(self.expected_return_pct) - float(self.benchmark_return_pct)

    def validate(self) -> None:
        if not self.strategy_id or not self.instrument_id or not self.evidence_ref:
            raise ValueError("strategy_id, instrument_id and evidence_ref are required")
        if self.sample_trades < 0:
            raise ValueError("sample_trades cannot be negative")
        for name in ("robustness_score", "regime_fit", "liquidity_quality", "uncertainty"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.maximum_drawdown_pct < 0:
            raise ValueError("maximum_drawdown_pct cannot be negative")

    def fingerprint(self) -> str:
        self.validate()
        return stable_sha256(asdict(self))


@dataclass(frozen=True)
class CapitalIntent:
    intent_id: str
    portfolio_id: str
    strategy_id: str
    instrument_id: str
    target_weight: float
    maximum_weight: float
    evidence_ref: str
    confidence: float
    constraints: Mapping[str, Any]
    expires_at: str
    status: str = "PREPARED"
    executable: bool = False
    financial_effect: bool = False

    def validate(self) -> None:
        if not self.intent_id or not self.portfolio_id or not self.strategy_id or not self.instrument_id:
            raise ValueError("capital intent identity fields are required")
        if not self.evidence_ref:
            raise ValueError("capital intent requires evidence_ref")
        if not 0.0 <= float(self.target_weight) <= 1.0:
            raise ValueError("target_weight must be between 0 and 1")
        if not 0.0 <= float(self.maximum_weight) <= 1.0:
            raise ValueError("maximum_weight must be between 0 and 1")
        if self.target_weight > self.maximum_weight:
            raise ValueError("target_weight cannot exceed maximum_weight")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.executable or self.financial_effect:
            raise PermissionError("CIOS_CAPITAL_INTENT_MUST_BE_NON_EXECUTABLE")
        forbidden = {"order_id", "order_type", "limit_price", "stop_price", "api_key", "api_secret", "withdrawal_address"}
        if forbidden.intersection(self.constraints):
            raise PermissionError("CIOS_CAPITAL_INTENT_CONTAINS_EXECUTION_FIELD")
        expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        if expires.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")

    def fingerprint(self) -> str:
        self.validate()
        return stable_sha256(asdict(self))


class CapitalIntentEngine:
    """Converts admitted portfolio decisions into non-executable capital intent only."""

    def prepare(
        self,
        *,
        portfolio_id: str,
        evidence: QuantResearchEvidence,
        target_weight: float,
        maximum_weight: float,
        confidence: float,
        expires_at: str,
        constraints: Mapping[str, Any] | None = None,
    ) -> CapitalIntent:
        evidence.validate()
        if evidence.research_state != ADMITTED_RESEARCH_STATE:
            raise PermissionError("CAPITAL_INTENT_REQUIRES_RESEARCH_ADMISSION")
        if evidence.excess_return_pct <= 0:
            raise PermissionError("CAPITAL_INTENT_REQUIRES_POSITIVE_EXCESS_RETURN")
        payload = {
            "portfolio_id": portfolio_id,
            "strategy_id": evidence.strategy_id,
            "instrument_id": evidence.instrument_id,
            "target_weight": float(target_weight),
            "maximum_weight": float(maximum_weight),
            "evidence_ref": evidence.evidence_ref,
            "confidence": float(confidence),
            "constraints": dict(constraints or {}),
            "expires_at": expires_at,
        }
        intent = CapitalIntent(intent_id=stable_sha256(payload), **payload)
        intent.validate()
        return intent


def utc_expiry(hours_from_now: int = 24) -> str:
    if hours_from_now <= 0:
        raise ValueError("hours_from_now must be positive")
    from datetime import timedelta
    return (datetime.now(timezone.utc) + timedelta(hours=hours_from_now)).isoformat()
