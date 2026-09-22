from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_institutional_qualification_v1 import (
    InstitutionalEvidence,
    qualify_institution,
)
from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import AutonomyDebt
from benchmarking.cfbe_omega.kim_dataverse_persistent_carrier_contract_v1 import CarrierQualification


BASE_SIGNALS = {
    "objective_ecology": True,
    "resource_economy": True,
    "owner_interruption_firewall": True,
    "autonomy_debt": True,
    "dynamic_topology": True,
    "digital_twin": True,
    "measured_gap_evolution": True,
    "historical_replay": True,
    "adversarial_qualification": True,
    "architectural_entropy_controller": True,
    "causal_learning": True,
    "no_self_authority_promotion": True,
    "unified_autonomic_loops": True,
    "dynamic_reorganization": True,
    "multi_timescale_objective_optimization": False,
    "constitutional_amendment_court": True,
    "capability_market": True,
    "cross_provider_counterfactuals": False,
    "information_value_budgeting": False,
    "negative_knowledge_diffusion": True,
}


def carrier() -> CarrierQualification:
    return CarrierQualification(
        carrier_id="worker",
        level7_continuity_candidate=True,
        missing=(),
        provider_verified=False,
        external_effect_authorized=False,
        receipt="sha256:carrier",
    )


class KimDataverseInstitutionalQualificationTests(unittest.TestCase):
    def test_source_complete_without_observed_cohorts_cannot_claim_level7(self) -> None:
        result = qualify_institution(
            source_signals=BASE_SIGNALS,
            evidence=InstitutionalEvidence(
                autonomy_debt=AutonomyDebt(),
                owner_interruption_rate=None,
                maintenance_self_resolution_rate=None,
                recovery_self_resolution_rate=None,
                observed_maintenance_episodes=0,
                observed_recovery_episodes=0,
                observed_no_chat_resumes=0,
                observed_owner_value_pairs=0,
                provider_native_receipts=(),
                rollback_verified=True,
                regression_passed=True,
                sustained_value_verified=False,
            ),
            carrier=carrier(),
        )
        self.assertFalse(result.level7_operational_claim)
        self.assertIn("PERSISTENT_NO_CHAT_CONTINUITY_UNPROVEN", result.empirical_holds)
        self.assertIn("SUSTAINED_OWNER_VALUE_UNPROVEN", result.empirical_holds)

    def test_full_observed_level7_evidence_can_claim_level7_only_when_source_signals_pass(self) -> None:
        result = qualify_institution(
            source_signals=BASE_SIGNALS,
            evidence=InstitutionalEvidence(
                autonomy_debt=AutonomyDebt(),
                owner_interruption_rate=0.02,
                maintenance_self_resolution_rate=0.95,
                recovery_self_resolution_rate=0.95,
                observed_maintenance_episodes=12,
                observed_recovery_episodes=12,
                observed_no_chat_resumes=4,
                observed_owner_value_pairs=30,
                provider_native_receipts=("provider:one",),
                rollback_verified=True,
                regression_passed=True,
                sustained_value_verified=True,
            ),
            carrier=carrier(),
        )
        self.assertEqual(7, result.highest_qualified_level)
        self.assertTrue(result.level7_operational_claim)
        self.assertFalse(result.level8_operational_claim)
        self.assertEqual((), result.empirical_holds)

    def test_high_owner_interruption_rate_blocks_level7(self) -> None:
        result = qualify_institution(
            source_signals=BASE_SIGNALS,
            evidence=InstitutionalEvidence(
                autonomy_debt=AutonomyDebt(owner_continuations=10),
                owner_interruption_rate=0.20,
                maintenance_self_resolution_rate=0.95,
                recovery_self_resolution_rate=0.95,
                observed_maintenance_episodes=12,
                observed_recovery_episodes=12,
                observed_no_chat_resumes=4,
                observed_owner_value_pairs=30,
                provider_native_receipts=("provider:one",),
                rollback_verified=True,
                regression_passed=True,
                sustained_value_verified=True,
            ),
            carrier=carrier(),
        )
        self.assertFalse(result.level7_operational_claim)

    def test_source_level8_flags_do_not_override_empirical_holds(self) -> None:
        signals = dict(BASE_SIGNALS)
        signals.update(
            {
                "multi_timescale_objective_optimization": True,
                "cross_provider_counterfactuals": True,
                "information_value_budgeting": True,
            }
        )
        result = qualify_institution(
            source_signals=signals,
            evidence=InstitutionalEvidence(
                autonomy_debt=AutonomyDebt(),
                owner_interruption_rate=0.01,
                maintenance_self_resolution_rate=1.0,
                recovery_self_resolution_rate=1.0,
                observed_maintenance_episodes=10,
                observed_recovery_episodes=10,
                observed_no_chat_resumes=3,
                observed_owner_value_pairs=30,
                provider_native_receipts=(),
                rollback_verified=False,
                regression_passed=True,
                sustained_value_verified=True,
            ),
            carrier=carrier(),
        )
        self.assertFalse(result.level8_operational_claim)
        self.assertIn("ROLLBACK_UNVERIFIED", result.empirical_holds)

    def test_receipt_is_deterministic(self) -> None:
        evidence = InstitutionalEvidence(
            autonomy_debt=AutonomyDebt(),
            owner_interruption_rate=None,
            maintenance_self_resolution_rate=None,
            recovery_self_resolution_rate=None,
            observed_maintenance_episodes=0,
            observed_recovery_episodes=0,
            observed_no_chat_resumes=0,
            observed_owner_value_pairs=0,
            provider_native_receipts=(),
            rollback_verified=True,
            regression_passed=True,
            sustained_value_verified=False,
        )
        first = qualify_institution(source_signals=BASE_SIGNALS, evidence=evidence, carrier=carrier())
        second = qualify_institution(source_signals=BASE_SIGNALS, evidence=evidence, carrier=carrier())
        self.assertEqual(first.receipt, second.receipt)


if __name__ == "__main__":
    unittest.main()
