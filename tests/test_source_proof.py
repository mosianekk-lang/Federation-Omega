import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from omega_one.source_proof import assert_sources_verified, git_blob_sha, verify_sources


class SourceProofTests(unittest.TestCase):
    def test_git_blob_sha_matches_known_empty_blob(self):
        self.assertEqual(git_blob_sha(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")

    def test_verifies_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "item.txt").write_text("proof\n", encoding="utf-8")
            expected = git_blob_sha((root / "item.txt").read_bytes())
            manifest = root / "SOURCE_BASE.json"
            manifest.write_text(json.dumps({"files": {"item.txt": expected}}), encoding="utf-8")
            self.assertTrue(assert_sources_verified(manifest)[0].valid)
            (root / "item.txt").write_text("changed\n", encoding="utf-8")
            self.assertFalse(verify_sources(manifest)[0].valid)
            with self.assertRaisesRegex(ValueError, "SOURCE_VERIFICATION_FAILED"):
                assert_sources_verified(manifest)

    def test_path_escape_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "SOURCE_BASE.json"
            manifest.write_text(json.dumps({"files": {"../outside": "x"}}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SOURCE_PATH_ESCAPES_ROOT"):
                verify_sources(manifest)


if __name__ == "__main__":
    unittest.main()
