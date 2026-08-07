from __future__ import annotations

from datetime import datetime, timezone
from .authority import AuthorityGuard
from .durable import DurableAutopilotRuntime
from .learning import LearningLedger
from .market_intelligence import MarketTruthGate, PublicMarketObservation, PublicTradingIntelligenceBridge
from .models import ActionRequest, Domain, InformationClass, AuthorityLevel, ActionDisposition, Event
from .mna import MNA_STAGES
from .store import SqliteStateStore
from .tenancy import TenantContext

class _PublicFixtureAdapter:
    def observations(self):
        return [PublicMarketObservation("verify-public","ABC","price",100.0,datetime.now(timezone.utc).isoformat(),"fixture:ABC",currency="ZAR")]

def verify() -> dict[str, object]:
    guard = AuthorityGuard()
    private_to_market = guard.evaluate(ActionRequest("RESEARCH_EXPORT", Domain.PRIVATE_MNA, Domain.PUBLIC_MARKETS, InformationClass.CONFIDENTIAL))
    live_order = guard.evaluate(ActionRequest("LIVE_ORDER", Domain.PUBLIC_MARKETS, Domain.PUBLIC_MARKETS, InformationClass.PUBLIC, financial_effect=True, requested_authority=AuthorityLevel.A5_SOVEREIGN_AUTHORITY))
    ledger = LearningLedger(); ledger.append("SUCCESS", "VERIFY_RELEASE", {"phase":3})
    store = SqliteStateStore(":memory:"); runtime = DurableAutopilotRuntime(store); ctx = TenantContext("verification-tenant","verification-user")
    event = Event("VERIFY","internal","verification",{"release":"0.3.0"},Domain.GOVERNANCE,InformationClass.PUBLIC,0.1)
    first = runtime.process(ctx,event); replay = runtime.process(ctx,event)
    bridge = PublicTradingIntelligenceBridge(_PublicFixtureAdapter()); observations = bridge.read_public_evidence(); market_claim = MarketTruthGate().to_claim(observations[0])
    checks = {
        "mna_stage_count":len(MNA_STAGES)==60,
        "private_to_market_denied":private_to_market.disposition==ActionDisposition.DENY,
        "live_order_denied":live_order.disposition==ActionDisposition.DENY,
        "learning_chain_valid":ledger.verify() and store.verify_learning_chain(ctx.tenant_id),
        "database_quick_check":store.quick_check(),
        "idempotent_replay":first["replayed"] is False and replay["replayed"] is True and store.count_rows("events",ctx.tenant_id)==1,
        "public_market_bridge_only":len(observations)==1 and market_claim.information_class==InformationClass.PUBLIC and market_claim.domain==Domain.PUBLIC_MARKETS,
        "bridge_has_no_order_interface":not hasattr(bridge,"place_order") and not hasattr(bridge,"transfer"),
    }
    store.close(); return {"passed":all(checks.values()),"release":"0.3.0","checks":checks}

if __name__ == "__main__":
    import json; print(json.dumps(verify(),indent=2,sort_keys=True))
