from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
EXPECTED_MANIFEST_SHA256 = "106b6db2b004e1574d31095f0c3e7371195082e9571fc3bf9ce160bb3bf5f815"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest_path = ROOT / "SOURCE_MANIFEST.json"
    acceptance = json.loads((ROOT / "ACCEPTANCE.json").read_text(encoding="utf-8"))
    receipt = json.loads((ROOT / "RELEASE_RECEIPT.json").read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert sha256(manifest_path) == EXPECTED_MANIFEST_SHA256
    assert manifest["file_count"] == len(manifest["files"]) == 11
    for row in manifest["files"]:
        path = SOURCE / row["path"]
        assert path.is_file(), row["path"]
        assert path.stat().st_size == row["size"], row["path"]
        assert sha256(path) == row["sha256"], row["path"]

    assert acceptance["accepted"] is True
    assert acceptance["source_tests"] == acceptance["clean_tests"] == 16
    assert acceptance["resource_warning_gate"] == "PASS"
    assert acceptance["sqlite_quick_check"] == "ok"
    assert acceptance["external_effects"] == 0
    assert receipt["state"] == "COMPLETE_VERIFIED_LOCAL_RELEASE"
    assert receipt["release_zip_sha256"] == "01e5b66a061d8784082c7690907eebfbb0a1c0a0e3a9ddad177f76eac0ef809e"
    assert receipt["external_effects"] == 0
    print("FEDERATION_OMEGA_V2_PHASE1_RELEASE_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
