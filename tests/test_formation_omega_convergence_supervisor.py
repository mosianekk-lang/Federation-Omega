import unittest

from formation_omega.convergence_supervisor import (
    ConvergenceSupervisor,
    ProviderSnapshot,
    SupervisorAction,
)
from formation_omega.source_convergence import ChangeCapsule, AdmissionState


class ConvergenceSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.supervisor = ConvergenceSupervisor()
        self.capsule = ChangeCapsule.create(
            change_id="CHANGE-LUNO-001",
            mission_id="MISSION-LUNO-001",
            base_sha="main-a",
            candidate_head_sha="feature-a",
            candidate_blobs={"a.py": "blob-candidate"},
            base_blobs={"a.py": "blob-base"},
            semantic_domains=("luno", "github-main"),
            required_checks=("Airlock", "Bubbles", "LeakGuard"),
            proof_boundary="source admission only",
            rollback_ref="feature-a",
        )

    def snapshot(self, *, main="main-a", head="feature-a", blob="blob-base", checks=None):
        return ProviderSnapshot.create(
            main_sha=main,
            candidate_head_sha=head,
            current_blobs={"a.py": blob},
            check_results=checks or {},
            evidence_refs=(f"provider:{main}:{head}",),
        )

    def test_current_base_requires_exact_head_checks(self):
        decision = self.supervisor.compile(self.capsule, self.snapshot())
        self.assertEqual(decision.action, SupervisorAction.RUN_REQUIRED_CHECKS)
        self.assertEqual(decision.admission.state, AdmissionState.EXACT_HEAD_CHECKS_REQUIRED)
        self.assertIsNone(decision.permit)
        self.assertFalse(decision.source_mutation_ready)

    def test_disjoint_stale_ancestry_compiles_lossless_reanchor_permit(self):
        snapshot = self.snapshot(main="main-b", head="feature-a", blob="blob-base")
        decision = self.supervisor.compile(self.capsule, snapshot)
        self.assertEqual(decision.action, SupervisorAction.REANCHOR_EXACT_BLOBS)
        self.assertTrue(decision.source_mutation_ready)
        self.assertEqual(decision.overlay_manifest, {"a.py": "blob-candidate"})
        self.assertEqual(decision.permit.expected_main_sha, "main-b")
        self.assertFalse(decision.permit.external_effect)
        self.assertFalse(decision.permit.authority_created)

    def test_semantic_conflict_fails_closed_and_becomes_learning(self):
        snapshot = self.snapshot(main="main-b", blob="third-blob")
        decision = self.supervisor.compile(
            self.capsule,
            snapshot,
            failure_recurrence_count=2,
        )
        self.assertEqual(decision.action, SupervisorAction.RECONCILE_SEMANTIC_CONFLICT)
        self.assertIsNone(decision.permit)
        self.assertIsNotNone(decision.failure_learning)
        self.assertEqual(
            decision.failure_learning.failure_event.required_response,
            "MANDATORY_OMEGA_SCIENTIST_ARCHITECTURE_REVIEW",
        )
        self.assertEqual(decision.failure_learning.resolver.occurrence_count, 1)
        self.assertTrue(decision.failure_learning.continuity_checkpoint)
        self.assertTrue(decision.failure_learning.maturation_transaction["idempotency_key"])

    def test_stale_main_after_checks_reclassifies_without_mission_restart(self):
        checked = self.snapshot(
            checks={"Airlock": True, "Bubbles": True, "LeakGuard": True}
        )
        initial = self.supervisor.compile(self.capsule, checked)
        self.assertEqual(initial.action, SupervisorAction.RECHECK_CURRENT_MAIN)
        self.assertEqual(initial.admission.state, AdmissionState.CHECKS_PASSED)

        fresh = self.snapshot(
            main="main-b",
            checks={"Airlock": True, "Bubbles": True, "LeakGuard": True},
        )
        decision = self.supervisor.recheck_before_merge(
            capsule=self.capsule,
            convergence=initial.convergence,
            admission=initial.admission,
            fresh_snapshot=fresh,
        )
        self.assertEqual(decision.action, SupervisorAction.RECLASSIFY_FRESH_MAIN)
        self.assertEqual(decision.admission.state, AdmissionState.STALE_RECLASSIFY)
        self.assertIn("PRESERVE_CHANGE_CAPSULE", decision.reason_codes)
        self.assertIsNotNone(decision.failure_learning)

    def test_candidate_head_drift_invalidates_prior_checks(self):
        checked = self.snapshot(
            checks={"Airlock": True, "Bubbles": True, "LeakGuard": True}
        )
        initial = self.supervisor.compile(self.capsule, checked)
        fresh = self.snapshot(
            head="feature-b",
            checks={"Airlock": True, "Bubbles": True, "LeakGuard": True},
        )
        decision = self.supervisor.recheck_before_merge(
            capsule=self.capsule,
            convergence=initial.convergence,
            admission=initial.admission,
            fresh_snapshot=fresh,
        )
        self.assertEqual(decision.action, SupervisorAction.RECLASSIFY_FRESH_MAIN)
        self.assertIn("CHECKS_INVALIDATED", decision.reason_codes)

    def test_fresh_recheck_compiles_expected_head_merge_permit(self):
        checked = self.snapshot(
            checks={"Airlock": True, "Bubbles": True, "LeakGuard": True}
        )
        initial = self.supervisor.compile(self.capsule, checked)
        decision = self.supervisor.recheck_before_merge(
            capsule=self.capsule,
            convergence=initial.convergence,
            admission=initial.admission,
            fresh_snapshot=checked,
        )
        self.assertEqual(decision.action, SupervisorAction.MERGE_EXPECTED_HEAD)
        self.assertTrue(decision.source_mutation_ready)
        decision.permit.assert_fresh(checked)

        drifted = self.snapshot(
            main="main-b",
            checks={"Airlock": True, "Bubbles": True, "LeakGuard": True},
        )
        with self.assertRaisesRegex(RuntimeError, "STALE_MAIN_RECLASSIFY_REQUIRED"):
            decision.permit.assert_fresh(drifted)

    def test_signed_main_readback_is_required_for_closure(self):
        checked = self.snapshot(
            checks={"Airlock": True, "Bubbles": True, "LeakGuard": True}
        )
        initial = self.supervisor.compile(self.capsule, checked)
        ready = self.supervisor.recheck_before_merge(
            capsule=self.capsule,
            convergence=initial.convergence,
            admission=initial.admission,
            fresh_snapshot=checked,
        )
        closed = self.supervisor.readback_after_merge(
            capsule=self.capsule,
            convergence=initial.convergence,
            admission=ready.admission,
            merge_sha="merge-1",
            observed_main_sha="merge-1",
        )
        self.assertEqual(closed.action, SupervisorAction.CLOSED)
        self.assertEqual(closed.admission.state, AdmissionState.ADMITTED)


if __name__ == "__main__":
    unittest.main()
