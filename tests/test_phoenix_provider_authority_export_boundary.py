import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "phoenix" / "export_policy.json"
PROVIDER_AUTHORITY_CONTROL_TEST = (
    "tests/test_bubbles_provider_authority_probe_readmission.py"
)
PST_RECOVERY_DIAGNOSTIC_TEST = "tests/test_pst_recovery_failure_diagnostic.py"
SOURCE_ONLY_CONTROL_TESTS = (
    PROVIDER_AUTHORITY_CONTROL_TEST,
    PST_RECOVERY_DIAGNOSTIC_TEST,
)


class PhoenixProviderAuthorityExportBoundaryTests(unittest.TestCase):
    def test_source_repository_control_tests_are_excluded_from_core(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        excluded = policy["core"]["excluded_test_globs"]

        for control_test in SOURCE_ONLY_CONTROL_TESTS:
            with self.subTest(control_test=control_test):
                self.assertIn(control_test, excluded)

    def test_provider_authority_control_depends_on_source_repository_surfaces(self):
        source = (ROOT / PROVIDER_AUTHORITY_CONTROL_TEST).read_text(
            encoding="utf-8"
        )
        self.assertIn(".github", source)
        self.assertIn("github_airlock_policy.json", source)

    def test_pst_recovery_diagnostic_depends_on_source_repository_surfaces(self):
        source = (ROOT / PST_RECOVERY_DIAGNOSTIC_TEST).read_text(encoding="utf-8")
        self.assertIn(".github/workflows/evidenceops-pst-corpus-v2-extract.yml", source)


if __name__ == "__main__":
    unittest.main()
