from pathlib import Path
import unittest

from federation.superior_logic_convergence_measurement import (
    ObservationMode,
    ProfileObservation,
)
from frontier_convergence.slos_convergence_runner import (
    BASELINE_OBSERVATION_PATH,
    OMEGA_ONE_HOST_PAIR_COUNT,
    run_hosted_shadow_campaign,
    run_omega_one_host_campaign,
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

    def test_omega_one_host_bridge_is_source_bound_and_no_effect(self):
        captured = {}

        def campaign_runner(**kwargs):
            captured.update(kwargs)
            return {
                "campaign_state": "QUALIFIED_HOST_OBSERVED_NO_EFFECT",
                "observed_pair_count": 30,
                "cold_replayable_pair_count": 30,
                "semantic_parity": True,
                "one_canonical_receipt_per_mission": True,
                "provider_effects": False,
                "external_effect": False,
            }

        receipt = run_omega_one_host_campaign(
            environment={
                "GITHUB_ACTIONS": "true",
                "RUNNER_ENVIRONMENT": "github-hosted",
                "GITHUB_RUN_ID": "123456",
                "GITHUB_SHA": "d" * 40,
            },
            campaign_runner=campaign_runner,
        )
        self.assertEqual(
            "QUALIFIED_HOST_OBSERVED_NO_EFFECT", receipt["campaign_state"]
        )
        self.assertEqual(OMEGA_ONE_HOST_PAIR_COUNT, captured["pair_count"])
        self.assertEqual("123456", captured["runtime_run_id"])
        self.assertEqual("d" * 40, captured["source_sha"])
        self.assertEqual("github-hosted", captured["runtime_environment"])
        self.assertFalse(receipt["provider_effects"])
        self.assertFalse(receipt["external_effect"])

    def test_omega_one_host_bridge_rejects_non_actions_runtime(self):
        with self.assertRaisesRegex(ValueError, "GITHUB_ACTIONS_HOST_IDENTITY_REQUIRED"):
            run_omega_one_host_campaign(environment={})

    def test_omega_one_host_bridge_rejects_self_hosted_runtime(self):
        with self.assertRaisesRegex(ValueError, "GITHUB_HOSTED_RUNNER_REQUIRED"):
            run_omega_one_host_campaign(
                environment={
                    "GITHUB_ACTIONS": "true",
                    "RUNNER_ENVIRONMENT": "self-hosted",
                }
            )


if __name__ == "__main__":
    unittest.main()
