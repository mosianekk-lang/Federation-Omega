from __future__ import annotations
import base64
import gzip
import hashlib
from pathlib import Path
import re
import unittest

EXPECTED_RAW_SHA256 = "773ee295b2ae3f2182afc47bcc94c676c1e6464face0176504ff8763c9616443"
EXPECTED_LF_NORMALIZED_SHA256 = "e777a19ed3750c989fdb82033fba1247e1b8fedb5be8721783697c83b4a4bb7f"
EXPECTED_GZIP_SHA256 = "a3b130bb71d08fb5a3a2c63615920ade240e2937a875f984e8d1982cf262f920"
EXPECTED_RAW_BYTES = 52480
EXPECTED_CRLF_COUNT = 2560
EXPECTED_CHUNK_LENGTHS = [4000, 4000, 4000, 4000, 4000, 460]
EXPECTED_B64_LENGTH = 20460

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
        self.assertEqual(len(raw), EXPECTED_RAW_BYTES)
        self.assertEqual(raw.count(b"\r\n"), EXPECTED_CRLF_COUNT)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), EXPECTED_RAW_SHA256)
        normalized = raw.decode("utf-8").replace("\r\n", "\n").encode("utf-8")
        self.assertEqual(hashlib.sha256(normalized).hexdigest(), EXPECTED_LF_NORMALIZED_SHA256)
        text = raw.decode("utf-8")
        self.assertEqual(len(text.splitlines()), 2561)
        parts = re.findall(r"# PART ([IVXLCDM0-9]+) — ", text)
        self.assertEqual(len(parts), 55)
        self.assertIn("0", parts)
        self.assertEqual(len([p for p in parts if p != "0"]), 54)

if __name__ == "__main__":
    unittest.main()
