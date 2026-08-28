from __future__ import annotations
import base64
import gzip
import hashlib
from pathlib import Path
import re
import unittest

EXPECTED_RAW_SHA256 = "e777a19ed3750c989fdb82033fba1247e1b8fedb5be8721783697c83b4a4bb7f"
EXPECTED_GZIP_SHA256 = "e1b911b405c2e2cd26f78b72b31e2702bdc904269ff48155398c2e3299ad9c59"
EXPECTED_CHUNK_LENGTHS = [4000, 4000, 4000, 4000, 4000, 196]
EXPECTED_B64_LENGTH = 20196

class CanonicalAO5PayloadTests(unittest.TestCase):
    def test_exact_canonical_payload(self):
        package = Path(__file__).resolve().parents[1]
        chunks = sorted((package / "canonical").glob("JARVIS_AO5_CANONICAL_SPEC.txt.gz.b64.part*"))
        self.assertEqual(len(chunks), 6)
        values = [p.read_text(encoding="utf-8").strip() for p in chunks]
        self.assertEqual([len(v) for v in values], EXPECTED_CHUNK_LENGTHS)
        encoded = "".join(values)
        self.assertEqual(len(encoded), EXPECTED_B64_LENGTH)
        compressed = base64.b64decode(encoded, validate=True)
        self.assertEqual(hashlib.sha256(compressed).hexdigest(), EXPECTED_GZIP_SHA256)
        raw = gzip.decompress(compressed)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), EXPECTED_RAW_SHA256)
        text = raw.decode("utf-8")
        self.assertEqual(len(text.splitlines()), 2561)
        parts = re.findall(r"# PART ([IVXLCDM0-9]+) — ", text)
        self.assertEqual(len(parts), 55)
        self.assertIn("0", parts)
        self.assertEqual(len([p for p in parts if p != "0"]), 54)

if __name__ == "__main__":
    unittest.main()
