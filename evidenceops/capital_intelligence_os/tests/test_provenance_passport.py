import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout

from evidenceops.provenance_passport.cli import main as cli_main
from evidenceops.provenance_passport.core import (
    build_record_passport,
    canonical_record_sha256,
    inclusion_proof,
    merkle_root,
    validate_many,
    validate_passport,
    verify_inclusion_proof,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "evidenceops"
    / "provenance_passport"
    / "fixtures"
    / "synthetic-odd-passport.json"
)


class ProvenancePassportTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_synthetic_fixture_validates(self):
        result = validate_passport(self.fixture)
        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.leaf_count, 5)
        self.assertEqual(result.proofs_checked, 5)
        self.assertEqual(result.receipt_status, "VERIFIED")

    def test_odd_leaf_duplicate_rule_and_proofs(self):
        leaves = [item["sha256"] for item in self.fixture["files"]]
        self.assertEqual(merkle_root(leaves), self.fixture["integrity"]["merkle_root"])
        for index, leaf in enumerate(leaves):
            proof = inclusion_proof(leaves, index)
            self.assertTrue(
                verify_inclusion_proof(
                    leaf, proof, self.fixture["integrity"]["merkle_root"]
                )
            )

    def test_tampering_is_detected(self):
        tampered = copy.deepcopy(self.fixture)
        tampered["files"][0]["sha256"] = "0" * 64
        result = validate_passport(tampered)
        self.assertFalse(result.valid)
        self.assertTrue(
            any(
                "Merkle root mismatch" in error
                or "merkle_leaf differs" in error
                or "inclusion proof failed" in error
                for error in result.errors
            )
        )

    def test_record_passport_is_deterministic_for_fixed_metadata(self):
        records = [
            {"record_id": "A", "value": 1},
            {"record_id": "B", "value": 2},
            {"record_id": "C", "value": 3},
        ]
        kwargs = {
            "records": records,
            "passport_id": "EPP-TEST-001",
            "source": {"title": "Test", "contract": "TEST_V1"},
            "classification": "PUBLIC_SYNTHETIC_TEST",
            "generated_at": "2026-08-01T00:00:00+00:00",
        }
        first = build_record_passport(**kwargs)
        second = build_record_passport(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(
            first["files"][0]["sha256"], canonical_record_sha256(records[0])
        )

    def test_batch_validation(self):
        batch = validate_many([self.fixture, self.fixture])
        self.assertTrue(batch["valid"])
        self.assertEqual(batch["passport_count"], 2)
        self.assertEqual(batch["valid_count"], 2)

    def test_cli_build_and_verify(self):
        manifest = {
            "source": {"title": "CLI fixture", "contract": "CLI_V1"},
            "records": [
                {"record_id": "CLI-1", "value": "one"},
                {"record_id": "CLI-2", "value": "two"},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path = tmp_path / "manifest.json"
            passport_path = tmp_path / "passport.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                build_code = cli_main(
                    [
                        "build-records",
                        str(manifest_path),
                        str(passport_path),
                        "--passport-id",
                        "EPP-CLI-001",
                    ]
                )
                verify_code = cli_main(["verify", str(passport_path)])
            self.assertEqual(build_code, 0)
            self.assertEqual(verify_code, 0)
            self.assertTrue(passport_path.exists())


if __name__ == "__main__":
    unittest.main()
