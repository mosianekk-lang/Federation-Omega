"""Canonical source identity for SOVARA × JARVIS ΑΩ5 full integration.

The uploaded file is CRLF-terminated.  RAW_UPLOAD_SHA256 is the byte-exact
identity and therefore the zero-dilution authority.  LF_NORMALIZED_SHA256 is a
secondary textual-equivalence identity retained because the first full rebuild
normalized line endings before hashing.  It must never outrank the raw upload.
"""

RAW_UPLOAD_SHA256 = "773ee295b2ae3f2182afc47bcc94c676c1e6464face0176504ff8763c9616443"
LF_NORMALIZED_SHA256 = "e777a19ed3750c989fdb82033fba1247e1b8fedb5be8721783697c83b4a4bb7f"
DETERMINISTIC_GZIP_SHA256 = "a3b130bb71d08fb5a3a2c63615920ade240e2937a875f984e8d1982cf262f920"
RAW_UPLOAD_BYTES = 52480
CRLF_COUNT = 2560
SOURCE_LINES = 2561
CANONICAL_B64_LENGTH = 20460
CANONICAL_CHUNK_LENGTHS = (4000, 4000, 4000, 4000, 4000, 460)

CANONICAL_AUTHORITY = "RAW_UPLOAD_SHA256"
