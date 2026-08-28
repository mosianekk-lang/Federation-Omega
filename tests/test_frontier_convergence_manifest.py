import hashlib
import json
from pathlib import Path
import unittest


class FrontierConvergenceManifestTests(unittest.TestCase):
    MANIFESTS = (
        "governance/superior_logic_gemini_frontier_convergence_v1.json",
        "governance/frontier_convergence_os_v1_manifest.json",
    )

    def test_manifest_hashes_match_checked_out_source(self):
        repo = Path(__file__).resolve().parents[1]
        mismatches = []
        for manifest_path in self.MANIFESTS:
            manifest = json.loads((repo / manifest_path).read_text(encoding="utf-8"))
            for relative_path, expected_sha256 in manifest["source_files"].items():
                source_path = repo / relative_path
                if not source_path.is_file():
                    mismatches.append(
                        {
                            "manifest": manifest_path,
                            "path": relative_path,
                            "expected_sha256": expected_sha256,
                            "actual_sha256": None,
                            "state": "MISSING",
                        }
                    )
                    continue
                actual_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
                if actual_sha256 != expected_sha256:
                    mismatches.append(
                        {
                            "manifest": manifest_path,
                            "path": relative_path,
                            "expected_sha256": expected_sha256,
                            "actual_sha256": actual_sha256,
                            "state": "HASH_MISMATCH",
                        }
                    )
        self.assertEqual(
            [],
            mismatches,
            "FRONTIER_SOURCE_MANIFEST_DRIFT="
            + json.dumps(mismatches, sort_keys=True, separators=(",", ":")),
        )

    def test_frontier_convergence_os_regression_court(self):
        repo = Path(__file__).resolve().parents[1]
        suite = unittest.defaultTestLoader.discover(
            str(repo / "tests"),
            pattern="test_frontier_convergence_os.py",
        )
        result = unittest.TestResult()
        suite.run(result)
        failures = [
            {"test": str(test), "message": message[-2000:]}
            for test, message in (*result.failures, *result.errors)
        ]
        self.assertTrue(
            result.wasSuccessful(),
            "FRONTIER_CONVERGENCE_OS_REGRESSION_FAILURE="
            + json.dumps(failures, sort_keys=True, separators=(",", ":")),
        )


if __name__ == "__main__":
    unittest.main()
