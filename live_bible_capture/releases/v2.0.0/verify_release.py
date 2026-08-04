from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    descriptor = json.loads((ROOT / "release_descriptor.json").read_text())
    manifest = json.loads((ROOT / "SOURCE_MANIFEST.json").read_text())
    source = ROOT / descriptor["source_root"]
    assert manifest["version"] == descriptor["version"]
    assert manifest["file_count"] == len(manifest["files"])
    for relative, expected in manifest["files"].items():
        path = source / relative
        assert path.is_file(), relative
        assert sha256(path) == expected["sha256"], relative
        assert path.stat().st_size == expected["bytes"], relative
    acceptance = json.loads((ROOT / "ACCEPTANCE.json").read_text())
    receipt = json.loads((ROOT / "RELEASE_RECEIPT.json").read_text())
    assert acceptance["accepted"] is True
    assert acceptance["zip_sha256"] == descriptor["archive_sha256"]
    assert receipt["zip_sha256"] == descriptor["archive_sha256"]
    assert descriptor["binary_reconstruction_in_github"] is False
    if args.run_tests:
        subprocess.run([sys.executable, "-m", "compileall", "-q", str(source / "live_bible_fabric")], check=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "--no-build-isolation", "-e", str(source)], check=True)
        subprocess.run([sys.executable, "-m", "pytest", "-q", str(source / "tests")], check=True)
    print("LIVE_BIBLE_CAPTURE_FABRIC_V2_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
