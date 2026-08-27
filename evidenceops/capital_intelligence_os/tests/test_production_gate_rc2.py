import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from evidenceops.capital_intelligence_os.production_gate import (
    DeploymentIntent,
    EvidenceBinding,
    EvidenceState,
    ProductionQualificationGate,
    ProviderEvidence,
)


NOW = datetime(2026, 8, 11, 21, 0, tzinfo=timezone.utc)
TARGET = EvidenceBinding(
    "google-cloud",
    "sov-hybrid-suite",
    "africa-south1",
    "PRODUCTION",
    "cios-production",
    "tenant-production",
    "a" * 40,
    "sha256:" + "b" * 64,
)


def evidence(
    control: str,
    state: EvidenceState = EvidenceState.VERIFIED,
    *,
    days: int = 0,
    binding: EvidenceBinding | None = TARGET,
    attestation: str = "signed-provider-receipt",
    attestor_id: str = "independent-reader",
    executor_id: str = "deployment-executor",
) -> ProviderEvidence:
    return ProviderEvidence(
        control,
        state,
        "google-cloud",
        f"provider://receipt/{control}",
        (NOW - timedelta(days=days)).isoformat(),
        {},
        binding,
        attestation,
        attestor_id,
        executor_id,
    )


class GateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.intent = DeploymentIntent("PRODUCTION", "africa-south1")
        self.gate = ProductionQualificationGate(
            expected_binding=TARGET,
            attestation_verifier=lambda item: item.attestation == "signed-provider-receipt",
        )

    def complete(self) -> list[ProviderEvidence]:
        return [evidence(control) for control in self.gate.required_controls(self.intent)]

    def test_empty_fails(self) -> None:
        self.assertFalse(self.gate.evaluate(self.intent, [], now=NOW).qualified)

    def test_all_independently_attested_exact_target_evidence_passes(self) -> None:
        decision = self.gate.evaluate(self.intent, self.complete(), now=NOW)
        self.assertTrue(decision.qualified)
        self.assertEqual("PRODUCTION_VERIFIED", decision.maturity)

    def test_failed_blocks(self) -> None:
        items = self.complete()
        items[-1] = replace(items[-1], state=EvidenceState.FAILED)
        self.assertFalse(self.gate.evaluate(self.intent, items, now=NOW).qualified)

    def test_verified_and_failed_conflict_is_blocking(self) -> None:
        items = self.complete()
        items.append(replace(items[0], state=EvidenceState.FAILED, observed_at=(NOW + timedelta(minutes=1)).isoformat()))
        decision = self.gate.evaluate(self.intent, items, now=NOW)
        self.assertFalse(decision.qualified)
        self.assertIn(items[0].control_id, decision.failed_controls)

    def test_future_evidence_is_rejected(self) -> None:
        items = self.complete()
        items[0] = replace(items[0], observed_at=(NOW + timedelta(days=1)).isoformat())
        decision = self.gate.evaluate(self.intent, items, now=NOW)
        self.assertFalse(decision.qualified)
        self.assertIn(items[0].control_id, decision.failed_controls)

    def test_timezone_naive_evidence_is_rejected(self) -> None:
        items = self.complete()
        items[0] = replace(items[0], observed_at="2026-08-11T21:00:00")
        self.assertFalse(self.gate.evaluate(self.intent, items, now=NOW).qualified)

    def test_wrong_target_and_self_attestation_are_rejected(self) -> None:
        items = self.complete()
        items[0] = replace(items[0], binding=replace(TARGET, region="us-central1"))
        items[1] = replace(items[1], attestor_id="deployment-executor")
        decision = self.gate.evaluate(self.intent, items, now=NOW)
        self.assertFalse(decision.qualified)
        self.assertIn(items[0].control_id, decision.failed_controls)
        self.assertIn(items[1].control_id, decision.failed_controls)

    def test_missing_verifier_cannot_self_certify_production(self) -> None:
        gate = ProductionQualificationGate(expected_binding=TARGET)
        self.assertFalse(gate.evaluate(self.intent, self.complete(), now=NOW).qualified)

    def test_expired_blocks(self) -> None:
        items = self.complete()
        items[0] = evidence(items[0].control_id, days=31)
        self.assertIn(
            "SOURCE_ADMISSION",
            self.gate.evaluate(self.intent, items, now=NOW).expired_controls,
        )

    def test_market_optional(self) -> None:
        intent = DeploymentIntent("STAGING", "africa-south1", market_intelligence_enabled=False)
        self.assertNotIn(self.gate.MARKET_CONTROL, self.gate.required_controls(intent))

    def test_live_and_destructive_effects_are_forbidden(self) -> None:
        with self.assertRaises(PermissionError):
            DeploymentIntent(
                "PRODUCTION", "africa-south1", live_financial_effects_enabled=True
            ).validate()
        with self.assertRaises(PermissionError):
            DeploymentIntent(
                "PRODUCTION", "africa-south1", destructive_actions_enabled=True
            ).validate()

    def test_secret_ref_is_rejected(self) -> None:
        secret_shaped = "s" + "k-" + ("x" * 26)
        with self.assertRaises(ValueError):
            ProviderEvidence(
                "X",
                EvidenceState.VERIFIED,
                "p",
                secret_shaped,
                "2026-08-11T00:00:00+00:00",
            ).validate(now=NOW)

    def test_unverified_is_missing(self) -> None:
        items = self.complete()
        items[0] = replace(items[0], state=EvidenceState.UNVERIFIED)
        self.assertIn(
            items[0].control_id,
            self.gate.evaluate(self.intent, items, now=NOW).missing_controls,
        )


if __name__ == "__main__":
    unittest.main()
