from __future__ import annotations

import os
import tempfile
import unittest

from .models import GovernanceCapsule
from .operating_profile import OperatingProfile
from .restore_assurance import RestoreAttestation
from .runtime import ChatBridgeOmega4
from .store import ChatBridgeStore


class RestoreAssuranceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = ChatBridgeOmega4(ChatBridgeStore(os.path.join(self.tmp.name, "cb.sqlite3")))
        self.capsule = GovernanceCapsule(
            owner="Kim Kagiso Mosiane",
            project="Forest First",
            workstream="forest-first-justice-os",
            adapter="FOREST_FIRST_CORE",
            objective="Continue the verified Forest-First workstream without rebuilding.",
            exact_next_action="Resume the highest-value safe IPEP/FKLM action.",
            external_effects_allowed=True,
        )
        self.profile = OperatingProfile(
            "CBOP-FOREST-FIRST-1",
            forest_first=True,
            failure_knowledge=True,
            harmonic_evolution=True,
            inplace_evolution=True,
            evidenceops_assurance=True,
            background_compute_fabric=True,
            live_bible_ref="drive:local-live-bible",
            active_systems=("Forest-First", "EvidenceOps", "IPEP", "Bubbles"),
        )
        self.runtime.backup(
            "forest-first",
            self.capsule,
            hot_state={"delta": "002"},
            warm_pointers=["drive:local-live-bible"],
            operating_profile=self.profile,
        )
        self.expected = self.runtime.restore(
            "forest-first", destination_session_key="dest-test"
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def attestation(self, **changes) -> RestoreAttestation:
        base = dict(
            namespace_key=self.expected["namespace_key"],
            generation_id=self.expected["generation_id"],
            handoff_id=self.expected["handoff_id"],
            destination_session_key="dest-test",
            checkpoint_fingerprint=self.expected["checkpoint_fingerprint"],
            operating_profile_id=self.expected["operating_profile"]["profile_id"],
            governance_capsule_ref="capsule",
            restored_objective=self.expected["governance"]["objective"],
            restored_next_action=self.expected["governance"]["exact_next_action"],
            active_systems=tuple(self.expected["operating_profile"]["active_systems"]),
            live_bible_ref=self.expected["operating_profile"]["live_bible_ref"],
            execution_posture=self.expected["operating_profile"]["execution_posture"],
            reconcile_not_rebuild=self.expected["operating_profile"]["reconcile_not_rebuild"],
            delta_checked=True,
            resume_started=True,
            observed_state="RESTORED_AND_RESUMED",
        )
        base.update(changes)
        return RestoreAttestation(**base)

    def test_matching_destination_attestation_passes(self) -> None:
        result = self.runtime.assess_restore_attestation(self.expected, self.attestation())
        self.assertEqual(result["conformance_state"], "PASS")
        self.assertEqual(result["finding_count"], 0)
        self.assertFalse(result["consequential_hold"])

    def test_wrong_generation_and_posture_require_repair(self) -> None:
        result = self.runtime.assess_restore_attestation(
            self.expected,
            self.attestation(
                generation_id="wrong-generation",
                execution_posture="REPORT_OPTIONS_ASK_PROCEED",
                delta_checked=False,
            ),
        )
        self.assertEqual(result["conformance_state"], "REPAIR_REQUIRED")
        self.assertTrue(result["consequential_hold"])
        classes = {item["drift_class"] for item in result["findings"]}
        self.assertIn("GENERATION_ID_DRIFT", classes)
        self.assertIn("EXECUTION_POSTURE_DRIFT", classes)
        self.assertIn("DELTA_CHECK_MISSING", classes)

    def test_missing_specialist_or_resume_is_warning_when_core_state_matches(self) -> None:
        result = self.runtime.assess_restore_attestation(
            self.expected,
            self.attestation(active_systems=("Forest-First",), resume_started=False),
        )
        self.assertEqual(result["conformance_state"], "WARN")
        self.assertFalse(result["consequential_hold"])
        classes = {item["drift_class"] for item in result["findings"]}
        self.assertIn("SPECIALIST_FORMATION_DRIFT", classes)
        self.assertIn("RESUME_NOT_STARTED", classes)

    def test_verified_post_checkpoint_delta_supersedes_mutable_semantics_only(self) -> None:
        current_objective = "Advance the newly verified FKLM replay programme."
        current_next = "Run a blind second environment-fit replay."
        self.expected["current_state_override"] = {
            "verified": True,
            "source": "LOCAL_LIVE_BIBLE_DELTA",
            "source_ref": "DELTA-006",
            "restored_objective": current_objective,
            "restored_next_action": current_next,
            "required_systems": list(self.expected["operating_profile"]["active_systems"]),
            "live_bible_ref": self.expected["operating_profile"]["live_bible_ref"],
        }
        observed = self.attestation(
            restored_objective=current_objective,
            restored_next_action=current_next,
        )
        result = self.runtime.assess_restore_attestation(self.expected, observed)
        self.assertEqual(result["conformance_state"], "PASS")
        self.assertEqual(result["semantic_source"], "LOCAL_LIVE_BIBLE_DELTA")
        self.assertEqual(result["semantic_source_ref"], "DELTA-006")
        self.assertEqual(result["finding_count"], 0)

    def test_unverified_semantic_override_is_rejected(self) -> None:
        self.expected["current_state_override"] = {
            "verified": False,
            "restored_next_action": "Invent a new action",
        }
        with self.assertRaises(ValueError):
            self.runtime.assess_restore_attestation(self.expected, self.attestation())


if __name__ == "__main__":
    unittest.main()
