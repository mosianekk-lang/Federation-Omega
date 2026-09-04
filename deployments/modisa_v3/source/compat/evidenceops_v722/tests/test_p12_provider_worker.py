from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "p12_provider_worker.py"


def run(mode: str, workspace: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            mode,
            "--workspace",
            str(workspace),
            "--event-name",
            "test",
            "--run-id",
            "123",
            "--run-attempt",
            "1",
            "--workflow",
            "unit-test",
            "--sha",
            "abc",
            "--ref",
            "refs/heads/test",
            "--repository",
            "mosianekk-lang/Federation-Omega",
        ],
        text=True,
        capture_output=True,
    )


class ProviderWorkerTests(unittest.TestCase):
    def test_checkpoint_resume_verify(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            checkpoint = run("checkpoint", workspace)
            self.assertEqual(checkpoint.returncode, 75)
            state = json.loads((workspace / "state" / "worker_state.json").read_text())
            self.assertEqual(state["status"], "CHECKPOINTED_BEFORE_SIMULATED_CRASH")
            self.assertEqual(state["external_effects"], 0)

            resumed = run("resume", workspace)
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            receipt = json.loads((workspace / "reports" / "p12_provider_worker_receipt.json").read_text())
            self.assertTrue(receipt["proof"]["crash_resume"])
            self.assertTrue(receipt["proof"]["rollback_canary"])
            self.assertTrue(receipt["proof"]["replicated_state"])
            self.assertEqual(receipt["proof"]["external_effects"], 0)
            self.assertEqual(receipt["maturity"], "OPERATIONAL_VERIFIED_SCOPED_GITHUB_ACTIONS_WORKER")

            verified = run("verify", workspace)
            self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_consequential_actions_are_denied(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.assertEqual(run("checkpoint", workspace).returncode, 75)
            self.assertEqual(run("resume", workspace).returncode, 0)
            policy = json.loads((workspace / "reports" / "policy_log.json").read_text())
            self.assertEqual(policy["allow_decision"]["decision"], "ALLOW")
            self.assertEqual(
                policy["deny_decision"],
                {
                    "action": "external_send",
                    "decision": "DENY",
                    "reason": "A2 authority absent",
                },
            )


if __name__ == "__main__":
    unittest.main()
