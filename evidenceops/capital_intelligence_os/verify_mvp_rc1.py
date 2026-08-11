
from __future__ import annotations
import json
from pathlib import Path
from .mvp_journey import MVPJourneyOrchestrator
from .verify_core_v07 import verify as verify_core_v07

class _VerificationRecorder:
    def __init__(self) -> None: self.rows=[]
    def record(self, **kwargs) -> None: self.rows.append(dict(kwargs))

def verify() -> dict[str, object]:
    core=verify_core_v07()
    payload=json.loads((Path(__file__).parent/"fixtures"/"synthetic_mvp_deal_v1.json").read_text())
    recorder=_VerificationRecorder()
    journey=MVPJourneyOrchestrator(outcome_recorder=recorder).run(payload)
    checks={
        "core_v07_regression": bool(core.get("passed")),
        "synthetic_full_deal_journey": journey.passed,
        "human_final_authority": journey.final_recommendation_disposition=="REQUIRE_HUMAN",
        "live_order_denied": journey.live_order_disposition=="DENY",
        "private_to_market_denied": journey.private_to_market_disposition=="DENY",
        "contradiction_surfaced": journey.contradiction_count>=1,
        "outcome_learning_recorded": journey.outcome_recorded and len(recorder.rows)==1,
        "passport_integrity": bool(journey.checks.get("passport_integrity")),
        "learning_chain_valid": journey.learning_chain_valid,
    }
    return {"passed":all(checks.values()),"release":"1.0.0-rc1","checks":checks,"journey":journey.deal_id}

if __name__=="__main__":
    print(json.dumps(verify(),indent=2,sort_keys=True))
