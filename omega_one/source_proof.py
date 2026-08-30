"""Verify that reconciled Federation source files match their Git blob identities."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - Git identity, not security


@dataclass(frozen=True)
class SourceCheck:
    path: str
    expected: str
    observed: str | None
    valid: bool
    reason: str


def verify_sources(manifest_path: str | Path, root: str | Path | None = None) -> tuple[SourceCheck, ...]:
    manifest_file = Path(manifest_path)
    base = Path(root) if root is not None else manifest_file.parent
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    expected_files = manifest.get("files")
    if not isinstance(expected_files, dict) or not expected_files:
        raise ValueError("SOURCE_MANIFEST_FILES_REQUIRED")
    checks = []
    for relative_path, expected in sorted(expected_files.items()):
        candidate = (base / relative_path).resolve()
        try:
            candidate.relative_to(base.resolve())
        except ValueError as error:
            raise ValueError(f"SOURCE_PATH_ESCAPES_ROOT:{relative_path}") from error
        if not candidate.is_file():
            checks.append(SourceCheck(relative_path, str(expected), None, False, "MISSING"))
            continue
        observed = git_blob_sha(candidate.read_bytes())
        checks.append(
            SourceCheck(
                relative_path,
                str(expected),
                observed,
                observed == expected,
                "MATCH" if observed == expected else "HASH_MISMATCH",
            )
        )
    return tuple(checks)


def assert_sources_verified(manifest_path: str | Path, root: str | Path | None = None) -> tuple[SourceCheck, ...]:
    checks = verify_sources(manifest_path, root)
    failures = [check for check in checks if not check.valid]
    if failures:
        reasons = ",".join(f"{item.path}:{item.reason}" for item in failures)
        raise ValueError("SOURCE_VERIFICATION_FAILED:" + reasons)
    return checks
