from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Mapping, Protocol

from .authority import AuthorityGuard
from .diligence import DiligenceEngine
from .evolution import CouncilOpinion, EvidenceWeightedCouncil
from .integration import DayOneReadiness, IntegrationMilestone, SynergyCommitment, SynergyLedger, ValueLeakageDetector
from .learning import LearningLedger
from .market_intelligence import FundamentalSignal, MarketDealTerms
from .market_service import MarketIntelligenceService
from .models import (
    ActionDisposition, ActionRequest, AuthorityLevel, Claim, Domain, EvidenceRef,
    EvidenceStatus, InformationClass, stable_sha256,
)
from .passport import DealPassportIssuer
from .outcomenet import OutcomeNet, OutcomeObservation
from .product_ui import DashboardRenderer, WorkspaceComposer
from .proofgraph import ProofGraph
from .qoe import EBITDAAdjustment, QualityOfEarningsEngine
from .strategy import TargetCandidate, TargetScreenEngine, ThesisCompiler
from .tenancy import TenantContext
from .valuation import ComparableValuationEngine, DCFEngine, EquityBridge, ForecastCashFlow, ReturnEngine
from .vault import DocumentVault


class OutcomeRecorder(Protocol):
    def record(self, *, tenant_id: str, cohort: str, metric: str, predicted: float, actual: float, metadata: Mapping[str, Any]) -> None: ...


class OutcomeNetRecorder:
    """Adapter for an already-consented canonical OutcomeNet instance."""
    def __init__(self, outcome_net: OutcomeNet) -> None:
        self.outcome_net = outcome_net

    def record(self, *, tenant_id: str, cohort: str, metric: str, predicted: float, actual: float, metadata: Mapping[str, Any]) -> None:
        self.outcome_net.record(OutcomeObservation(
            tenant_id=tenant_id, cohort=cohort, metric=metric,
            predicted=predicted, actual=actual, metadata=dict(metadata),
        ))


@dataclass(frozen=True)
class JourneyResult:
    deal_id: str
    target_name: str
    target_eligible: bool
    target_score: float
    contradiction_count: int
    diligence_score: float
    normalized_ebitda: float
    dcf_enterprise_value: float
    comparable_low: float
    comparable_high: float
    equity_value: float
    irr: float
    market_fundamental_probability: float
    market_implied_proxy: float
    market_expectation_gap: float
    market_fragility: float
    council_recommendation: str
    council_support_weight: float
    passport_readiness: float
    transaction_readiness: float
    day_one_readiness: float
    synergy_realization: float
    value_leakage: float
    final_recommendation_disposition: str
    live_order_disposition: str
    private_to_market_disposition: str
    outcome_recorded: bool
    learning_chain_valid: bool
    dashboard_html: str
    checks: Mapping[str, bool]
    passed: bool


class DecisionCompletenessIndex:
    def score(self, *, target_fit: float, diligence: float, passport: float, evidence_confidence: float) -> float:
        values=(target_fit,diligence,passport,evidence_confidence)
        if any(not 0 <= x <= 1 for x in values):
            raise ValueError("decision completeness inputs must be between 0 and 1")
        return max(0.0,min(1.0,.20*target_fit+.30*diligence+.30*passport+.20*evidence_confidence))


class DealJourneyInvariantGuard:
    def evaluate(
        self, *, target_eligible: bool, dcf_value: float, diligence_score: float,
        final_disposition: ActionDisposition, live_order_disposition: ActionDisposition,
        private_market_disposition: ActionDisposition, learning_valid: bool,
        outcome_expected: bool, outcome_recorded: bool,
    ) -> dict[str,bool]:
        return {
            "target_eligible": bool(target_eligible),
            "valuation_positive": dcf_value > 0,
            "diligence_bounded": 0 <= diligence_score <= 1,
            "final_recommendation_human_gated": final_disposition == ActionDisposition.REQUIRE_HUMAN,
            "live_order_denied": live_order_disposition == ActionDisposition.DENY,
            "private_to_market_denied": private_market_disposition == ActionDisposition.DENY,
            "learning_chain_valid": bool(learning_valid),
            "outcome_learning_respects_configuration": (not outcome_expected) or outcome_recorded,
        }


class MVPJourneyOrchestrator:
    """A1-safe synthetic end-to-end transaction composition layer."""

    def __init__(self, *, outcome_recorder: OutcomeRecorder | None = None) -> None:
        self.outcome_recorder = outcome_recorder
        self.strategy = TargetScreenEngine()
        self.diligence = DiligenceEngine()
        self.qoe = QualityOfEarningsEngine()
        self.dcf = DCFEngine()
        self.comps = ComparableValuationEngine()
        self.returns = ReturnEngine()
        self.market = MarketIntelligenceService()
        self.council = EvidenceWeightedCouncil()
        self.passports = DealPassportIssuer()
        self.completeness = DecisionCompletenessIndex()
        self.invariants = DealJourneyInvariantGuard()

    @staticmethod
    def _evidence_ref(row: Mapping[str, Any]) -> EvidenceRef:
        return EvidenceRef(
            str(row["source_id"]), str(row.get("source_type","synthetic_fixture")),
            str(row["locator"]), str(row["observed_at"]),
            str(row.get("content_hash") or stable_sha256(row)), str(row.get("authority","SYNTHETIC_TEST_SOURCE")),
        )

    def run(self, payload: Mapping[str, Any]) -> JourneyResult:
        deal_id=str(payload["deal_id"])
        ctx=TenantContext(str(payload["tenant_id"]),str(payload.get("user_id","mvp-runner")),tuple(payload.get("roles",("admin","deal_member"))))
        ctx.validate()

        thesis=ThesisCompiler().compile(payload["objective"])
        target=TargetCandidate(**payload["target"])
        target_assessment=self.strategy.assess(thesis,target)

        vault=DocumentVault(":memory:")
        try:
            for doc in payload.get("documents",()):
                vault.ingest(
                    ctx, logical_key=str(doc["logical_key"]), filename=str(doc["filename"]),
                    document_type=str(doc["document_type"]), content_type=str(doc.get("content_type","application/octet-stream")),
                    content=str(doc.get("content","")).encode("utf-8"),
                    information_class=InformationClass(str(doc.get("information_class","CONFIDENTIAL"))),
                    source_id=str(doc.get("source_id","synthetic-v1")), extracted_text=str(doc.get("extracted_text","")),
                    tags=tuple(doc.get("tags",())),
                )
            document_types=vault.document_types(ctx)
            diligence_score=self.diligence.completeness(self.diligence.standard_profile(),document_types)
            missing_gaps=self.diligence.missing(self.diligence.standard_profile(),document_types)

            graph=ProofGraph()
            claims=[]
            contradictions=[]
            for row in payload.get("claims",()):
                evidence=[self._evidence_ref(e) for e in row.get("evidence",())]
                claim=Claim(
                    str(row.get("subject_id",target.target_id)),str(row["predicate"]),row["value"],
                    EvidenceStatus(str(row.get("status","VERIFIED"))),evidence,
                    InformationClass(str(row.get("information_class","CONFIDENTIAL"))),
                    Domain(str(row.get("domain","PRIVATE_MNA"))),float(row.get("confidence",1.0)),
                    list(row.get("assumptions",())),
                )
                claims.append(claim)
                contradictions.extend(graph.add_claim(claim))

            qoe_rows=[EBITDAAdjustment(
                str(a["adjustment_id"]),str(a["description"]),float(a["ebitda_effect"]),
                bool(a["recurring"]),float(a["evidence_confidence"]),str(a.get("category","OTHER"))
            ) for a in payload["qoe_adjustments"]]
            qoe=self.qoe.normalize_ebitda(float(payload["reported_ebitda"]),qoe_rows,float(payload.get("qoe_min_confidence",.5)))
            normalized=float(qoe["normalized_ebitda"])

            forecasts=[ForecastCashFlow(int(x["year"]),float(x["free_cash_flow"])) for x in payload["forecasts"]]
            dcf=self.dcf.value(forecasts,float(payload["wacc"]),float(payload["terminal_growth"]))
            comp=self.comps.implied_enterprise_value(normalized,[float(x) for x in payload["peer_multiples"]])
            bridge=EquityBridge(dcf.enterprise_value,float(payload.get("cash",0)),float(payload.get("debt",0)),float(payload.get("debt_like",0)),float(payload.get("non_operating_assets",0)),float(payload.get("minority_interest",0)))
            equity=bridge.equity_value()
            irr=self.returns.irr([float(x) for x in payload["equity_cash_flows"]])

            signals=[FundamentalSignal(str(s["name"]),float(s["completion_probability"]),float(s["reliability"])) for s in payload["market"]["fundamental_signals"]]
            terms=MarketDealTerms(**{k:float(v) for k,v in payload["market"]["terms"].items()})
            ma=self.market.assess_deal(
                signals,terms,
                financing_stress=float(payload["market"]["financing_stress"]),
                regulatory_uncertainty=float(payload["market"]["regulatory_uncertainty"]),
                market_volatility=float(payload["market"]["market_volatility"]),
                synergy_dependence=float(payload["market"]["synergy_dependence"]),
                leverage=float(payload["market"]["leverage"]),
                evidence_confidence=float(payload["market"].get("evidence_confidence",1.0)),
            )

            opinions=[CouncilOpinion(str(x["agent"]),str(x["recommendation"]),float(x["confidence"]),float(x["evidence_quality"]),str(x.get("rationale",""))) for x in payload["council_opinions"]]
            council=self.council.synthesize(opinions)

            required=tuple(str(x) for x in payload.get("passport_required_predicates",()))
            passport=self.passports.issue(ctx,target.target_id,claims,required)

            evidence_confidence=0.0 if not claims else sum(c.confidence for c in claims)/len(claims)
            readiness=self.completeness.score(target_fit=target_assessment.score/100,diligence=diligence_score,passport=passport.readiness_score,evidence_confidence=evidence_confidence)

            milestones=[IntegrationMilestone(str(x["milestone_id"]),int(x["due_day"]),bool(x["critical"]),bool(x.get("completed",False))) for x in payload["integration"]["milestones"]]
            day_one=DayOneReadiness().score(milestones)
            synergies=[SynergyCommitment(str(x["synergy_id"]),str(x["category"]),float(x["expected_value"]),float(x.get("realized_value",0)),float(x.get("confidence",.5)),x.get("owner"),list(x.get("evidence_ids",()))) for x in payload["integration"]["synergies"]]
            synergy=SynergyLedger().realization(synergies)
            leakage=ValueLeakageDetector().detect(float(payload["integration"]["baseline_value"]),float(payload["integration"]["current_value"]),float(payload["integration"].get("approved_investment",0)))

            guard=AuthorityGuard()
            final_decision=guard.evaluate(ActionRequest("FINAL_ACQUISITION_RECOMMENDATION",Domain.PRIVATE_MNA,Domain.GOVERNANCE,InformationClass.CONFIDENTIAL))
            live_decision=guard.evaluate(ActionRequest("LIVE_ORDER",Domain.PUBLIC_MARKETS,Domain.PUBLIC_MARKETS,InformationClass.PUBLIC,financial_effect=True,requested_authority=AuthorityLevel.A5_SOVEREIGN_AUTHORITY))
            private_market=guard.evaluate(ActionRequest("RESEARCH_EXPORT",Domain.PRIVATE_MNA,Domain.PUBLIC_MARKETS,InformationClass.CONFIDENTIAL))

            learning=LearningLedger()
            learning.append("SUCCESS","MVP_JOURNEY",{
                "deal_id":deal_id,"target_id":target.target_id,"diligence_score":diligence_score,
                "passport_readiness":passport.readiness_score,"council_recommendation":council.recommendation,
                "final_disposition":final_decision.disposition.value,
            })
            learning_ok=learning.verify()

            outcome_recorded=False
            outcome_cfg=payload.get("outcome")
            if outcome_cfg is not None and self.outcome_recorder is not None:
                self.outcome_recorder.record(
                    tenant_id=ctx.tenant_id,cohort=str(outcome_cfg["cohort"]),metric=str(outcome_cfg["metric"]),
                    predicted=float(outcome_cfg["predicted"]),actual=float(outcome_cfg["actual"]),
                    metadata={"deal_id":deal_id,"target_id":target.target_id},
                )
                outcome_recorded=True

            top_risks=[]
            if contradictions: top_risks.append(f"{len(contradictions)} evidence contradiction(s) require resolution")
            if missing_gaps: top_risks.extend(f"Missing {g.document_type}" for g in missing_gaps[:2])
            if ma.fragility_score>=.6: top_risks.append("Market/financing fragility is elevated")
            next_actions=["Resolve material evidence contradictions"] if contradictions else []
            next_actions += [g.question for g in missing_gaps[:2]]
            next_actions.append("Human Investment Committee decision required before any consequential action")

            low=max(0.0,min(float(comp["low"]),dcf.enterprise_value))
            high=max(float(comp["high"]),dcf.enterprise_value)
            workspace=WorkspaceComposer().compose(
                company_name=target.name,mode=str(payload.get("workspace_mode","GUIDED_OWNER")),
                readiness_score=readiness,valuation_range=(low,high),diligence_score=diligence_score,
                top_risks=top_risks,next_actions=next_actions,
                market_note=f"Fundamental completion {ma.fundamental_probability:.0%}; public-market proxy {ma.market_implied_proxy:.0%}; gap {ma.expectation_gap:+.0%}.",
            )
            dashboard=DashboardRenderer().render(workspace)

            checks=self.invariants.evaluate(
                target_eligible=target_assessment.eligible,dcf_value=dcf.enterprise_value,diligence_score=diligence_score,
                final_disposition=final_decision.disposition,live_order_disposition=live_decision.disposition,
                private_market_disposition=private_market.disposition,learning_valid=learning_ok,
                outcome_expected=outcome_cfg is not None,outcome_recorded=outcome_recorded,
            )
            checks["passport_integrity"]=passport.validate_integrity()
            checks["contradictions_visible"]=(len(contradictions)>=int(payload.get("minimum_expected_contradictions",0)))
            checks["council_is_advisory"]=final_decision.disposition==ActionDisposition.REQUIRE_HUMAN
            passed=all(checks.values())

            return JourneyResult(
                deal_id,target.name,target_assessment.eligible,target_assessment.score,len(contradictions),diligence_score,normalized,
                dcf.enterprise_value,float(comp["low"]),float(comp["high"]),equity,irr,ma.fundamental_probability,ma.market_implied_proxy,
                ma.expectation_gap,ma.fragility_score,council.recommendation,council.support_weight,passport.readiness_score,readiness,
                day_one,float(synergy["realization_ratio"]),float(leakage["leakage"]),final_decision.disposition.value,live_decision.disposition.value,
                private_market.disposition.value,outcome_recorded,learning_ok,dashboard,checks,passed,
            )
        finally:
            vault.close()
