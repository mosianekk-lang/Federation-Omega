from __future__ import annotations
from datetime import datetime,timezone
from .audit import AuditLedger
from .authority import AuthorityGuard
from .diligence import DiligenceEngine
from .durable import DurableAutopilotRuntime
from .learning import LearningLedger
from .market_intelligence import MarketTruthGate,PublicMarketObservation,PublicTradingIntelligenceBridge
from .models import ActionRequest,Domain,InformationClass,AuthorityLevel,ActionDisposition,Event
from .mna import MNA_STAGES
from .policy import RuntimePolicy
from .store import SqliteStateStore
from .tenancy import TenantContext
from .valuation import DCFEngine,ForecastCashFlow,ReturnEngine
from .workspace import ReadinessDimension,SaleReadinessEngine
class _PublicFixtureAdapter:
    def observations(self): return [PublicMarketObservation('verify-public','ABC','price',100.0,datetime.now(timezone.utc).isoformat(),'fixture:ABC',currency='ZAR')]
def verify()->dict[str,object]:
    guard=AuthorityGuard(); private_to_market=guard.evaluate(ActionRequest('RESEARCH_EXPORT',Domain.PRIVATE_MNA,Domain.PUBLIC_MARKETS,InformationClass.CONFIDENTIAL)); live_order=guard.evaluate(ActionRequest('LIVE_ORDER',Domain.PUBLIC_MARKETS,Domain.PUBLIC_MARKETS,InformationClass.PUBLIC,financial_effect=True,requested_authority=AuthorityLevel.A5_SOVEREIGN_AUTHORITY)); ledger=LearningLedger(); ledger.append('SUCCESS','VERIFY_RELEASE',{'phase':5}); store=SqliteStateStore(':memory:'); runtime=DurableAutopilotRuntime(store); ctx=TenantContext('verification-tenant','verification-user'); event=Event('VERIFY','internal','verification',{'release':'0.5.0'},Domain.GOVERNANCE,InformationClass.PUBLIC,.1,occurred_at='2026-08-07T09:00:00+00:00'); first=runtime.process(ctx,event); replay=runtime.process(ctx,event); bridge=PublicTradingIntelligenceBridge(_PublicFixtureAdapter()); observations=bridge.read_public_evidence(); market_claim=MarketTruthGate().to_claim(observations[0]); policy=RuntimePolicy('v'*32); route_denied=False
    try: policy.authorize('POST','/trade/order')
    except PermissionError: route_denied=True
    audit=AuditLedger(':memory:'); audit.append('t','u','GET','/health','ALLOW',{}); audit_valid=audit.verify(); audit.close(); dcf=DCFEngine().value([ForecastCashFlow(1,100),ForecastCashFlow(2,110)],.10,.03); irr=ReturnEngine().irr([-100,0,121]); diligence=DiligenceEngine(); completeness=diligence.completeness(diligence.standard_profile(),[]); readiness=SaleReadinessEngine().assess([ReadinessDimension('financials',.8,1,'x'),ReadinessDimension('contracts',.4,1,'x')]); checks={'mna_stage_count':len(MNA_STAGES)==60,'private_to_market_denied':private_to_market.disposition==ActionDisposition.DENY,'live_order_denied':live_order.disposition==ActionDisposition.DENY,'learning_chain_valid':ledger.verify() and store.verify_learning_chain(ctx.tenant_id),'database_quick_check':store.quick_check(),'idempotent_replay':first['replayed'] is False and replay['replayed'] is True,'public_market_bridge_only':market_claim.information_class==InformationClass.PUBLIC,'bridge_has_no_order_interface':not hasattr(bridge,'place_order'),'local_runtime_consequential_routes_denied':route_denied,'audit_chain_valid':audit_valid,'dcf_positive':dcf.enterprise_value>0,'irr_deterministic':abs(irr-.1)<1e-5,'diligence_detects_missing':completeness<1,'guided_owner_readiness':0<=readiness.score<=1 and bool(readiness.owner_summary)}; store.close(); return {'passed':all(checks.values()),'release':'0.5.0','checks':checks}
if __name__=='__main__':
    import json; print(json.dumps(verify(),indent=2,sort_keys=True))
