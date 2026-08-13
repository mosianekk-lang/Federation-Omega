from __future__ import annotations

import subprocess
import sys
import unittest

from evidenceops.build_system.chat_failure_resilience import classify_failure


class ChatFailureResilienceAirlockTests(unittest.TestCase):
    def test_focused_chat_failure_resilience_suite_executes(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "evidenceops/build_system/tests",
                "-p",
                "test_chat_failure_resilience.py",
                "-v",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertIn("Ran 13 tests", combined)
        self.assertIn("OK", combined)

    def test_specific_causal_surface_outranks_generic_stall_symptom(self):
        tool = classify_failure({"message": "tool call timeout", "tool_inflight": True})
        self.assertEqual("TOOL_OR_CONNECTOR_FAILURE", tool[0].failure_class)
        self.assertIn("STALL_TIMEOUT", {candidate.failure_class for candidate in tool})

        interrupted = classify_failure({
            "message": "Connection interrupted. Waiting for the complete answer"
        })
        self.assertEqual("TRANSPORT_INTERRUPTION", interrupted[0].failure_class)
        self.assertIn("STALL_TIMEOUT", {candidate.failure_class for candidate in interrupted})


if __name__ == "__main__":
    unittest.main()
