from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Iterable, Sequence


@dataclass(frozen=True)
class TechnologyInvestment:
    investment_id: str
    name: str
    annual_cost: float
    three_year_tco: float
    expected_value: float
    risk_score: int
    owner: str
    kpi: str
    target: float
    observed: float | None = None
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class VendorScorecard:
    vendor_id: str
    name: str
    annual_cost: float
    sla_target: float
    sla_observed: float
    risk_score: int
    strategic_dependency: int
    exit_plan: bool


@dataclass(frozen=True)
class PortfolioDecision:
    investment_id: str
    priority_score: float
    decision: str
    benefit_state: str


class ExecutiveTechnologyManagementLab:
    """Synthetic proof lab for executive technology portfolio management.

    This lab models budget/TCO/ROI hypotheses, vendor performance, portfolio
    sequencing, OKRs/KPIs and benefits-realisation gates. All money and outcomes
    are synthetic. It does not establish that the human owner held a real budget,
    vendor portfolio or executive authority.
    """

    SCHEMA = "BUBBLES-EXECUTIVE-TECHNOLOGY-MANAGEMENT-LAB-V1"

    def __init__(self, annual_budget: float) -> None:
        if annual_budget <= 0:
            raise ValueError("annual_budget must be positive")
        self.annual_budget = float(annual_budget)

    @staticmethod
    def _validate_investment(item: TechnologyInvestment) -> None:
        if item.annual_cost < 0 or item.three_year_tco < 0 or item.expected_value < 0:
            raise ValueError("investment financial values must be non-negative")
        if not item.owner.strip() or not item.kpi.strip():
            raise ValueError("every investment requires an owner and KPI")
        if not 0 <= item.risk_score <= 100:
            raise ValueError("risk_score must be between 0 and 100")
        if item.three_year_tco < item.annual_cost:
            raise ValueError("three_year_tco cannot be lower than annual_cost")

    @staticmethod
    def _validate_vendor(item: VendorScorecard) -> None:
        if item.annual_cost < 0:
            raise ValueError("vendor cost must be non-negative")
        if not 0 <= item.sla_target <= 100 or not 0 <= item.sla_observed <= 100:
            raise ValueError("SLA values must be percentages between 0 and 100")
        if not 0 <= item.risk_score <= 100 or not 0 <= item.strategic_dependency <= 100:
            raise ValueError("vendor risk/dependency must be between 0 and 100")

    @staticmethod
    def priority_score(item: TechnologyInvestment) -> float:
        ExecutiveTechnologyManagementLab._validate_investment(item)
        # Synthetic risk-adjusted value score. Higher expected value and lower
        # TCO/risk rank higher. This is a prioritisation aid, not an ROI claim.
        value_ratio = item.expected_value / max(item.three_year_tco, 1.0)
        risk_multiplier = max(0.0, 1.0 - item.risk_score / 125.0)
        return round(value_ratio * risk_multiplier * 100.0, 4)

    @staticmethod
    def benefit_state(item: TechnologyInvestment) -> str:
        ExecutiveTechnologyManagementLab._validate_investment(item)
        if item.observed is None:
            return "TARGET_HYPOTHESIS_NOT_OBSERVED"
        if item.observed >= item.target:
            return "TARGET_MET_IN_SYNTHETIC_OBSERVATION"
        return "TARGET_NOT_MET_IN_SYNTHETIC_OBSERVATION"

    @staticmethod
    def vendor_health(item: VendorScorecard) -> dict[str, object]:
        ExecutiveTechnologyManagementLab._validate_vendor(item)
        sla_ratio = item.sla_observed / max(item.sla_target, 1.0)
        risk_penalty = (item.risk_score + item.strategic_dependency) / 200.0
        score = max(0.0, min(100.0, 100.0 * sla_ratio * (1.0 - 0.45 * risk_penalty)))
        decision = "REVIEW" if score < 75 or not item.exit_plan else "CONTINUE_SYNTHETIC"
        return {
            "vendor_id": item.vendor_id,
            "score": round(score, 2),
            "decision": decision,
            "truth_boundary": "Synthetic vendor-performance model only; not evidence of a real supplier decision.",
        }

    def assess_portfolio(
        self,
        investments: Sequence[TechnologyInvestment],
        vendors: Sequence[VendorScorecard] = (),
    ) -> dict[str, object]:
        if not investments:
            raise ValueError("at least one technology investment is required")
        for item in investments:
            self._validate_investment(item)
        for vendor in vendors:
            self._validate_vendor(vendor)

        annual_commitment = round(sum(item.annual_cost for item in investments), 2)
        if annual_commitment > self.annual_budget:
            raise ValueError("portfolio exceeds annual synthetic budget envelope")

        known_ids = {item.investment_id for item in investments}
        if len(known_ids) != len(investments):
            raise ValueError("investment IDs must be unique")
        for item in investments:
            missing = set(item.dependencies) - known_ids
            if missing:
                raise ValueError(f"unknown dependencies for {item.investment_id}: {sorted(missing)}")

        ordered = sorted(investments, key=self.priority_score, reverse=True)
        decisions: list[PortfolioDecision] = []
        consumed = 0.0
        for item in ordered:
            consumed += item.annual_cost
            decision = "FUND_SYNTHETIC" if consumed <= self.annual_budget else "DEFER_SYNTHETIC"
            decisions.append(
                PortfolioDecision(
                    investment_id=item.investment_id,
                    priority_score=self.priority_score(item),
                    decision=decision,
                    benefit_state=self.benefit_state(item),
                )
            )

        vendor_results = [self.vendor_health(v) for v in vendors]
        payload: dict[str, object] = {
            "schema": self.SCHEMA,
            "annual_budget": self.annual_budget,
            "annual_commitment": annual_commitment,
            "budget_variance": round(self.annual_budget - annual_commitment, 2),
            "investments": [asdict(item) for item in investments],
            "decisions": [asdict(item) for item in decisions],
            "vendors": vendor_results,
            "proof_state": "LOCAL_DEMONSTRATION_VERIFIED" if all(d.decision == "FUND_SYNTHETIC" for d in decisions) else "TESTED",
            "capabilities": ["CAP-IT-FIN", "CAP-VENDOR", "CAP-PPM"],
            "truth_boundary": (
                "All budgets, vendor records, ROI/value hypotheses and observed outcomes in this lab are synthetic. "
                "This demonstrates Bubbles organisational capability only and is not evidence that Kim personally "
                "held budget, procurement, vendor, portfolio or CIO authority. CV/interview claims require separate "
                "human-owner evidence plus Ledger approval."
            ),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload["receipt_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return payload

    @staticmethod
    def safe_claim() -> str:
        return (
            "Designed and deterministically tested a synthetic executive technology portfolio model covering "
            "budget/TCO/value hypotheses, risk-adjusted prioritisation, vendor/SLA review, OKRs/KPIs and "
            "benefits-realisation gates."
        )

    @staticmethod
    def forbidden_claims() -> tuple[str, ...]:
        return (
            "managed a real enterprise technology budget",
            "delivered verified ROI for a real employer",
            "owned a real vendor portfolio",
            "served as CIO or executive technology authority",
            "realised production benefits without observed evidence",
        )


def synthetic_reference_portfolio() -> tuple[TechnologyInvestment, ...]:
    return (
        TechnologyInvestment(
            "INV-INTEGRATION",
            "Student lifecycle integration",
            1_800_000,
            4_900_000,
            8_200_000,
            28,
            "Director Institutional Systems",
            "manual_reconciliation_hours_reduced_pct",
            45.0,
            51.0,
        ),
        TechnologyInvestment(
            "INV-DATA",
            "Institutional BI and data quality",
            1_250_000,
            3_300_000,
            5_400_000,
            24,
            "Head Data & BI",
            "critical_kpis_with_lineage_pct",
            90.0,
            93.0,
            ("INV-INTEGRATION",),
        ),
        TechnologyInvestment(
            "INV-CYBER",
            "Identity and cyber assurance",
            1_100_000,
            2_900_000,
            4_200_000,
            18,
            "Head Cybersecurity",
            "privileged_access_reviews_completed_pct",
            98.0,
            99.0,
        ),
        TechnologyInvestment(
            "INV-AI",
            "Governed AI and automation pilots",
            850_000,
            2_100_000,
            3_700_000,
            42,
            "Head Digital Innovation",
            "pilot_use_cases_meeting_release_gate_pct",
            70.0,
            None,
            ("INV-DATA",),
        ),
    )


def synthetic_reference_vendors() -> tuple[VendorScorecard, ...]:
    return (
        VendorScorecard("VENDOR-LMS", "Synthetic LMS Partner", 900_000, 99.5, 99.7, 25, 55, True),
        VendorScorecard("VENDOR-CLOUD", "Synthetic Cloud Partner", 1_100_000, 99.9, 99.92, 22, 70, True),
    )
