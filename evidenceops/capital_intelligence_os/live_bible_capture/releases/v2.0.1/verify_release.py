from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED = {
    "version": "2.0.1",
    "source_manifest_sha256": "71ae0de6321fd628e64b0bdc6a74223c3099ae5af1eb67967a5907a99989fa71",
    "source_zip_sha256": "7bbaced5481303e236f8b72bef76f9fecee0f5b82ca2eac107587d3375761336",
    "wheel_sha256": "586411ce2aafd6967bbd195137ddf7e08f8c92d6c076bf1b3ae08d5754824667",
    "release_zip_sha256": "3ca119ebb0c86b2b9934f2cb63a5b676b85ef8a121ce9cae064eccd466811942",
}


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    acceptance = load("ACCEPTANCE.json")
    receipt = load("RELEASE_RECEIPT.json")
    descriptor = load("release_descriptor.json")
    manifest = load("SOURCE_MANIFEST.json")

    assert acceptance["accepted"] is True
    assert acceptance["source_tests"] == 18
    assert acceptance["clean_tests"] == 18
    assert acceptance["sqlite_quick_check"] == "ok"
    assert acceptance["installed_cli_canary"] == "passed"
    assert acceptance["external_effects"] == 0
    assert receipt["release_state"] == "COMPLETE_VERIFIED_LOCAL_RELEASE"
    assert descriptor["canonical_source_commit"] == "fc0553026bed27b2ed66e955de3a200a3136b336"
    assert descriptor["binary_distribution"] == "GOVERNED_LIBRARY_NOT_SOURCE_REPOSITORY"
    assert manifest["file_count"] == len(manifest["files"]) == 17
    assert sha256(ROOT / "SOURCE_MANIFEST.json") == EXPECTED["source_manifest_sha256"]

    for key, expected in EXPECTED.items():
        if key == "version":
            assert acceptance[key] == receipt[key] == descriptor[key] == expected
        elif key == "source_manifest_sha256":
            assert acceptance[key] == receipt[key] == descriptor[key] == expected
        else:
            assert acceptance[key] == receipt[key] == descriptor[key] == expected

    print("LIVE_BIBLE_V2_0_1_RELEASE_METADATA_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
