import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from evidenceops.capital_intelligence_os.production_dataplane import (
    AdapterProbe,
    IdentityClaims,
    ProductionBindingIntent,
    ProductionDataPlanePreflight,
    ProviderAdapterRegistration,
)
from evidenceops.capital_intelligence_os.production_gate import EvidenceBinding, EvidenceState


NOW = datetime(2026, 8, 11, 21, tzinfo=timezone.utc)
TARGET = EvidenceBinding(
    "google-cloud",
    "sov-hybrid-suite",
    "africa-south1",
    "PRODUCTION",
    "cios-production",
    "t",
    "a" * 40,
    "sha256:" + "b" * 64,
)


def claims(tenant: str = "t", mfa: bool = True) -> IdentityClaims:
    return IdentityClaims("u", tenant, ("admin",), "idp", mfa, NOW.isoformat())


def probe(
    adapter_id: str,
    control: str,
    *,
    healthy: bool = True,
    days: int = 0,
) -> AdapterProbe:
    return AdapterProbe(
        adapter_id,
        "google-cloud",
        healthy,
        (control,),
        f"provider://receipt/{adapter_id}",
        (NOW - timedelta(days=days)).isoformat(),
        {},
        TARGET,
        "signed-probe",
        "independent-reader",
        "deployment-executor",
    )


def preflight(intent: ProductionBindingIntent) -> ProductionDataPlanePreflight:
    required = ProductionDataPlanePreflight().required_controls(intent)
    registrations = [
        ProviderAdapterRegistration(
            f"adapter-{index}",
            "google-cloud",
            control,
            TARGET,
            "independent-reader",
        )
        for index, control in enumerate(required)
    ]
    return ProductionDataPlanePreflight(
        registrations,
        attestation_verifier=lambda item: item.attestation == "signed-probe",
    )


def complete(intent: ProductionBindingIntent) -> tuple[ProductionDataPlanePreflight, list[AdapterProbe]]:
    gate = preflight(intent)
    probes = [
        probe(f"adapter-{index}", control)
        for index, control in enumerate(gate.required_controls(intent))
    ]
    return gate, probes


class ProductionDataPlaneRC4Tests(unittest.TestCase):
    def test_empty_fails(self) -> None:
        intent = ProductionBindingIntent("t")
        gate = preflight(intent)
        self.assertFalse(gate.evaluate(intent, claims(), [], now=NOW).ready)

    def test_complete_registered_attested_set_passes(self) -> None:
        intent = ProductionBindingIntent("t")
        gate, probes = complete(intent)
        report = gate.evaluate(intent, claims(), probes, now=NOW)
        self.assertTrue(report.ready)
        self.assertEqual(0, len(report.missing_controls))

    def test_market_and_private_controls_follow_intent(self) -> None:
        gate = ProductionDataPlanePreflight()
        self.assertNotIn(
            gate.MARKET_CONTROL,
            gate.required_controls(ProductionBindingIntent("t", market_intelligence_enabled=False)),
        )
        self.assertIn(
            gate.MARKET_CONTROL,
            gate.required_controls(ProductionBindingIntent("t", market_intelligence_enabled=True)),
        )
        self.assertNotIn(
            gate.PRIVATE_CONTROL,
            gate.required_controls(ProductionBindingIntent("t", private_mna_enabled=False)),
        )

    def test_mfa_and_tenant_binding_are_required(self) -> None:
        intent = ProductionBindingIntent("t")
        gate = preflight(intent)
        with self.assertRaises(PermissionError):
            gate.evaluate(intent, claims(mfa=False), [], now=NOW)
        with self.assertRaises(PermissionError):
            gate.evaluate(intent, claims("other"), [], now=NOW)

    def test_stale_or_unhealthy_probe_fails(self) -> None:
        intent = ProductionBindingIntent("t", False, False)
        gate, probes = complete(intent)
        probes[0] = replace(probes[0], observed_at=(NOW - timedelta(days=31)).isoformat())
        report = gate.evaluate(intent, claims(), probes, now=NOW)
        self.assertFalse(report.ready)
        self.assertIn(probes[0].adapter_id, report.failed_adapters)

        gate, probes = complete(intent)
        probes[0] = replace(probes[0], healthy=False)
        self.assertFalse(gate.evaluate(intent, claims(), probes, now=NOW).ready)

    def test_unregistered_or_self_attesting_probe_fails(self) -> None:
        intent = ProductionBindingIntent("t", False, False)
        gate, probes = complete(intent)
        probes[0] = replace(probes[0], adapter_id="unregistered")
        self.assertFalse(gate.evaluate(intent, claims(), probes, now=NOW).ready)

        gate, probes = complete(intent)
        probes[0] = replace(probes[0], attestor_id="deployment-executor")
        self.assertFalse(gate.evaluate(intent, claims(), probes, now=NOW).ready)

    def test_one_probe_cannot_claim_multiple_unrelated_controls(self) -> None:
        intent = ProductionBindingIntent("t", False, False)
        gate, probes = complete(intent)
        probes[0] = replace(probes[0], control_ids=tuple(gate.required_controls(intent)))
        report = gate.evaluate(intent, claims(), probes, now=NOW)
        self.assertFalse(report.ready)
        self.assertIn(probes[0].adapter_id, report.failed_adapters)

    def test_wrong_target_or_attestation_fails(self) -> None:
        intent = ProductionBindingIntent("t", False, False)
        gate, probes = complete(intent)
        probes[0] = replace(probes[0], binding=replace(TARGET, region="us-central1"))
        probes[1] = replace(probes[1], attestation="forged")
        report = gate.evaluate(intent, claims(), probes, now=NOW)
        self.assertFalse(report.ready)
        self.assertIn(probes[0].adapter_id, report.failed_adapters)
        self.assertIn(probes[1].adapter_id, report.failed_adapters)

    def test_compiles_bound_provider_evidence(self) -> None:
        intent = ProductionBindingIntent("t", False, False)
        gate, probes = complete(intent)
        report = gate.evaluate(intent, claims(), probes, now=NOW)
        self.assertTrue(all(item.state == EvidenceState.VERIFIED for item in report.provider_evidence))
        self.assertTrue(all(item.binding == TARGET for item in report.provider_evidence))


if __name__ == "__main__":
    unittest.main()
