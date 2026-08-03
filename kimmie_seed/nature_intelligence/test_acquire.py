from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent / "acquire.py"
SPEC = importlib.util.spec_from_file_location("nature_acquire", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NatureAcquireTests(unittest.TestCase):
    def test_canonical_sha256_is_stable(self) -> None:
        left = MODULE.canonical_sha256({"b": 2, "a": 1})
        right = MODULE.canonical_sha256({"a": 1, "b": 2})
        self.assertEqual(left, right)
        self.assertEqual(len(left), 64)

    def test_validation_passes_valid_fixture(self) -> None:
        source = {
            "source_id": "FIXTURE",
            "title": "Fixture",
            "source_url": "https://example.invalid",
            "minimum_bytes": 20,
            "required_markers": ["NATURE", "HIVE"],
            "mechanism_hypotheses": ["local rules can coordinate a collective"],
        }
        raw = (
            "Project Gutenberg\nNature and HIVE systems use variation, selection, "
            "simple local worker rules, and adaptation."
        ).encode("utf-8")
        result = MODULE.validate_source(source, raw)
        self.assertEqual(result["validation"], "PASS")
        self.assertEqual(result["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertGreater(result["word_count"], 5)

    def test_validation_rejects_missing_marker(self) -> None:
        source = {
            "source_id": "FIXTURE",
            "title": "Fixture",
            "source_url": "https://example.invalid",
            "minimum_bytes": 1,
            "required_markers": ["ABSENT"],
            "mechanism_hypotheses": [],
        }
        result = MODULE.validate_source(source, b"Project Gutenberg fixture")
        self.assertEqual(result["validation"], "FAIL")
        self.assertIn("missing_marker:ABSENT", result["failures"])

    def test_manifest_has_three_bounded_sources(self) -> None:
        manifest = json.loads((MODULE.ROOT / "source_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["storage_policy"], "NO_FULL_TEXT_COMMIT")
        self.assertEqual(len(manifest["sources"]), 3)
        self.assertTrue(all(item["mechanism_hypotheses"] for item in manifest["sources"]))


if __name__ == "__main__":
    unittest.main()
