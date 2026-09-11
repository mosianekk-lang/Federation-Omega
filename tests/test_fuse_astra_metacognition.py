import unittest

from fuse_astra_semantic_kernel.epistemic import ClaimStatus
from fuse_astra_semantic_kernel.metacognition import ActionRisk, Decision, MetacognitionGovernor


class MetacognitionGovernorTests(unittest.TestCase):
    def setUp(self):
        self.governor = MetacognitionGovernor()

    def test_low_risk_possible_claim_can_proceed(self):
        advice = self.governor.advise(
            ClaimStatus.POSSIBLE,
            ActionRisk(0.1, 0.1, 0.1, 0.1),
        )
        self.assertEqual(advice.decision, Decision.PROCEED)

    def test_high_risk_requires_known(self):
        advice = self.governor.advise(
            ClaimStatus.LIKELY,
            ActionRisk(0.7, 0.2, 0.2, 0.2),
        )
        self.assertEqual(advice.decision, Decision.SEEK_EVIDENCE)

    def test_critical_known_still_requires_independent_verifier(self):
        advice = self.governor.advise(
            ClaimStatus.KNOWN,
            ActionRisk(0.9, 0.9, 0.9, 0.9),
            independent_verifier=False,
        )
        self.assertEqual(advice.decision, Decision.HOLD)

    def test_critical_known_with_verifier_can_proceed(self):
        advice = self.governor.advise(
            ClaimStatus.KNOWN,
            ActionRisk(0.9, 0.9, 0.9, 0.9),
            independent_verifier=True,
        )
        self.assertEqual(advice.decision, Decision.PROCEED)

    def test_contested_routes_to_experiment(self):
        advice = self.governor.advise(
            ClaimStatus.CONTESTED,
            ActionRisk(0.5, 0.3, 0.2, 0.2),
            experiment_available=True,
        )
        self.assertEqual(advice.decision, Decision.RUN_EXPERIMENT)

    def test_stale_never_proceeds(self):
        advice = self.governor.advise(
            ClaimStatus.STALE,
            ActionRisk(0.1, 0.1, 0.1, 0.1),
        )
        self.assertEqual(advice.decision, Decision.SEEK_EVIDENCE)


if __name__ == "__main__":
    unittest.main()
