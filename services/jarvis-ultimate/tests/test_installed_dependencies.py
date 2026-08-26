import importlib
import importlib.metadata
import inspect
import os
import sys
import tempfile
import unittest
from unittest.mock import patch


class InstalledDependencyTests(unittest.TestCase):
    def test_locked_direct_versions_are_installed(self):
        expected = {
            "google-adk": "2.1.0",
            "google-genai": "1.75.0",
            "cryptography": "46.0.0",
        }
        actual = {
            distribution: importlib.metadata.version(distribution)
            for distribution in expected
        }
        self.assertEqual(actual, expected)

    def test_adk_workflow_nodes_execute_without_provider_credentials(self):
        with tempfile.TemporaryDirectory() as state_dir, patch.dict(
            os.environ,
            {"JARVIS_STATE_DIR": state_dir, "JARVIS_PROVIDER": "offline"},
            clear=True,
        ):
            sys.modules.pop("jarvis.agent", None)
            agent = importlib.import_module("jarvis.agent")
            self.assertEqual(type(agent.root_agent).__name__, "Workflow")
            reasoning_events = list(agent.governed_reasoning("map objective"))
            self.assertEqual(len(reasoning_events), 1)
            self.assertTrue(reasoning_events[0].output["semanticFruit"])
            response_events = list(
                agent.emit_verified_response(
                    {
                        "answer": "Evidence-bounded installed-package response.",
                        "semanticFruit": True,
                        "learningHash": "test-learning-hash",
                        "providerMode": "offline",
                    }
                )
            )
            self.assertEqual(len(response_events), 1)
            self.assertEqual(response_events[0].output["providerMode"], "offline")

    def test_genai_sdk_call_contract_is_present_without_invocation(self):
        from google import genai
        from google.genai import types

        client_parameters = inspect.signature(genai.Client).parameters
        self.assertIn("enterprise", client_parameters)
        self.assertIn("http_options", client_parameters)
        self.assertTrue(inspect.isclass(types.GenerateContentConfig))


if __name__ == "__main__":
    unittest.main()
