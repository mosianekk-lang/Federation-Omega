import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from evidenceops.provenance_passport import (
    PassportError,
    build_passport,
    build_passports,
    verify_passport,
    verify_passports,
)


def digest(char: str) -> str:
    return char * 64


class ProvenancePassportTests(unittest.TestCase):
    def manifest(self, corpus_id: str = "CORPUS-A") -> dict:
        return {
            "corpus_id": corpus_id,
            "records": [
                {"record_id": "r-3", "sha256": digest("c"), "metadata": {"type": "audio"}},
                {"record_id": "r-1", "sha256": digest("a")},
                {"record_id": "r-2", "sha256": digest("b")},
            ],
        }

    def test_build_is_deterministic_and_order_independent(self) -> None:
        first = self.manifest()
        second = deepcopy(first)
        second["records"].reverse()
        self.assertEqual(build_passport(first), build_passport(second))

    def test_odd_leaf_tree_and_all_inclusion_proofs_verify(self) -> None:
        passport = build_passport(self.manifest())
        result = verify_passport(passport)
        self.assertTrue(result["ok"])
        self.assertEqual(result["record_count"], 3)

    def test_tampering_fails_closed(self) -> None:
        passport = build_passport(self.manifest())
        passport["records"][0]["record"]["sha256"] = digest("d")
        with self.assertRaisesRegex(PassportError, "receipt mismatch"):
            verify_passport(passport)

    def test_duplicate_record_id_is_rejected(self) -> None:
        manifest = self.manifest()
        manifest["records"][1]["record_id"] = manifest["records"][0]["record_id"]
        with self.assertRaisesRegex(PassportError, "duplicate record_id"):
            build_passport(manifest)

    def test_invalid_digest_is_rejected(self) -> None:
        manifest = self.manifest()
        manifest["records"][0]["sha256"] = "not-a-digest"
        with self.assertRaisesRegex(PassportError, "64-character"):
            build_passport(manifest)

    def test_multiple_corpora_verify(self) -> None:
        passports = build_passports([self.manifest("CORPUS-A"), self.manifest("CORPUS-B")])
        result = verify_passports(passports)
        self.assertEqual(result["corpus_count"], 2)
        self.assertEqual(result["record_count"], 6)

    def test_duplicate_corpus_id_is_rejected(self) -> None:
        passports = [build_passport(self.manifest()), build_passport(self.manifest())]
        with self.assertRaisesRegex(PassportError, "duplicate corpus_id"):
            verify_passports(passports)

    def test_cli_build_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            passport = root / "passport.json"
            manifest.write_text(json.dumps(self.manifest()), encoding="utf-8")
            build = subprocess.run(
                [sys.executable, "-m", "evidenceops.provenance_passport.cli", "build", str(manifest), "-o", str(passport)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            verify = subprocess.run(
                [sys.executable, "-m", "evidenceops.provenance_passport.cli", "verify", str(passport)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(verify.returncode, 0, verify.stderr)
            self.assertTrue(json.loads(verify.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
