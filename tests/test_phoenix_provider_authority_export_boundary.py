import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "phoenix" / "export_policy.json"
CONTROL_TEST = "tests/test_bubbles_provider_authority_probe_readmission.py"


class PhoenixProviderAuthorityExportBoundaryTests(unittest.TestCase):
    def test_source_repository_control_test_is_excluded_from_core(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertIn(CONTROL_TEST, policy["core"]["excluded_test_globs"])

    def test_control_test_depends_on_source_repository_surfaces(self):
        source = (ROOT / CONTROL_TEST).read_text(encoding="utf-8")
        self.assertIn(".github", source)
        self.assertIn("github_airlock_policy.json", source)


if __name__ == "__main__":
    unittest.main()
