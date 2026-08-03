from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DESC = json.loads((ROOT / "source_descriptor.json").read_text(encoding="utf-8"))
SOURCE = ROOT / DESC["source_archive"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


observed = sha256(SOURCE)
assert observed == DESC["source_archive_sha256"], (observed, DESC["source_archive_sha256"])
with tarfile.open(SOURCE, "r:xz") as tf:
    members = [member for member in tf.getmembers() if member.isfile()]
    assert len(members) == DESC["source_file_count"], (len(members), DESC["source_file_count"])
    assert all(".." not in Path(member.name).parts for member in members)
    assert all(not Path(member.name).is_absolute() for member in members)
print(json.dumps({
    "state": "DETERMINISTIC_SOURCE_ARCHIVE_VERIFIED",
    "source_archive_sha256": observed,
    "source_file_count": len(members),
}, indent=2))
