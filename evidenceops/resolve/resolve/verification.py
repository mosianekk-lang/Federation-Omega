from __future__ import annotations

import sqlite3
import zipfile
from pathlib import Path
from typing import Any

from .transport import sha256_file


def verify_hash(path: Path, expected_sha256: str | None = None, expected_size: int | None = None) -> dict[str, Any]:
    result = {"path": str(path), "size": path.stat().st_size, "sha256": sha256_file(path)}
    result["size_ok"] = expected_size is None or result["size"] == expected_size
    result["sha256_ok"] = expected_sha256 is None or result["sha256"] == expected_sha256.lower()
    result["ok"] = result["size_ok"] and result["sha256_ok"]
    return result


def verify_zip(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path, "r") as archive:
        bad_member = archive.testzip()
        count = len(archive.infolist())
    return {"path": str(path), "member_count": count, "bad_member": bad_member, "ok": bad_member is None}


def verify_sqlite(path: Path, count_queries: dict[str, str] | None = None) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        counts = {}
        for name, query in (count_queries or {}).items():
            counts[name] = connection.execute(query).fetchone()[0]
        return {"path": str(path), "integrity": integrity, "counts": counts, "ok": integrity == "ok"}
    finally:
        connection.close()
