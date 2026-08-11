from __future__ import annotations
from .production_gate import DeploymentIntent, ProductionQualificationGate
from .verify_mvp_rc1 import verify as verify_mvp_rc1

def verify() -> dict[str, object]:
    mvp=verify_mvp_rc1()
    gate=ProductionQualificationGate()
    intent=DeploymentIntent("PRODUCTION","UNBOUND")
    decision=gate.evaluate(intent,[])
    unsafe_intent_denied=False
    try:
        DeploymentIntent("PRODUCTION","UNBOUND",live_financial_effects_enabled=True).validate()
    except PermissionError:
        unsafe_intent_denied=True
    checks={
        "mvp_rc1_regression": bool(mvp.get("passed")),
        "production_gate_fails_closed_without_provider_proof": not decision.qualified and len(decision.missing_controls)>=len(gate.BASE_CONTROLS),
        "maturity_not_overpromoted": decision.maturity=="PROVIDER_QUALIFICATION_REQUIRED",
        "unsafe_financial_effect_intent_denied": unsafe_intent_denied,
    }
    return {
        "passed": all(checks.values()),
        "release": "1.0.0-rc2",
        "maturity": decision.maturity,
        "checks": checks,
        "missing_provider_controls": list(decision.missing_controls),
    }

if __name__=="__main__":
    import json
    print(json.dumps(verify(),indent=2,sort_keys=True))
