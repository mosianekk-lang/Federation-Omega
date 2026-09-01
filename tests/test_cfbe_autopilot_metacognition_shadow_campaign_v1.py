from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from benchmarking.cfbe_omega.autopilot_metacognition_empirical_court_v1 import EvidenceMode
from benchmarking.cfbe_omega.autopilot_metacognition_shadow_campaign_v1 import (
    PAIR_COUNT,
    RESUME_COUNT,
    _case,
    _first_order_baseline,
    build_pairs,
    build_resume_observations,
    run_campaign,
)
from benchmarking.cfbe_omega.federation_autopilot_metacognition_v1 import MetaAction, metacognitive_assessment


HEAD = "c" * 40


class AutoPilotMetaCognitionShadowCampaignV1Tests(unittest.TestCase):
    def test_oracle_covers_all_six_meta_actions_exactly_five_times(self) -> None:
        expected = [_case(index)[1] for index in range(PAIR_COUNT)]
        self.assertEqual(set(MetaAction), set(expected))
        for action in MetaAction:
            self.assertEqual(5, expected.count(action))

    def test_candidate_matches_all_oracles_while_first_order_baseline_misses_challenge_and_reflect(self) -> None:
        baseline_misses = []
        for index in range(PAIR_COUNT):
            state, expected, _ = _case(index)
            self.assertIs(expected, metacognitive_assessment(state).action)
            if _first_order_baseline(state).action is not expected:
                baseline_misses.append(expected)
        self.assertEqual(10, len(baseline_misses))
        self.assertEqual({MetaAction.CHALLENGE, MetaAction.REFLECT}, set(baseline_misses))

    def test_local_pair_builder_is_synthetic_and_meets_quality_and_burden_shape(self) -> None:
        pairs = build_pairs(HEAD, evidence_mode=EvidenceMode.SYNTHETIC_SHADOW, measure=False)
        self.assertEqual(PAIR_COUNT, len(pairs))
        self.assertTrue(all(item.evidence_mode is EvidenceMode.SYNTHETIC_SHADOW for item in pairs))
        self.assertTrue(all(item.candidate_reflection_used for item in pairs))
        self.assertTrue(all(item.candidate_quality >= item.baseline_quality for item in pairs))
        self.assertGreater(sum(item.baseline_owner_interventions for item in pairs), 0)
        self.assertEqual(0, sum(item.candidate_owner_interventions for item in pairs))

    def test_resume_builder_executes_ten_distinct_child_processes_without_effect_or_drift(self) -> None:
        observations = build_resume_observations(HEAD, evidence_mode=EvidenceMode.SYNTHETIC_SHADOW)
        self.assertEqual(RESUME_COUNT, len(observations))
        self.assertTrue(all(item.process_before != item.process_after for item in observations))
        self.assertTrue(all(item.resumed for item in observations))
        self.assertEqual(0, sum(item.duplicate_effect_count for item in observations))
        self.assertFalse(any(item.state_drift for item in observations))
        self.assertTrue(all(item.independent_readback for item in observations))

    def test_local_campaign_cannot_claim_hosted_shadow_or_full_autopilot(self) -> None:
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "", "GITHUB_RUN_ID": ""}, clear=False):
            result = run_campaign(HEAD, measure=False)
        self.assertFalse(result["github_actions_runtime"])
        self.assertEqual("SYNTHETIC_SHADOW", result["evidence_mode"])
        self.assertEqual("STRUCTURAL_ONLY_SYNTHETIC_SHADOW", result["empirical_receipt"]["decision"])
        self.assertFalse(result["empirical_receipt"]["hosted_shadow_qualified"])
        self.assertFalse(result["empirical_receipt"]["observed_empirical_candidate"])
        self.assertFalse(result["empirical_receipt"]["provider_runtime_candidate"])
        self.assertFalse(result["full_autopilot_runtime_proven"])
        self.assertFalse(result["provider_effect_authorized"])
        self.assertFalse(result["stable_promotion_authorized"])

    def test_hosted_classification_requires_runtime_evidence_not_caller_mode_argument(self) -> None:
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "", "GITHUB_RUN_ID": ""}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "HOSTED_SHADOW_REQUIRES_GITHUB_ACTIONS_RUNTIME"):
                run_campaign(HEAD, require_github_actions=True, measure=False)

    def test_invalid_source_sha_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "HOSTED_SHADOW_SOURCE_SHA_INVALID"):
            build_pairs("not-a-sha", evidence_mode=EvidenceMode.SYNTHETIC_SHADOW, measure=False)


if __name__ == "__main__":
    unittest.main()
