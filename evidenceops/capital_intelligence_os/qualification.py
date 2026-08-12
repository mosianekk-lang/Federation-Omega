from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import copy
import json

from .authority import AuthorityGuard
from .diligence import DiligenceEngine
from .models import (
    ActionDisposition,
    ActionRequest,
    AuthorityLevel,
    Domain,
    InformationClass,
    stable_sha256,
)
from .mvp_journey import MVPJourneyOrchestrator
from .qoe import (
    DebtLikeEngine,
    DebtLikeItem,
    EBITDAAdjustment,
    QualityOfEarningsEngine,
    WorkingCapitalNormalizer,
)
from .strategy import AcquisitionThesis, TargetCandidate, TargetScreenEngine
from .valuation import DCFEngine, EquityBridge, ForecastCashFlow, ReturnEngine


@dataclass(frozen=True)
class QualificationCheck:
    check_id: str
    passed: bool
    observed: object
    expected: object
    category: str
    fatal: bool = True


@dataclass(frozen=True)
class QualificationReport:
    schema: str
    qualification_class: str
    passed: bool
    score: float
    checks: tuple[QualificationCheck, ...]
    fatal_failures: tuple[str, ...]
    truth_boundary: str
    receipt_sha256: str


class _Recorder:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def record(self, **kwargs: Any) -> None:
        self.rows.append(dict(kwargs))


class InternalQualificationCourt:
    """Independent-oracle qualification for deterministic/synthetic CIOS behavior.

    This court is deliberately not a historical-deal calibration claim. It checks
    mathematical correctness, monotonic properties, fail-closed gates and
    counterfactual behavior using transparent synthetic cases.
    """

    def __init__(self, fixture_path: str | Path | None = None) -> None:
        self.fixture_path = Path(fixture_path) if fixture_path else (
            Path(__file__).parent / "fixtures" / "synthetic_mvp_deal_v1.json"
        )

    @staticmethod
    def _close(observed: float, expected: float, tolerance: float = 1e-6) -> bool:
        return abs(observed - expected) <= tolerance

    def run(self) -> QualificationReport:
        checks: list[QualificationCheck] = []

        dcf = DCFEngine()
        one_period = dcf.value([ForecastCashFlow(1, 100.0)], 0.10, 0.0)
        # Independent oracle: PV(100 in year 1) + PV(100/10% terminal value) = 1000.
        checks.append(QualificationCheck(
            "DCF_ANALYTIC_ORACLE",
            self._close(one_period.enterprise_value, 1000.0),
            round(one_period.enterprise_value, 8),
            1000.0,
            "VALUATION",
        ))
        lower_wacc = dcf.value([ForecastCashFlow(1, 100), ForecastCashFlow(2, 110)], 0.09, 0.02)
        higher_wacc = dcf.value([ForecastCashFlow(1, 100), ForecastCashFlow(2, 110)], 0.13, 0.02)
        checks.append(QualificationCheck(
            "DCF_WACC_MONOTONICITY",
            lower_wacc.enterprise_value > higher_wacc.enterprise_value,
            [round(lower_wacc.enterprise_value, 6), round(higher_wacc.enterprise_value, 6)],
            "lower WACC produces higher EV",
            "VALUATION",
        ))
        lower_growth = dcf.value([ForecastCashFlow(1, 100), ForecastCashFlow(2, 110)], 0.12, 0.01)
        higher_growth = dcf.value([ForecastCashFlow(1, 100), ForecastCashFlow(2, 110)], 0.12, 0.04)
        checks.append(QualificationCheck(
            "DCF_TERMINAL_GROWTH_MONOTONICITY",
            higher_growth.enterprise_value > lower_growth.enterprise_value,
            [round(lower_growth.enterprise_value, 6), round(higher_growth.enterprise_value, 6)],
            "higher valid terminal growth produces higher EV",
            "VALUATION",
        ))

        returns = ReturnEngine()
        irr = returns.irr([-100.0, 110.0])
        checks.append(QualificationCheck(
            "IRR_ANALYTIC_ORACLE",
            self._close(irr, 0.10, 1e-5),
            round(irr, 8),
            0.10,
            "RETURNS",
        ))
        moic = returns.moic(100.0, 250.0)
        checks.append(QualificationCheck("MOIC_ORACLE", moic == 2.5, moic, 2.5, "RETURNS"))
        equity = EquityBridge(
            enterprise_value=1000.0,
            cash=50.0,
            debt=200.0,
            debt_like=30.0,
            non_operating_assets=20.0,
            minority_interest=10.0,
        ).equity_value()
        checks.append(QualificationCheck("EQUITY_BRIDGE_ORACLE", equity == 830.0, equity, 830.0, "VALUATION"))

        qoe = QualityOfEarningsEngine().normalize_ebitda(
            100.0,
            [
                EBITDAAdjustment("supported", "supported adjustment", 10.0, False, 0.9),
                EBITDAAdjustment("weak", "low-confidence adjustment", 50.0, False, 0.2),
            ],
            minimum_confidence=0.5,
        )
        checks.append(QualificationCheck(
            "QOE_EVIDENCE_THRESHOLD",
            qoe["normalized_ebitda"] == 110.0
            and qoe["accepted_ids"] == ["supported"]
            and qoe["excluded_low_confidence_ids"] == ["weak"],
            qoe,
            {"normalized_ebitda": 110.0, "accepted": ["supported"], "excluded": ["weak"]},
            "QOE",
        ))

        wc = WorkingCapitalNormalizer()
        target_wc = wc.target([10.0, 20.0, 30.0])
        wc_adjustment = wc.adjustment(25.0, target_wc)
        checks.append(QualificationCheck(
            "WORKING_CAPITAL_ORACLE",
            target_wc == 20.0 and wc_adjustment == 5.0,
            [target_wc, wc_adjustment],
            [20.0, 5.0],
            "QOE",
        ))

        debt_like = DebtLikeEngine().total(
            [
                DebtLikeItem("accepted", 10.0, 0.9, True),
                DebtLikeItem("weak", 20.0, 0.2, True),
                DebtLikeItem("excluded", 30.0, 1.0, False),
            ],
            minimum_confidence=0.5,
        )
        checks.append(QualificationCheck(
            "DEBT_LIKE_EVIDENCE_THRESHOLD",
            debt_like["total_debt_like"] == 10.0 and debt_like["accepted_ids"] == ["accepted"],
            debt_like,
            {"total_debt_like": 10.0, "accepted": ["accepted"]},
            "QOE",
        ))

        diligence = DiligenceEngine()
        profile = diligence.standard_profile()
        full_types = {item.document_type for item in profile}
        empty_score = diligence.completeness(profile, set())
        full_score = diligence.completeness(profile, full_types)
        partial_score = diligence.completeness(profile, set(list(full_types)[:3]))
        checks.append(QualificationCheck(
            "DILIGENCE_BOUNDARY_ORACLE",
            empty_score == 0.0 and full_score == 1.0 and 0.0 < partial_score < 1.0,
            [empty_score, partial_score, full_score],
            [0.0, "between", 1.0],
            "DILIGENCE",
        ))

        thesis = AcquisitionThesis(
            sectors=("saas",),
            geographies=("south africa",),
            min_revenue=50.0,
            max_revenue=500.0,
            min_ebitda_margin=0.15,
            max_leverage=3.0,
            required_recurring_revenue=0.6,
            strategic_priorities=("ai", "payments"),
        )
        target_ok = TargetCandidate("ok", "OK", "saas", "south africa", 100, 0.25, 1.0, 0.8, ("ai", "payments"))
        target_bad = TargetCandidate("bad", "BAD", "mining", "south africa", 100, 0.25, 1.0, 0.8, ("ai", "payments"))
        screen = TargetScreenEngine()
        ok_assessment = screen.assess(thesis, target_ok)
        bad_assessment = screen.assess(thesis, target_bad)
        checks.append(QualificationCheck(
            "THESIS_HARD_GATE",
            ok_assessment.eligible and not bad_assessment.eligible and "SECTOR_OUTSIDE_THESIS" in bad_assessment.hard_failures,
            {"ok": asdict(ok_assessment), "bad": asdict(bad_assessment)},
            "eligible target passes; off-thesis sector fails",
            "STRATEGY",
        ))

        guard = AuthorityGuard()
        final_decision = guard.evaluate(ActionRequest(
            "FINAL_ACQUISITION_RECOMMENDATION",
            Domain.PRIVATE_MNA,
            Domain.GOVERNANCE,
            InformationClass.CONFIDENTIAL,
        ))
        live_order = guard.evaluate(ActionRequest(
            "LIVE_ORDER",
            Domain.PUBLIC_MARKETS,
            Domain.PUBLIC_MARKETS,
            InformationClass.PUBLIC,
            financial_effect=True,
            requested_authority=AuthorityLevel.A5_SOVEREIGN_AUTHORITY,
        ))
        private_market = guard.evaluate(ActionRequest(
            "RESEARCH_EXPORT",
            Domain.PRIVATE_MNA,
            Domain.PUBLIC_MARKETS,
            InformationClass.CONFIDENTIAL,
        ))
        checks.append(QualificationCheck(
            "AUTHORITY_CONSTITUTION",
            final_decision.disposition == ActionDisposition.REQUIRE_HUMAN
            and live_order.disposition == ActionDisposition.DENY
            and private_market.disposition == ActionDisposition.DENY,
            [
                final_decision.disposition.value,
                live_order.disposition.value,
                private_market.disposition.value,
            ],
            ["REQUIRE_HUMAN", "DENY", "DENY"],
            "AUTHORITY",
        ))

        payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        base_recorder = _Recorder()
        base = MVPJourneyOrchestrator(outcome_recorder=base_recorder).run(copy.deepcopy(payload))
        repeated = MVPJourneyOrchestrator(outcome_recorder=_Recorder()).run(copy.deepcopy(payload))
        missing_payload = copy.deepcopy(payload)
        missing_payload["documents"] = missing_payload["documents"][:1]
        missing = MVPJourneyOrchestrator(outcome_recorder=_Recorder()).run(missing_payload)
        off_thesis_payload = copy.deepcopy(payload)
        off_thesis_payload["target"]["sector"] = "mining"
        off_thesis = MVPJourneyOrchestrator(outcome_recorder=_Recorder()).run(off_thesis_payload)

        checks.append(QualificationCheck(
            "MVP_BASE_INVARIANTS",
            base.passed
            and base.contradiction_count >= 1
            and base.final_recommendation_disposition == "REQUIRE_HUMAN"
            and base.live_order_disposition == "DENY"
            and base.private_to_market_disposition == "DENY",
            {
                "passed": base.passed,
                "contradictions": base.contradiction_count,
                "final": base.final_recommendation_disposition,
                "live_order": base.live_order_disposition,
                "private_to_market": base.private_to_market_disposition,
            },
            "base journey passes while contradiction remains visible and consequential routes remain gated",
            "END_TO_END",
        ))
        checks.append(QualificationCheck(
            "MISSING_EVIDENCE_COUNTERFACTUAL",
            missing.diligence_score < base.diligence_score
            and missing.transaction_readiness < base.transaction_readiness,
            {
                "base_diligence": base.diligence_score,
                "missing_diligence": missing.diligence_score,
                "base_readiness": base.transaction_readiness,
                "missing_readiness": missing.transaction_readiness,
            },
            "removing evidence reduces diligence and transaction readiness",
            "COUNTERFACTUAL",
        ))
        checks.append(QualificationCheck(
            "OFF_THESIS_COUNTERFACTUAL",
            not off_thesis.passed and not off_thesis.target_eligible,
            {"passed": off_thesis.passed, "eligible": off_thesis.target_eligible},
            {"passed": False, "eligible": False},
            "COUNTERFACTUAL",
        ))
        deterministic_fields = (
            "target_score",
            "contradiction_count",
            "diligence_score",
            "normalized_ebitda",
            "dcf_enterprise_value",
            "comparable_low",
            "comparable_high",
            "equity_value",
            "irr",
            "market_fundamental_probability",
            "market_implied_proxy",
            "market_expectation_gap",
            "market_fragility",
            "council_recommendation",
            "passport_readiness",
            "transaction_readiness",
            "day_one_readiness",
            "synergy_realization",
            "value_leakage",
        )
        deterministic = all(getattr(base, field) == getattr(repeated, field) for field in deterministic_fields)
        checks.append(QualificationCheck(
            "DETERMINISTIC_ECONOMIC_REPLAY",
            deterministic,
            {field: getattr(base, field) for field in deterministic_fields},
            "exact replay match on deterministic economic/decision fields",
            "REPRODUCIBILITY",
        ))

        fatal_failures = tuple(check.check_id for check in checks if check.fatal and not check.passed)
        score = sum(1 for check in checks if check.passed) / len(checks)
        body = {
            "schema": "CIOS-INTERNAL-QUALIFICATION-RECEIPT-V1",
            "qualification_class": "SYNTHETIC_DETERMINISTIC_QUALIFICATION",
            "score": score,
            "checks": [asdict(check) for check in checks],
            "fatal_failures": fatal_failures,
            "truth_boundary": (
                "This receipt proves transparent deterministic/synthetic behavior only. "
                "It is not historical-deal calibration, investment performance, accounting assurance, legal advice, or provider production proof."
            ),
        }
        return QualificationReport(
            schema=body["schema"],
            qualification_class=body["qualification_class"],
            passed=not fatal_failures and score == 1.0,
            score=score,
            checks=tuple(checks),
            fatal_failures=fatal_failures,
            truth_boundary=body["truth_boundary"],
            receipt_sha256=stable_sha256(body),
        )
