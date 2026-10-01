from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from services.sol62_client_runtime.capability_registry import (
    REGISTRY_SCHEMA,
    built_in_bindings,
    compile_registry,
)


class Sol62CapabilityRegistryTests(unittest.TestCase):
    def test_full_current_chat_census_is_bound_without_false_server_promotion(self):
        rows = {row.capability_id: row for row in built_in_bindings(gateway_execution_ready=True)}
        expected = {
            "FUSE-GATEWAY",
            "GOOGLE-VERTEX-GEMINI",
            "KDV-GOOGLE-SHEETS",
            "FUSE-GENESIS-RESIDENT-EXECUTOR-V2",
            "CHATGPT-GPT-5.6-SOL",
            "WEB-INTELLIGENCE",
            "IMAGE-SEARCH",
            "IMAGE-GENERATION-EDITING",
            "PYTHON-PRIVATE",
            "PYTHON-USER-VISIBLE",
            "LINUX-CONTAINER",
            "FILES-LIBRARY",
            "GOOGLE-DRIVE",
            "GMAIL",
            "GOOGLE-CALENDAR",
            "GOOGLE-CONTACTS",
            "GITHUB",
            "OUTLOOK-EMAIL",
            "OUTLOOK-CALENDAR",
            "CANVA",
            "ADOBE-CREATIVE-CLOUD",
            "ADOBE-ACROBAT",
            "ADOBE-EXPRESS",
            "REMOTE-DESKTOP-COMMANDER",
            "OPENAI-PLATFORM",
            "AUTOMATION-SCHEDULER",
            "PLUGIN-MANAGEMENT",
            "PERSONAL-CONTEXT",
            "MEMORY",
            "SUMMARY-RECOVERY",
            "GENUI",
            "BOOKING-COM",
            "LONA-TRADING-ASSISTANT",
            "GOOGLE-APPS-SCRIPT",
            "GOOGLE-CLOUD",
            "GOOGLE-AI-STUDIO",
            "GEMINI-DEVELOPER-API",
            "MICROSOFT-GRAPH",
            "MICROSOFT-TEAMS",
            "SHAREPOINT",
            "POWER-AUTOMATE",
            "POWER-APPS",
            "POWER-BI",
            "DATAVERSE",
            "MICROSOFT-COPILOT",
            "GITHUB-COPILOT",
            "OLLAMA",
            "LM-STUDIO",
            "OPENROUTER",
            "X",
        }
        self.assertTrue(expected.issubset(rows))
        self.assertTrue(rows["FUSE-GATEWAY"].runtime_native)
        self.assertTrue(rows["FUSE-GATEWAY"].callable)
        self.assertFalse(rows["GOOGLE-DRIVE"].runtime_native)
        self.assertFalse(rows["GOOGLE-DRIVE"].callable)
        self.assertEqual(rows["GOOGLE-DRIVE"].maturity, "CHAT_BOUND_RUNTIME_UNPROVEN")
        self.assertEqual(rows["MICROSOFT-GRAPH"].maturity, "ESTATE_KNOWN_CHAT_UNBOUND")

    def test_unready_gateway_downgrades_native_provider_callability(self):
        rows = {row.capability_id: row for row in built_in_bindings(gateway_execution_ready=False)}
        self.assertFalse(rows["FUSE-GATEWAY"].callable)
        self.assertFalse(rows["GOOGLE-VERTEX-GEMINI"].callable)
        self.assertEqual(rows["GOOGLE-VERTEX-GEMINI"].maturity, "CONFIGURED_UNBOUND")

    def test_fresh_snapshot_can_hydrate_current_client_binding_without_granting_authority(self):
        payload = """[
          {
            "capability_id": "GOOGLE-DRIVE",
            "family": "GOOGLE_WORKSPACE",
            "transport": "CHAT_SESSION_TOOL",
            "maturity": "CHAT_SESSION_CALLABLE",
            "callable": true,
            "runtime_native": false,
            "authority": "CURRENT_CLIENT_ACTION_SPECIFIC",
            "operations": ["read", "write"]
          }
        ]"""
        with patch.dict(os.environ, {"SOL62_EXTERNAL_CAPABILITY_SNAPSHOT_JSON": payload}):
            registry = compile_registry(gateway_execution_ready=False)
        self.assertEqual(registry["schema"], REGISTRY_SCHEMA)
        rows = {row["capability_id"]: row for row in registry["bindings"]}
        self.assertTrue(rows["GOOGLE-DRIVE"]["callable"])
        self.assertFalse(rows["GOOGLE-DRIVE"]["runtime_native"])
        self.assertEqual(rows["GOOGLE-DRIVE"]["authority"], "CURRENT_CLIENT_ACTION_SPECIFIC")
        self.assertIn("REGISTERED_NE_CALLABLE", registry["truth_boundary"])


if __name__ == "__main__":
    unittest.main()
