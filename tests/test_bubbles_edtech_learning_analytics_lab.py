from __future__ import annotations

import unittest

from bubbles.edtech_learning_analytics_lab import (
    EdTechLearningAnalyticsLab,
    LearnerSignal,
    SupportRecommendation,
    reject_sensitive_payload,
)


class EdTechLearningAnalyticsLabTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lab = EdTechLearningAnalyticsLab()

    def test_recruiter_demo_is_synthetic_and_hash_bound(self) -> None:
        demo = self.lab.recruiter_demo()
        receipt = demo["receipt"]
        self.assertEqual("SYNTHETIC_LOCAL_DETERMINISTICALLY_TESTED", receipt["state"])
        self.assertEqual(64, len(receipt["receipt_sha256"]))
        self.assertEqual(3, receipt["record_count"])
        self.assertIn("Synthetic", receipt["truth_boundary"])

    def test_support_routing_requires_human_review(self) -> None:
        signal = LearnerSignal("SYN-100", "LMS", 1, 0.5, 5.0, 0.6, "synthetic:lms")
        result = self.lab.recommend(signal)
        self.assertTrue(result.human_review_required)
        self.assertEqual("TUTORING_REVIEW", result.recommendation)
        self.assertIsNone(result.automated_academic_decision)

    def test_high_consequence_automated_decision_is_rejected(self) -> None:
        result = SupportRecommendation(
            learner_key="SYN-101",
            recommendation="SUPPORT_REVIEW",
            reason_codes=("LOW_PLATFORM_ENGAGEMENT",),
            human_review_required=True,
            automated_academic_decision="FAIL",
        )
        with self.assertRaises(ValueError):
            result.validate()

    def test_missing_human_review_is_rejected(self) -> None:
        result = SupportRecommendation(
            learner_key="SYN-102",
            recommendation="SUPPORT_REVIEW",
            reason_codes=("LOW_PLATFORM_ENGAGEMENT",),
            human_review_required=False,
        )
        with self.assertRaises(ValueError):
            result.validate()

    def test_real_identity_key_is_rejected(self) -> None:
        signal = LearnerSignal("STUDENT-12345", "LMS", 3, 0.8, 4.0, 0.8, "synthetic:lms")
        with self.assertRaises(ValueError):
            signal.validate()

    def test_unknown_source_system_is_rejected(self) -> None:
        signal = LearnerSignal("SYN-103", "SOCIAL_MEDIA", 3, 0.8, 4.0, 0.8, "synthetic:unknown")
        with self.assertRaises(ValueError):
            signal.validate()

    def test_missing_lineage_is_rejected(self) -> None:
        signal = LearnerSignal("SYN-104", "LMS", 3, 0.8, 4.0, 0.8, "")
        with self.assertRaises(ValueError):
            signal.validate()

    def test_sensitive_fields_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            reject_sensitive_payload({"learner_key": "SYN-1", "race": "synthetic-value"})

    def test_duplicate_learner_keys_fail_closed(self) -> None:
        one = LearnerSignal("SYN-105", "LMS", 3, 0.8, 4.0, 0.8, "synthetic:lms:a")
        two = LearnerSignal("SYN-105", "TUTORING", 2, 0.7, 3.0, 0.7, "synthetic:tutoring:b")
        with self.assertRaises(ValueError):
            self.lab.run((one, two))

    def test_no_real_outcome_or_deployment_claim(self) -> None:
        demo = self.lab.recruiter_demo()
        forbidden = " ".join(demo["forbidden_claims"]).lower()
        self.assertIn("production", forbidden)
        self.assertIn("real student", forbidden)
        self.assertIn("director of educational technology", forbidden)


if __name__ == "__main__":
    unittest.main()
