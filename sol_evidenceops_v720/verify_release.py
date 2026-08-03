from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
DESC = json.loads((ROOT / "release_descriptor.json").read_text(encoding="utf-8"))
ARCHIVE = ROOT / DESC["archive"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


observed = sha256(ARCHIVE)
assert observed == DESC["archive_sha256"], (observed, DESC["archive_sha256"])
with ZipFile(ARCHIVE) as zf:
    assert zf.testzip() is None
    names = zf.namelist()
    prefix = f"OmegaMax_Sol61_Autonomous_EvidenceOps_Runtime_v{DESC['version']}/"
    assert prefix + "SOURCE_MANIFEST.json" in names
    manifest_bytes = zf.read(prefix + "SOURCE_MANIFEST.json")
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    assert manifest_sha == DESC["source_manifest_sha256"], (manifest_sha, DESC["source_manifest_sha256"])
    wheel_names = [name for name in names if name.startswith(prefix + "dist/") and name.endswith(".whl")]
    assert len(wheel_names) == 1
    wheel_sha = hashlib.sha256(zf.read(wheel_names[0])).hexdigest()
    assert wheel_sha == DESC["wheel_sha256"], (wheel_sha, DESC["wheel_sha256"])
print(json.dumps({
    "state": "EXACT_ARCHIVE_AND_EMBEDDED_ARTIFACTS_VERIFIED",
    "archive_sha256": observed,
    "source_manifest_sha256": manifest_sha,
    "wheel_sha256": wheel_sha,
}, indent=2))
