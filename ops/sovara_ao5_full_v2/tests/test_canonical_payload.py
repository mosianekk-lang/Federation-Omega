from __future__ import annotations
import base64
import gzip
import hashlib
from pathlib import Path
import re
import unittest

EXPECTED_SHA256 = "e777a19ed3750c989fdb82033fba1247e1b8fedb5be8721783697c83b4a4bb7f"

class CanonicalAO5PayloadTests(unittest.TestCase):
    def test_exact_canonical_payload(self):
        package = Path(__file__).resolve().parents[1]
        encoded = (package / "JARVIS_AO5_CANONICAL_SPEC.txt.gz.b64").read_text(encoding="utf-8").strip()
        raw = gzip.decompress(base64.b64decode(encoded))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), EXPECTED_SHA256)
        text = raw.decode("utf-8")
        self.assertEqual(len(text.splitlines()), 2561)
        parts = re.findall(r"# PART ([IVXLCDM0-9]+) — ", text)
        self.assertEqual(len(parts), 55)
        self.assertIn("0", parts)
        self.assertEqual(len([p for p in parts if p != "0"]), 54)

if __name__ == "__main__":
    unittest.main()
