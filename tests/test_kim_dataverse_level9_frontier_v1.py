from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_level9_frontier_v1 import FrontierState, InstitutionalFrontierCandidate, evaluate_frontier_candidates


class KimDataverseLevel9FrontierTests(unittest.TestCase):
    def test_reversible_authority_neutral_falsifiable_gain_candidate_can_enter_shadow(self) -> None:
        decision = evaluate_frontier_candidates((InstitutionalFrontierCandidate("c", "self-model option market", True, True, True, 0.2),))[0]
        self.assertEqual(FrontierState.SHADOW, decision.state)

    def test_authority_or_external_effect_candidate_is_held(self) -> None:
        decision = evaluate_frontier_candidates((InstitutionalFrontierCandidate("c", "authority expansion", True, False, True, 10, external_effect=True),))[0]
        self.assertEqual(FrontierState.HELD, decision.state)

    def test_unfalsifiable_frontier_claim_is_held(self) -> None:
        decision = evaluate_frontier_candidates((InstitutionalFrontierCandidate("c", "magic", True, True, False, 1),))[0]
        self.assertEqual(FrontierState.HELD, decision.state)


if __name__ == "__main__":
    unittest.main()
