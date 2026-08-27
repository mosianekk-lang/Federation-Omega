import unittest

from formation_omega.source_convergence import (
    AdmissionPlan,
    AdmissionState,
    ChangeCapsule,
    SourceConvergenceClass,
    classify_convergence,
    reanchor_manifest,
    required_admission_actions,
)


def capsule():
    return ChangeCapsule.create(
        change_id="CHANGE-PR628",
        mission_id="MISSION-MCE-PR628",
        base_sha="OLDMAIN",
        candidate_head_sha="CANDIDATE",
        candidate_blobs={
            "chatbridge-companion/manifest.json": "cand-manifest",
            "chatbridge-companion/src/background.js": "cand-background",
            "bef-edge-agent/manifest.json": "cand-edge",
        },
        base_blobs={
            "chatbridge-companion/manifest.json": "base-manifest",
            "chatbridge-companion/src/background.js": "base-background",
            "bef-edge-agent/manifest.json": None,
        },
        semantic_domains=("BEF", "CHATBRIDGE", "DPF"),
        required_checks=("AIRLOCK", "BUBBLES", "LEAK_GUARD"),
        proof_boundary="Source admission does not prove runtime installation.",
        rollback_ref="PR628-OLD-HEAD",
    )


class FormationOmegaSourceConvergenceTests(unittest.TestCase):
    def test_disjoint_stale_candidate_is_safe_to_reanchor(self):
        item = capsule()
        decision = classify_convergence(
            item,
            current_main_sha="NEWMAIN",
            current_blobs={
                "chatbridge-companion/manifest.json": "base-manifest",
                "chatbridge-companion/src/background.js": "base-background",
                "bef-edge-agent/manifest.json": None,
            },
        )
        self.assertEqual(decision.classification, SourceConvergenceClass.DISJOINT_STALE_BY_ANCESTRY)
        self.assertTrue(decision.safe_auto_reanchor)
        self.assertEqual(set(decision.overlay_paths), set(item.candidate_blobs))
        self.assertEqual(reanchor_manifest(item, decision), dict(item.candidate_blobs))

    def test_current_base_does_not_require_rebase(self):
        item = capsule()
        decision = classify_convergence(
            item,
            current_main_sha="OLDMAIN",
            current_blobs={
                "chatbridge-companion/manifest.json": "base-manifest",
                "chatbridge-companion/src/background.js": "base-background",
                "bef-edge-agent/manifest.json": None,
            },
        )
        self.assertEqual(decision.classification, SourceConvergenceClass.CURRENT_BASE)
        self.assertTrue(decision.safe_auto_reanchor)

    def test_already_applied_candidate_is_recognized(self):
        item = capsule()
        decision = classify_convergence(item, current_main_sha="NEWMAIN", current_blobs=dict(item.candidate_blobs))
        self.assertEqual(decision.classification, SourceConvergenceClass.ALREADY_APPLIED)
        self.assertTrue(decision.safe_auto_reanchor)
        self.assertFalse(decision.overlay_paths)

    def test_third_blob_on_same_path_is_semantic_conflict(self):
        item = capsule()
        decision = classify_convergence(
            item,
            current_main_sha="NEWMAIN",
            current_blobs={
                "chatbridge-companion/manifest.json": "third-manifest",
                "chatbridge-companion/src/background.js": "base-background",
                "bef-edge-agent/manifest.json": None,
            },
        )
        self.assertEqual(decision.classification, SourceConvergenceClass.SEMANTIC_CONFLICT)
        self.assertFalse(decision.safe_auto_reanchor)
        self.assertEqual(decision.conflicting_paths, ("chatbridge-companion/manifest.json",))
        with self.assertRaisesRegex(ValueError, "not allowed"):
            reanchor_manifest(item, decision)

    def test_explicit_compatible_overlap_requires_reconciled_candidate_not_auto_overlay(self):
        item = capsule()
        decision = classify_convergence(
            item,
            current_main_sha="NEWMAIN",
            current_blobs={
                "chatbridge-companion/manifest.json": "third-manifest",
                "chatbridge-companion/src/background.js": "base-background",
                "bef-edge-agent/manifest.json": None,
            },
            semantic_compatibility={"chatbridge-companion/manifest.json": True},
        )
        self.assertEqual(decision.classification, SourceConvergenceClass.STRUCTURALLY_COMPATIBLE)
        self.assertFalse(decision.safe_auto_reanchor)
        self.assertEqual(decision.compatible_overlap_paths, ("chatbridge-companion/manifest.json",))

    def test_admission_train_forces_exact_head_checks_and_main_recheck(self):
        item = capsule()
        decision = classify_convergence(
            item,
            current_main_sha="NEWMAIN",
            current_blobs={
                "chatbridge-companion/manifest.json": "base-manifest",
                "chatbridge-companion/src/background.js": "base-background",
                "bef-edge-agent/manifest.json": None,
            },
        )
        plan = AdmissionPlan.create(capsule=item, decision=decision, reanchored_candidate_head_sha="REANCHORED")
        self.assertEqual(plan.state, AdmissionState.EXACT_HEAD_CHECKS_REQUIRED)
        self.assertEqual(set(required_admission_actions(plan)), {"RUN_CHECK:AIRLOCK", "RUN_CHECK:BUBBLES", "RUN_CHECK:LEAK_GUARD"})
        plan = plan.with_checks(("AIRLOCK", "BUBBLES", "LEAK_GUARD"))
        self.assertEqual(plan.state, AdmissionState.CHECKS_PASSED)
        self.assertEqual(required_admission_actions(plan), ("RECHECK_CURRENT_MAIN",))
        stale = plan.recheck_main("MOVED_AGAIN")
        self.assertEqual(stale.state, AdmissionState.STALE_RECLASSIFY)
        self.assertEqual(required_admission_actions(stale), ("RECLASSIFY_AGAINST_FRESH_MAIN",))
        ready = plan.recheck_main("NEWMAIN")
        self.assertEqual(ready.state, AdmissionState.READY_TO_MERGE)
        merged = ready.merged(merge_sha="MERGE123")
        self.assertEqual(merged.state, AdmissionState.MERGED_READBACK_REQUIRED)
        admitted = merged.readback(observed_main_sha="MERGE123")
        self.assertEqual(admitted.state, AdmissionState.ADMITTED)
        self.assertEqual(required_admission_actions(admitted), ())

    def test_admission_plan_rejects_unproven_checks(self):
        item = capsule()
        decision = classify_convergence(
            item,
            current_main_sha="NEWMAIN",
            current_blobs={
                "chatbridge-companion/manifest.json": "base-manifest",
                "chatbridge-companion/src/background.js": "base-background",
                "bef-edge-agent/manifest.json": None,
            },
        )
        plan = AdmissionPlan.create(capsule=item, decision=decision, reanchored_candidate_head_sha="H")
        plan = plan.with_checks(("AIRLOCK",))
        self.assertEqual(plan.state, AdmissionState.EXACT_HEAD_CHECKS_REQUIRED)
        with self.assertRaisesRegex(ValueError, "checks pass"):
            plan.recheck_main("NEWMAIN")


if __name__ == "__main__":
    unittest.main()
