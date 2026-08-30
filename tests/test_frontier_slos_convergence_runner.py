from pathlib import Path
import unittest

from federation.superior_logic_convergence_measurement import (
    ObservationMode,
    ProfileObservation,
)
from frontier_convergence.slos_convergence_runner import (
    BASELINE_OBSERVATION_PATH,
    run_hosted_shadow_campaign,
)


class FrontierSLOSConvergenceRunnerTests(unittest.TestCase):
    def test_hosted_shadow_campaign_executes_thirty_pairs_without_promotion(self):
        receipt = run_hosted_shadow_campaign(
            pair_count=30,
            run_id="TEST-RUN-30",
            source_sha="a" * 40,
        )
        self.assertEqual("HOSTED_SHADOW_30_OF_30_PASS", receipt["state"])
        self.assertEqual(30, receipt["pair_count"])
        self.assertEqual(30, receipt["hosted_shadow_pair_count"])
        self.assertEqual(0, receipt["observed_pair_count"])
        self.assertEqual(30, receipt["structural_pass_count"])
        self.assertTrue(receipt["zero_critical_omissions"])
        self.assertTrue(receipt["structural_candidate"])
        self.assertFalse(receipt["empirical_value_candidate"])
        self.assertFalse(receipt["stable_promotion_allowed"])
        self.assertFalse(receipt["provider_effects"])
        self.assertFalse(receipt["external_effect"])
        self.assertEqual("PRESERVED", receipt["full_doctrine_rollback"])
        self.assertEqual("0/30", receipt["observed_empirical_campaign_progress"])

    def test_campaign_receipt_is_deterministic_for_identical_host_identity(self):
        first = run_hosted_shadow_campaign(
            run_id="DETERMINISTIC-RUN",
            source_sha="b" * 40,
        )
        second = run_hosted_shadow_campaign(
            run_id="DETERMINISTIC-RUN",
            source_sha="b" * 40,
        )
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])
        self.assertEqual(first["pairs"], second["pairs"])

    def test_hosted_shadow_requires_at_least_thirty_pairs(self):
        with self.assertRaisesRegex(ValueError, "HOSTED_SHADOW_MINIMUM_30_PAIRS_REQUIRED"):
            run_hosted_shadow_campaign(pair_count=29)

    def test_baseline_is_source_bound_and_no_effect(self):
        self.assertTrue(Path(BASELINE_OBSERVATION_PATH).is_file())
        receipt = run_hosted_shadow_campaign(
            run_id="SOURCE-BOUND-RUN",
            source_sha="c" * 40,
        )
        self.assertRegex(receipt["baseline_observation_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            "FRONTIER_RUNTIME_QUALIFICATION_PROVIDER_DISABLED",
            receipt["runtime"],
        )

    def test_hosted_shadow_profile_without_proof_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "PROOF_REFERENCED_PROFILE_REQUIRED"):
            ProfileObservation(
                profile="HOSTED_SHADOW",
                mission_id="M1",
                mode=ObservationMode.HOSTED_SHADOW,
                active_controls=frozenset({"CONTROL"}),
                context_chars=1,
                tool_round_trips=0,
                owner_interventions=0,
                stale_state_rejected=True,
                duplicate_suppressed=True,
                trace_complete=True,
                proof_refs=(),
            )


if __name__ == "__main__":
    unittest.main()
