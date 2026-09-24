from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPANION = ROOT / "clients" / "sol62_browser_companion"


class Sol62BrowserCompanionSourceContractTests(unittest.TestCase):
    def test_manifest_is_fuse_owned_observer_not_ui_mutator(self):
        manifest = json.loads((COMPANION / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertIn("https://chatgpt.com/*", manifest["host_permissions"])
        self.assertNotIn("scripting", manifest["permissions"])

    def test_exact_chat_load_failure_maps_to_route_local_failure_code(self):
        content = (COMPANION / "content.js").read_text(encoding="utf-8")
        self.assertIn("Could not load this ChatGPT conversation", content)
        self.assertIn("CHATGPT_CONVERSATION_LOAD_FAILED", content)
        self.assertNotIn(".click(", content)
        self.assertNotIn("Retry", content)

    def test_companion_never_embeds_provider_or_fuse_credentials(self):
        worker = (COMPANION / "service_worker.js").read_text(encoding="utf-8")
        manifest = (COMPANION / "manifest.json").read_text(encoding="utf-8")
        combined = worker + manifest
        self.assertNotIn("OPENAI_API_KEY", combined)
        self.assertNotIn("sk-", combined)
        self.assertIn("chrome.storage.session", worker)
        self.assertIn("NO_FUSE_SESSION", worker)

    def test_relay_failure_never_asserts_mission_failure(self):
        worker = (COMPANION / "service_worker.js").read_text(encoding="utf-8")
        readme = (COMPANION / "README.md").read_text(encoding="utf-8")
        self.assertIn("Do not turn a relay failure into a mission-state assertion", worker)
        self.assertIn("preserve mission identity/state", readme)
        self.assertIn("READBACK FIRST", readme)


if __name__ == "__main__":
    unittest.main()
