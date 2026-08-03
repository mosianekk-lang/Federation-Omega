from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("translate", ROOT / "translate.py")
assert SPEC and SPEC.loader
TRANSLATE = importlib.util.module_from_spec(SPEC)
sys.modules["translate"] = TRANSLATE
SPEC.loader.exec_module(TRANSLATE)

RECOVERY_SPEC = importlib.util.spec_from_file_location("recovery", ROOT / "recovery.py")
assert RECOVERY_SPEC and RECOVERY_SPEC.loader
RECOVERY = importlib.util.module_from_spec(RECOVERY_SPEC)
RECOVERY_SPEC.loader.exec_module(RECOVERY)


class NatureTranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads((ROOT / "source_manifest.json").read_text(encoding="utf-8"))
        cls.health = json.loads((ROOT / "monitoring" / "latest_health.json").read_text(encoding="utf-8"))

    def test_translation_is_deterministic(self) -> None:
        left = TRANSLATE.build_translation(self.manifest, self.health)
        right = TRANSLATE.build_translation(self.manifest, self.health)
        self.assertEqual(left["translation_sha256"], right["translation_sha256"])
        self.assertEqual(left, right)
        self.assertEqual(left["mechanism_count"], 12)

    def test_all_registered_hypotheses_are_mapped(self) -> None:
        expected = {hypothesis for source in self.manifest["sources"] for hypothesis in source["mechanism_hypotheses"]}
        self.assertEqual(expected, set(TRANSLATE.PATTERNS))

    def test_validator_rejects_record_tamper(self) -> None:
        payload = TRANSLATE.build_translation(self.manifest, self.health)
        payload["records"][0]["engineering_pattern"] = "tampered"
        with self.assertRaisesRegex(ValueError, "record_digest_mismatch"):
            TRANSLATE.validate_translation(payload)

    def test_validator_rejects_claim_inflation_even_with_rehashed_record(self) -> None:
        payload = TRANSLATE.build_translation(self.manifest, self.health)
        record = payload["records"][0]
        record["claim_state"] = "DEPLOYED_AND_PROVEN"
        candidate = dict(record)
        candidate.pop("record_sha256")
        record["record_sha256"] = TRANSLATE.canonical_sha256(candidate)
        payload_without_digest = dict(payload)
        payload_without_digest.pop("translation_sha256")
        payload["translation_sha256"] = TRANSLATE.canonical_sha256(payload_without_digest)
        with self.assertRaisesRegex(ValueError, "claim_boundary_violation"):
            TRANSLATE.validate_translation(payload)

    def test_controlled_recovery_restores_exact_hash(self) -> None:
        receipt = RECOVERY.run_recovery_drill(self.manifest, self.health)
        self.assertEqual(receipt["controlled_recovery"], "PASS")
        self.assertEqual(receipt["exact_restoration"], "PASS")
        self.assertEqual(receipt["baseline_translation_sha256"], receipt["recovered_translation_sha256"])


if __name__ == "__main__":
    unittest.main()
