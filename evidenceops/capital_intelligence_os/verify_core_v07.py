from __future__ import annotations
from datetime import datetime,timezone
from .audit import AuditLedger
from .authority import AuthorityGuard
from .diligence import DiligenceEngine
from .durable import DurableAutopilotRuntime
from .evolution import CouncilOpinion,EvidenceWeightedCouncil,ExperimentCourt,ExperimentEvidence
from .learning import LearningLedger
from .market_intelligence import MarketTruthGate,PublicMarketObservation,PublicTradingIntelligenceBridge
from .models import ActionRequest,Domain,InformationClass,AuthorityLevel,ActionDisposition,Event
from .mna import MNA_STAGES
from .policy import RuntimePolicy
from .product_ui import DashboardRenderer,WorkspaceComposer
from .store import SqliteStateStore
from .strategy import AcquisitionThesis,TargetCandidate,TargetScreenEngine
from .tenancy import TenantContext
from .valuation import DCFEngine,ForecastCashFlow,ReturnEngine
from .vault import DocumentVault
from .workspace import ReadinessDimension,SaleReadinessEngine
class _PublicFixtureAdapter:
 def observations(self):return [PublicMarketObservation('verify-public','ABC','price',100.0,datetime.now(timezone.utc).isoformat(),'fixture:ABC',currency='ZAR')]
def verify():
 guard=AuthorityGuard();private=guard.evaluate(ActionRequest('RESEARCH_EXPORT',Domain.PRIVATE_MNA,Domain.PUBLIC_MARKETS,InformationClass.CONFIDENTIAL));live=guard.evaluate(ActionRequest('LIVE_ORDER',Domain.PUBLIC_MARKETS,Domain.PUBLIC_MARKETS,InformationClass.PUBLIC,financial_effect=True,requested_authority=AuthorityLevel.A5_SOVEREIGN_AUTHORITY));ledger=LearningLedger();ledger.append('SUCCESS','VERIFY_RELEASE',{'phase':7});store=SqliteStateStore(':memory:');runtime=DurableAutopilotRuntime(store);ctx=TenantContext('verification-tenant','verification-user');event=Event('VERIFY','internal','verification',{'release':'0.7.0'},Domain.GOVERNANCE,InformationClass.PUBLIC,.1,occurred_at='2026-08-11T21:00:00+00:00');first=runtime.process(ctx,event);replay=runtime.process(ctx,event);bridge=PublicTradingIntelligenceBridge(_PublicFixtureAdapter());market_claim=MarketTruthGate().to_claim(bridge.read_public_evidence()[0]);policy=RuntimePolicy('v'*32);denied=False
 try:policy.authorize('POST','/trade/order')
 except PermissionError:denied=True
 audit=AuditLedger(':memory:');audit.append('t','u','GET','/health','ALLOW',{});audit_ok=audit.verify();audit.close();dcf=DCFEngine().value([ForecastCashFlow(1,100),ForecastCashFlow(2,110)],.1,.03);irr=ReturnEngine().irr([-100,0,121]);diligence=DiligenceEngine();readiness=SaleReadinessEngine().assess([ReadinessDimension('financials',.8,1,'x'),ReadinessDimension('contracts',.4,1,'x')]);vault=DocumentVault(':memory:');admin=TenantContext('verification-tenant','admin',('admin',));rec,d1=vault.ingest(admin,logical_key='fs',filename='fs.pdf',document_type='audited financial statements',content_type='application/pdf',content=b'abc',information_class=InformationClass.CONFIDENTIAL,source_id='fixture');rec2,d2=vault.ingest(admin,logical_key='copy',filename='copy.pdf',document_type='audited financial statements',content_type='application/pdf',content=b'abc',information_class=InformationClass.CONFIDENTIAL,source_id='fixture');vault_ok=(not d1 and d2 and rec.document_id==rec2.document_id);vault.close();snap=WorkspaceComposer().compose(company_name='<Co>',mode='GUIDED_OWNER',readiness_score=.6,valuation_range=(10,20),diligence_score=.5,top_risks=['Risk'],next_actions=['Act']);html=DashboardRenderer().render(snap)
 thesis=AcquisitionThesis(sectors=('saas',),geographies=('south africa',),min_revenue=50,max_revenue=500,min_ebitda_margin=.15,max_leverage=3,required_recurring_revenue=.6,strategic_priorities=('ai','payments'));target=TargetCandidate('T1','Target','saas','south africa',100,.25,1,.8,('ai','payments'));target_ok=TargetScreenEngine().assess(thesis,target).eligible
 court=ExperimentCourt().decide(ExperimentEvidence('exp',.6,.7,.68,100,.001,2,False));veto=ExperimentCourt().decide(ExperimentEvidence('exp2',.6,.9,.9,100,.001,1,True));council=EvidenceWeightedCouncil().synthesize([CouncilOpinion('weak1','BUY',1,.1),CouncilOpinion('weak2','BUY',1,.1),CouncilOpinion('strong','PASS',.9,.9)])
 checks={'mna_stage_count':len(MNA_STAGES)==60,'private_to_market_denied':private.disposition==ActionDisposition.DENY,'live_order_denied':live.disposition==ActionDisposition.DENY,'learning_chain_valid':ledger.verify() and store.verify_learning_chain(ctx.tenant_id),'database_quick_check':store.quick_check(),'idempotent_replay':first['replayed'] is False and replay['replayed'] is True,'public_market_bridge_only':market_claim.information_class==InformationClass.PUBLIC,'local_runtime_consequential_routes_denied':denied,'audit_chain_valid':audit_ok,'dcf_positive':dcf.enterprise_value>0,'irr_deterministic':abs(irr-.1)<1e-5,'diligence_detects_missing':diligence.completeness(diligence.standard_profile(),[])<1,'guided_owner_readiness':0<=readiness.score<=1,'vault_hash_deduplication':vault_ok,'dashboard_escapes_content':'<Co>' not in html and '&lt;Co&gt;' in html,'strategy_target_gate':target_ok,'experiment_court_promotes_proven_gain':court.promoted,'safety_regression_veto':not veto.promoted and 'SAFETY_REGRESSION_VETO' in veto.reasons,'evidence_weighted_council':council.recommendation=='PASS'};store.close();return {'passed':all(checks.values()),'release':'0.7.0','checks':checks}
if __name__=='__main__':
 import json;print(json.dumps(verify(),indent=2,sort_keys=True))
