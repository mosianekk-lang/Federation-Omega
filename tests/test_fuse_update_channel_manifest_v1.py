from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fuse_update_channel" / "manifest.json"


class FuseUpdateChannelManifestV1Tests(unittest.TestCase):
    def load(self) -> dict:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)
        return data

    def test_schema_and_stable_channel(self) -> None:
        data = self.load()
        self.assertEqual("FUSE_UPDATE_MANIFEST_V1", data["schema"])
        self.assertEqual("stable", data["channel"])
        self.assertGreaterEqual(int(data["sequence"]), 1)

    def test_required_truth_fields_exist(self) -> None:
        data = self.load()
        required = {
            "artifacts",
            "authority_class",
            "capability_deltas",
            "issued_at",
            "llm_context",
            "min_client_version",
            "route_deltas",
            "summary",
            "valid_until",
            "warnings",
            "llm_context_sha256",
            "manifest_body_sha256",
        }
        self.assertFalse(required - set(data))

    def test_current_sequence_carries_durable_scheduler_and_currentness(self) -> None:
        data = self.load()
        if int(data["sequence"]) >= 8:
            ctx = data["llm_context"]
            self.assertEqual(
                "FUSE_DURABLE_SCHEDULER_BUS_V1",
                ctx["durable_scheduler"],
            )
            self.assertEqual(
                "FUSE_CAPABILITY_TRUTH_CURRENTNESS_V1",
                ctx["capability_truth_currentness"],
            )
            self.assertEqual(
                "FCOA_CURRENTNESS_GATE_V1",
                ctx["fcoa_currentness_gate"],
            )
            self.assertEqual(
                "ISSUE_1648_SUCCEEDED_AND_CLOSED",
                ctx["durable_scheduler_live_canary"],
            )

    def test_external_authority_is_not_inherited(self) -> None:
        data = self.load()
        ctx = data["llm_context"]
        rule = str(ctx.get("external_effect_rule", ""))
        self.assertIn("NEVER_GRANT_EXTERNAL_AUTHORITY", rule)
        self.assertIn("WITH_EFFECT_GATES", data["authority_class"])

    def test_artifact_names_are_unique(self) -> None:
        data = self.load()
        names = [str(x["name"]) for x in data["artifacts"]]
        self.assertEqual(len(names), len(set(names)))

    def test_warnings_preserve_open_proof_boundaries(self) -> None:
        data = self.load()
        warnings = " ".join(str(x) for x in data["warnings"])
        self.assertIn("effectful", warnings.lower())
        self.assertIn("Windows", warnings)


if __name__ == "__main__":
    unittest.main()
