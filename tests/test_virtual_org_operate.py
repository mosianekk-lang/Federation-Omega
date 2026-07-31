import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


OPERATE = Path(__file__).resolve().parents[1] / "virtual-org" / "operate.py"


class VirtualOrganizationSelectionTests(unittest.TestCase):
    def test_approval_checkpoint_cannot_displace_safe_lane(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            org = root / "virtual-org"
            org.mkdir()
            registry = {
                "lanes": [
                    {
                        "lane_id": "ORG-REVENUE-001",
                        "state": "CHECKPOINTED",
                        "priority": 99,
                        "approval_gate": "FOUNDER_APPROVAL_REQUIRED",
                        "next_action": "Publish externally",
                    },
                    {
                        "lane_id": "ORG-PROOF-001",
                        "state": "TEST_PASSED",
                        "priority": 96,
                        "next_action": "Build reusable validator",
                    },
                    {
                        "lane_id": "ORG-AUDIO-001",
                        "state": "BLOCKED",
                        "priority": 100,
                        "next_action": "Run canary",
                    },
                ]
            }
            (org / "lane-registry.json").write_text(json.dumps(registry), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(OPERATE)],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            cycle = json.loads((org / "status" / "latest-cycle.json").read_text(encoding="utf-8"))
            self.assertEqual(cycle["top_safe_lane"], "ORG-PROOF-001")
            self.assertEqual(cycle["safe_executable_count"], 1)
            self.assertEqual(cycle["approval_checkpoint_count"], 1)
            self.assertEqual(cycle["blocked_count"], 1)


if __name__ == "__main__":
    unittest.main()
