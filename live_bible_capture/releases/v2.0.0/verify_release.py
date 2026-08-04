from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
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
    assembled = Path(tempfile.mkdtemp(prefix="lbf-v2-source-"))
    shutil.copytree(ROOT / descriptor["source_root"], assembled, dirs_exist_ok=True)
    for target, parts in descriptor.get("split_files", {}).items():
        target_path = assembled / target
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text("".join((ROOT / part).read_text() for part in parts))
    assert manifest["version"] == descriptor["version"]
    assert manifest["file_count"] == len(manifest["files"])
    for relative, expected in manifest["files"].items():
        path = assembled / relative
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
        subprocess.run([sys.executable, "-m", "compileall", "-q", str(assembled / "live_bible_fabric")], check=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "--no-build-isolation", "-e", str(assembled)], check=True)
        subprocess.run([sys.executable, "-m", "pytest", "-q", str(assembled / "tests")], check=True)
    print("LIVE_BIBLE_CAPTURE_FABRIC_V2_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
