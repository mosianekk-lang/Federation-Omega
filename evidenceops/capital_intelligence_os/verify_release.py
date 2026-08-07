from __future__ import annotations

from .authority import AuthorityGuard
from .models import ActionRequest, Domain, InformationClass, AuthorityLevel, ActionDisposition
from .learning import LearningLedger
from .mna import MNA_STAGES

def verify() -> dict[str, object]:
    guard = AuthorityGuard()
    private_to_market = guard.evaluate(ActionRequest("RESEARCH_EXPORT", Domain.PRIVATE_MNA, Domain.PUBLIC_MARKETS, InformationClass.CONFIDENTIAL))
    live_order = guard.evaluate(ActionRequest("LIVE_ORDER", Domain.PUBLIC_MARKETS, Domain.PUBLIC_MARKETS, InformationClass.PUBLIC, financial_effect=True, requested_authority=AuthorityLevel.A5_SOVEREIGN_AUTHORITY))
    ledger = LearningLedger(); ledger.append("SUCCESS", "VERIFY_RELEASE", {"phase": 1})
    checks = {"mna_stage_count": len(MNA_STAGES) == 60, "private_to_market_denied": private_to_market.disposition == ActionDisposition.DENY, "live_order_denied": live_order.disposition == ActionDisposition.DENY, "learning_chain_valid": ledger.verify()}
    return {"passed": all(checks.values()), "checks": checks}

if __name__ == "__main__":
    import json
    print(json.dumps(verify(), indent=2, sort_keys=True))
