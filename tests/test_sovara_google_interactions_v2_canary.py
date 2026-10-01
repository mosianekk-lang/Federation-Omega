from __future__ import annotations

import unittest
import importlib.util
from pathlib import Path

from scripts.run_google_interactions_v2_canary import _normalize_interaction_response

ROOT = Path(__file__).resolve().parents[1]
_profile_spec = importlib.util.spec_from_file_location("phoenix_core_test_profile", ROOT / "tests/phoenix_core_test_profile.py")
_profile = importlib.util.module_from_spec(_profile_spec)
_profile_spec.loader.exec_module(_profile)
_profile.attach_source_case(globals(), ROOT, "SovaraWorkflowSourceContracts")


class SovaraGoogleInteractionsV2CanaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = (
            ROOT / "scripts" / "run_google_interactions_v2_canary.py"
        ).read_text(encoding="utf-8")

    def test_declared_archive_or_source_collection_profile(self) -> None:
        self.assertIn(_profile.collection_profile(ROOT), {"SOURCE", "PORTABLE_CORE"})

    def test_runner_is_stateless_and_targets_interactions(self) -> None:
        self.assertIn('"store": False', self.runner)
        self.assertIn("gemini-3.8-flash", self.runner)
        self.assertIn("/locations/{location}/interactions", self.runner)
        self.assertIn("VERTEX_AI_INTERACTIONS_REST", self.runner)
        self.assertIn("interaction_id", self.runner)
        self.assertIn("interaction_status", self.runner)
        self.assertIn("semantic_verified", self.runner)
        self.assertNotIn("GEMINI_API_KEY", self.runner)

    def test_runner_declares_zero_external_effects(self) -> None:
        for marker in (
            '"provider_mutation_performed": False',
            '"iam_mutation_performed": False',
            '"secret_value_recorded": False',
            '"deployment_performed": False',
            '"traffic_change_performed": False',
            '"external_communication_performed": False',
        ):
            self.assertIn(marker, self.runner)

    def test_normalizer_accepts_direct_and_wrapped_interactions(self) -> None:
        interaction = {
            "id": "int_1",
            "status": "completed",
            "model": "gemini-3.8-flash",
            "steps": [{"type": "model_output", "content": [{"type": "text", "text": "ok"}]}],
        }
        direct, direct_meta = _normalize_interaction_response(interaction)
        self.assertEqual(direct["id"], "int_1")
        self.assertEqual(direct_meta["top_level_type"], "dict")

        wrapped, wrapped_meta = _normalize_interaction_response({"interaction": interaction})
        self.assertEqual(wrapped["id"], "int_1")
        self.assertEqual(wrapped_meta["wrapper"], "interaction")

        listed, listed_meta = _normalize_interaction_response([{"interaction": interaction}])
        self.assertEqual(listed["id"], "int_1")
        self.assertEqual(listed_meta["wrapper"], "list_single_interaction")

    def test_normalizer_fails_closed_on_ambiguous_list(self) -> None:
        a = {"id": "int_a", "status": "completed", "steps": []}
        b = {"id": "int_b", "status": "completed", "steps": []}
        normalized, meta = _normalize_interaction_response([a, b])
        self.assertEqual(normalized, {})
        self.assertEqual(meta["wrapper"], "ambiguous_list")
        self.assertEqual(meta["candidate_count"], 2)

    def test_normalizer_selects_single_completed_interaction_from_event_list(self) -> None:
        pending = {"id": "int_p", "status": "in_progress", "steps": []}
        done = {
            "id": "int_done",
            "status": "completed",
            "model": "gemini-3.8-flash",
            "steps": [{"type": "model_output", "content": [{"type": "text", "text": "ok"}]}],
        }
        normalized, meta = _normalize_interaction_response(
            [{"interaction": pending}, {"interaction": done}]
        )
        self.assertEqual(normalized["id"], "int_done")
        self.assertEqual(meta["wrapper"], "list_completed_interaction")


if __name__ == "__main__":
    unittest.main()
