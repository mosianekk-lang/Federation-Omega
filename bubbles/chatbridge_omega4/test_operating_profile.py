from __future__ import annotations

import os
import tempfile
import unittest

from .models import GovernanceCapsule
from .operating_profile import OperatingProfile
from .runtime import ChatBridgeOmega4
from .store import ChatBridgeStore


class ChatBridgeOperatingProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = ChatBridgeOmega4(
            ChatBridgeStore(os.path.join(self.tmp.name, "chatbridge.sqlite3"))
        )
        self.capsule = GovernanceCapsule(
            owner="Kim Kagiso Mosiane",
            project="Forest-First",
            workstream="failure-knowledge",
            adapter="FOREST_FIRST_CORE",
            objective="Resume the current creative research workstream.",
            exact_next_action="Continue the highest-value safe research/build action.",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_default_profile_is_automatically_bound_and_restored(self) -> None:
        self.runtime.backup("demo", self.capsule, hot_state={"state": "READY"})
        restored = self.runtime.restore("demo", destination_session_key="dest-default")
        self.assertEqual(restored["hot_state"], {"state": "READY"})
        self.assertEqual(
            restored["operating_profile"]["execution_posture"],
            "EXECUTE_VERIFY_READBACK",
        )
        self.assertTrue(restored["restore_directives"]["reconcile_not_rebuild"])
        self.assertTrue(restored["restore_directives"]["creator_mode"])
        self.assertTrue(restored["restore_directives"]["federation_route_scan"])
        self.assertTrue(restored["restore_directives"]["realityguard_assurance"])
        self.assertTrue(restored["restore_directives"]["pre_owner_assurance"])
        self.assertEqual(
            restored["restore_directives"]["assurance_policy"],
            "SYSTEM_QA_BEFORE_OWNER",
        )
        self.assertEqual(
            restored["restore_directives"]["major_change_discovery_policy"],
            "AUDIT_FIRST_BEFORE_ARCHITECTURE",
        )
        self.assertTrue(restored["pre_owner_assurance_required"])
        self.assertEqual(restored["operating_profile_source"], "CHECKPOINT_BOUND")

    def test_namespace_specific_profile_restores_working_intelligence_contract(self) -> None:
        profile = OperatingProfile(
            profile_id="CBOP-FOREST-FIRST-1",
            forest_first=True,
            failure_knowledge=True,
            harmonic_evolution=True,
            inplace_evolution=True,
            evidenceops_assurance=True,
            background_compute_fabric=True,
            realityguard_assurance=True,
            pre_owner_assurance=True,
            live_bible_ref="drive:forest-first-live-bible",
            master_bible_ref="drive:omega-scientia-master",
            master_sync_ref="automation:federation-bible-sync",
            active_systems=(
                "Forest-First",
                "EvidenceOps",
                "RealityGuard",
                "FKLM/Harmonic Evolution",
                "IPEP",
                "Kimmie",
                "Bubbles",
            ),
        )
        self.runtime.backup(
            "forest-first",
            self.capsule,
            hot_state={"latest_delta": "DELTA 002"},
            operating_profile=profile,
        )
        restored = self.runtime.restore(
            "forest-first", destination_session_key="dest-forest-first"
        )
        self.assertTrue(restored["operating_profile"]["forest_first"])
        self.assertTrue(restored["operating_profile"]["failure_knowledge"])
        self.assertTrue(restored["operating_profile"]["inplace_evolution"])
        self.assertTrue(restored["operating_profile"]["background_compute_fabric"])
        self.assertTrue(restored["operating_profile"]["realityguard_assurance"])
        self.assertTrue(restored["operating_profile"]["pre_owner_assurance"])
        self.assertIn("RealityGuard", restored["operating_profile"]["active_systems"])
        self.assertEqual(restored["hot_state"]["latest_delta"], "DELTA 002")
        self.assertEqual(
            restored["restore_directives"]["anticipatory_policy"],
            "NEXT_WHY_NOW_AND_UNLOCKS",
        )
        self.assertEqual(
            restored["restore_directives"]["assurance_receipt_policy"],
            "REQUIRED_FOR_CONSEQUENTIAL_RECOMMENDATIONS",
        )

    def test_legacy_checkpoint_gets_safe_default_without_rewriting_history(self) -> None:
        self.runtime.store.backup(
            "legacy",
            self.capsule,
            hot_state={"legacy": True},
            warm_pointers=[],
            cold_pointers=[],
        )
        before = self.runtime.status("legacy")["checkpoint_fingerprint"]
        restored = self.runtime.restore("legacy", destination_session_key="dest-legacy")
        after = self.runtime.status("legacy")["checkpoint_fingerprint"]
        self.assertEqual(before, after)
        self.assertEqual(restored["operating_profile_source"], "LEGACY_DEFAULT_SYNTHESIZED")
        self.assertEqual(restored["hot_state"], {"legacy": True})
        self.assertTrue(restored["restore_directives"]["pre_owner_assurance"])


if __name__ == "__main__":
    unittest.main()
