from __future__ import annotations
from datetime import datetime, timezone
from .production_dataplane import AdapterProbe, IdentityClaims, ProductionBindingIntent, ProductionDataPlanePreflight
from .production_gate import DeploymentIntent, ProductionQualificationGate
from .verify_rc3 import verify as verify_rc3


def verify() -> dict[str, object]:
    rc3 = verify_rc3()
    now = datetime(2026, 8, 11, 21, 0, tzinfo=timezone.utc)
    intent = ProductionBindingIntent("verification-tenant", private_mna_enabled=True, market_intelligence_enabled=True)
    claims = IdentityClaims("verification-user", "verification-tenant", ("admin",), "verification-idp", True, now.isoformat())
    preflight = ProductionDataPlanePreflight()
    empty = preflight.evaluate(intent, claims, [], now=now)
    probes = [
        AdapterProbe(
            f"verify-{index}",
            "verification-provider",
            True,
            (control,),
            f"provider-receipt:{control}",
            now.isoformat(),
        )
        for index, control in enumerate(preflight.required_controls(intent))
    ]
    complete = preflight.evaluate(intent, claims, probes, now=now)
    gate = ProductionQualificationGate()
    gate_required = set(
        gate.required_controls(
            DeploymentIntent(
                "STAGING",
                "UNBOUND",
                private_mna_enabled=True,
                market_intelligence_enabled=True,
            )
        )
    )
    compiled_controls = {evidence.control_id for evidence in complete.provider_evidence}
    checks = {
        "rc3_regression": bool(rc3.get("passed")),
        "empty_dataplane_fails_closed": not empty.ready and bool(empty.missing_controls),
        "complete_reference_dataplane_ready": complete.ready and not complete.failed_adapters,
        "compiled_provider_evidence_validated": bool(complete.provider_evidence)
        and all(evidence.state.value == "VERIFIED" for evidence in complete.provider_evidence),
        "dataplane_controls_are_qualification_controls": compiled_controls.issubset(gate_required),
        "production_not_overpromoted": rc3.get("maturity") == "PROVIDER_CANARY_READY",
    }
    return {
        "passed": all(checks.values()),
        "release": "1.0.0-rc4",
        "maturity": "PROVIDER_BINDING_READY",
        "checks": checks,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(verify(), indent=2, sort_keys=True))
