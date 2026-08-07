from __future__ import annotations

from dataclasses import dataclass, field

MNA_STAGES = (
    "STRATEGIC_INTENT", "ACQUISITION_THESIS", "EXIT_READINESS", "COMPANY_PREPARATION", "BUSINESS_VALUATION", "VALUE_ENHANCEMENT", "TARGET_MARKET_MAPPING", "TARGET_SOURCING", "RELATIONSHIP_DEVELOPMENT", "INITIAL_SCREENING", "STRATEGIC_FIT", "NDA", "CIM", "IOI", "LOI", "FINANCING_STRATEGY", "DATA_ROOM", "DILIGENCE_PLANNING", "FINANCIAL_DILIGENCE", "LEGAL_DILIGENCE", "TAX_DILIGENCE", "COMMERCIAL_DILIGENCE", "OPERATIONAL_DILIGENCE", "TECHNOLOGY_DILIGENCE", "CYBER_DILIGENCE", "HR_DILIGENCE", "IP_DILIGENCE", "REGULATORY_DILIGENCE", "ESG_DILIGENCE", "SUPPLY_CHAIN_DILIGENCE", "CUSTOMER_DILIGENCE", "VENDOR_DILIGENCE", "INSURANCE_DILIGENCE", "REAL_ESTATE_DILIGENCE", "MANAGEMENT_ASSESSMENT", "CULTURE_ASSESSMENT", "FORENSIC_DILIGENCE", "QUALITY_OF_EARNINGS", "WORKING_CAPITAL", "DEBT_LIKE", "VALUATION_UPDATE", "SYNERGY_ESTIMATION", "DEAL_STRUCTURE", "PURCHASE_PRICE", "NEGOTIATION_PREPARATION", "TRANSACTION_DOCUMENTS", "REGULATORY_APPROVALS", "CONDITIONS_PRECEDENT", "CLOSING_READINESS", "SIGNING", "COMPLETION", "DAY_1", "INTEGRATION_30_60_90_100", "INTEGRATION_MANAGEMENT", "SYNERGY_CAPTURE", "VALUE_CREATION", "PORTFOLIO_MONITORING", "THESIS_VALIDATION", "CONTINUOUS_RISK_MONITORING", "FUTURE_EXIT_PLANNING",
)

CORE_PREREQUISITES = {
    "NDA": {"INITIAL_SCREENING"}, "LOI": {"STRATEGIC_FIT", "NDA"}, "DATA_ROOM": {"NDA"},
    "DILIGENCE_PLANNING": {"DATA_ROOM"}, "VALUATION_UPDATE": {"FINANCIAL_DILIGENCE"},
    "DEAL_STRUCTURE": {"VALUATION_UPDATE"}, "CLOSING_READINESS": {"TRANSACTION_DOCUMENTS", "CONDITIONS_PRECEDENT"},
    "SIGNING": {"CLOSING_READINESS"}, "COMPLETION": {"SIGNING"}, "DAY_1": {"COMPLETION"},
    "THESIS_VALIDATION": {"COMPLETION"},
}

@dataclass
class DealLifecycle:
    deal_id: str
    completed: set[str] = field(default_factory=set)
    current_stage: str = "STRATEGIC_INTENT"

    def complete(self, stage: str) -> None:
        if stage not in MNA_STAGES:
            raise ValueError(f"unknown M&A stage: {stage}")
        missing = CORE_PREREQUISITES.get(stage, set()) - self.completed
        if missing:
            raise ValueError(f"cannot complete {stage}; missing prerequisites: {sorted(missing)}")
        self.completed.add(stage)
        self.current_stage = stage

    def next_recommended(self) -> str | None:
        for stage in MNA_STAGES:
            if stage in self.completed:
                continue
            if not (CORE_PREREQUISITES.get(stage, set()) - self.completed):
                return stage
        return None
