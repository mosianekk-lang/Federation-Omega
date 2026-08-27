import unittest

from ao_harmonic_v3.failure_win_proof_convertibility import (
    ConvertibilityReason,
    EvidenceKind,
    ExecutionPhase,
    ProofConvertibilityClassifier,
    ProofEvidence,
    SemanticSurface,
    SurfaceSearchBudget,
)


class ProofConvertibilityClassifierTests(unittest.TestCase):
    def surface(
        self,
        receiver="Formation Omega",
        operation="standalone core export",
        runtime="Phoenix reduced core",
        interface="python unittest discovery",
        contract="export portability",
    ):
        return SemanticSurface(receiver, operation, runtime, interface, contract)

    def failure(self, **overrides):
        values = dict(
            evidence_id="failure-1",
            surface=self.surface(),
            phase=ExecutionPhase.RUNTIME,
            observed_success=False,
            material=True,
            actual_execution_started=True,
            proof_refs=("run:failed",),
        )
        values.update(overrides)
        return ProofEvidence(**values)

    def recovery(self, **overrides):
        values = dict(
            evidence_id="recovery-1",
            surface=self.surface(),
            phase=ExecutionPhase.READBACK,
            observed_success=True,
            material=True,
            actual_execution_started=True,
            independent_readback=True,
            reversible=True,
            proof_refs=("run:green", "commit:exact-head"),
        )
        values.update(overrides)
        return ProofEvidence(**values)

    def test_formation_export_failure_and_unittest_repair_are_convertible(self):
        decision = ProofConvertibilityClassifier.pair(self.failure(), self.recovery())
        self.assertTrue(decision.convertible)
        self.assertEqual(decision.reason, ConvertibilityReason.CONVERTIBLE)
        self.assertTrue(decision.surface_fingerprint.startswith("ssf-"))
        self.assertGreater(decision.proof_score, 0)

    def test_same_receiver_is_not_enough_when_semantic_surface_differs(self):
        cloud_run = SemanticSurface(
            "Bubbles",
            "operator health contract",
            "Google Cloud Run",
            "/health and /contract",
            "provider operator semantic readback",
        )
        apps_script = SemanticSurface(
            "Bubbles",
            "apps script source authority",
            "Google Apps Script",
            "clasp source canary",
            "source authority mutation proof",
        )
        failure = self.failure(evidence_id="apps-script-failure", surface=apps_script)
        recovery = self.recovery(evidence_id="cloud-run-success", surface=cloud_run)
        decision = ProofConvertibilityClassifier.pair(failure, recovery)
        self.assertFalse(decision.convertible)
        self.assertEqual(decision.reason, ConvertibilityReason.SURFACE_MISMATCH)

    def test_cross_receiver_trust_transfer_is_rejected(self):
        recovery = self.recovery(
            surface=SemanticSurface(
                "Federation Omega",
                "standalone core export",
                "Phoenix reduced core",
                "python unittest discovery",
                "export portability",
            )
        )
        decision = ProofConvertibilityClassifier.pair(self.failure(), recovery)
        self.assertFalse(decision.convertible)
        self.assertEqual(decision.reason, ConvertibilityReason.RECEIVER_MISMATCH)

    def test_jarvis_harness_contamination_is_test_harness_noise(self):
        evidence = self.failure(
            evidence_id="jarvis-monkeypatch",
            phase=ExecutionPhase.TEST_HARNESS,
            harness_defect=True,
        )
        classified = ProofConvertibilityClassifier.classify(evidence)
        self.assertEqual(classified.kind, EvidenceKind.TEST_HARNESS_NOISE)
        self.assertEqual(classified.reason, ConvertibilityReason.TEST_HARNESS_NOISE)
        self.assertFalse(classified.promotable)

    def test_reality_guard_stale_ancestry_is_admission_noise(self):
        evidence = self.failure(
            evidence_id="realityguard-stale-base",
            phase=ExecutionPhase.ADMISSION,
            admission_failure=True,
            actual_execution_started=False,
        )
        classified = ProofConvertibilityClassifier.classify(evidence)
        self.assertEqual(classified.kind, EvidenceKind.ADMISSION_NOISE)
        self.assertEqual(classified.reason, ConvertibilityReason.ADMISSION_NOISE)

    def test_missing_owner_bootstrap_credential_is_authority_hold(self):
        evidence = self.failure(
            evidence_id="apps-script-no-clasprc",
            phase=ExecutionPhase.SETUP,
            actual_execution_started=False,
            authority_current=False,
            owner_secret_required=True,
        )
        classified = ProofConvertibilityClassifier.classify(evidence)
        self.assertEqual(classified.kind, EvidenceKind.AUTHORITY_HOLD)
        self.assertEqual(classified.reason, ConvertibilityReason.AUTHORITY_HOLD)

    def test_success_without_antecedent_is_retained_but_not_promoted(self):
        evidence = self.recovery(evidence_id="bubbles-cloud-run-health")
        classified = ProofConvertibilityClassifier.classify(evidence)
        self.assertEqual(classified.kind, EvidenceKind.SUCCESS_ONLY)
        self.assertEqual(classified.reason, ConvertibilityReason.SUCCESS_ONLY)
        self.assertFalse(classified.promotable)

    def test_real_success_becomes_convertible_only_after_same_surface_pair(self):
        recovery = self.recovery(evidence_id="paired-success")
        self.assertEqual(
            ProofConvertibilityClassifier.classify(recovery).kind,
            EvidenceKind.SUCCESS_ONLY,
        )
        decision = ProofConvertibilityClassifier.pair(self.failure(), recovery)
        self.assertTrue(decision.convertible)
        self.assertEqual(decision.reason, ConvertibilityReason.CONVERTIBLE)

    def test_setup_failure_does_not_become_behavior_failure(self):
        evidence = self.failure(
            evidence_id="setup-failed",
            phase=ExecutionPhase.SETUP,
            actual_execution_started=False,
        )
        classified = ProofConvertibilityClassifier.classify(evidence)
        self.assertNotEqual(classified.kind, EvidenceKind.FAILURE_FACT)
        self.assertEqual(classified.reason, ConvertibilityReason.FAILURE_NOT_EXECUTED)

    def test_success_without_independent_readback_cannot_pair(self):
        recovery = self.recovery(independent_readback=False)
        decision = ProofConvertibilityClassifier.pair(self.failure(), recovery)
        self.assertFalse(decision.convertible)
        self.assertEqual(decision.reason, ConvertibilityReason.NO_INDEPENDENT_READBACK)

    def test_synthetic_success_cannot_pair_for_behavior_proof(self):
        recovery = self.recovery(synthetic=True)
        decision = ProofConvertibilityClassifier.pair(self.failure(), recovery)
        self.assertFalse(decision.convertible)
        self.assertEqual(decision.reason, ConvertibilityReason.SYNTHETIC_ONLY)

    def test_non_reversible_recovery_is_not_convertible(self):
        decision = ProofConvertibilityClassifier.pair(
            self.failure(),
            self.recovery(reversible=False),
        )
        self.assertFalse(decision.convertible)
        self.assertEqual(decision.reason, ConvertibilityReason.NON_REVERSIBLE_ROUTE)

    def test_rank_pairs_applies_hard_gates_before_score(self):
        good = (self.failure(), self.recovery())
        mismatch = (
            self.failure(evidence_id="f2"),
            self.recovery(
                evidence_id="r2",
                surface=SemanticSurface(
                    "Bubbles",
                    "operator health contract",
                    "Google Cloud Run",
                    "/health",
                    "provider semantic readback",
                ),
            ),
        )
        lanes = ProofConvertibilityClassifier.rank_pairs((mismatch, good))
        self.assertEqual(len(lanes), 1)
        self.assertEqual(lanes[0].failure_id, "failure-1")

    def test_surface_search_budget_demotes_repeated_same_surface_misses(self):
        budget = SurfaceSearchBudget(maximum_misses=2)
        surface = self.surface()
        self.assertFalse(budget.should_demote(surface))
        self.assertEqual(budget.record_miss(surface), 1)
        self.assertFalse(budget.should_demote(surface))
        self.assertEqual(budget.record_miss(surface), 2)
        self.assertTrue(budget.should_demote(surface))
        budget.reset(surface)
        self.assertFalse(budget.should_demote(surface))

    def test_surface_fingerprint_is_normalized_and_deterministic(self):
        first = self.surface()
        second = SemanticSurface(
            "  Formation   Omega ",
            "Standalone CORE export",
            "PHOENIX reduced core",
            "python unittest discovery",
            "export portability",
        )
        self.assertEqual(first.fingerprint, second.fingerprint)

    def test_ambiguous_surface_fails_closed(self):
        evidence = self.failure(
            surface=SemanticSurface(
                "Bubbles",
                "",
                "Google Cloud Run",
                "/health",
                "provider semantic readback",
            )
        )
        classified = ProofConvertibilityClassifier.classify(evidence)
        self.assertEqual(classified.reason, ConvertibilityReason.AMBIGUOUS_SURFACE)
        self.assertFalse(classified.promotable)


if __name__ == "__main__":
    unittest.main()
