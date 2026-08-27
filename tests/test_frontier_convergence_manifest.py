import hashlib
import json
from pathlib import Path
import unittest


class FrontierConvergenceManifestTests(unittest.TestCase):
    def test_manifest_hashes_match_checked_out_source(self):
        repo = Path(__file__).resolve().parents[1]
        manifest = json.loads(
            (repo / "governance/superior_logic_gemini_frontier_convergence_v1.json").read_text(encoding="utf-8")
        )
        for relative_path, expected_sha256 in manifest["source_files"].items():
            actual_sha256 = hashlib.sha256((repo / relative_path).read_bytes()).hexdigest()
            self.assertEqual(actual_sha256, expected_sha256, relative_path)


if __name__ == "__main__":
    unittest.main()
