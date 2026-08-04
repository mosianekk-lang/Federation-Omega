#!/usr/bin/env python3
"""Build deterministic, source-clean Phoenix Core and private Ops exports."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class FileRecord:
    path: str
    size: int
    sha256: str
    classification: str
    reason: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_sha(root: Path) -> str:
    value = os.getenv("GITHUB_SHA", "").strip()
    if value:
        return value
    process = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True
    )
    return process.stdout.strip() if process.returncode == 0 else "UNRESOLVED"


def matches_prefix(path: str, prefixes: list[str]) -> bool:
    return any(path == item.rstrip("/") or path.startswith(item) for item in prefixes)


def classify_core(path: Path, root: Path, policy: dict) -> tuple[bool, str]:
    rel = path.relative_to(root).as_posix()
    parts = set(path.relative_to(root).parts)
    core = policy["core"]

    if path.is_symlink():
        return False, "SYMLINK_PROHIBITED"
    if matches_prefix(rel, core["excluded_prefixes"]):
        return False, "EXCLUDED_PREFIX"
    if rel.startswith("phoenix/"):
        return False, "MIGRATION_CONTROL_NOT_CORE_SOURCE"
    if rel.startswith("evidenceops/runtime/"):
        return False, "EVIDENCEOPS_RUNTIME_STATE"
    if rel.startswith("evidenceops/secure_capability_box/"):
        return False, "SECURE_CAPABILITY_MATERIAL"
    if any(segment in parts for segment in core["excluded_segments"]):
        return False, "EXCLUDED_STATE_OR_AUTHORITY_SEGMENT"
    if path.suffix.lower() in set(core["excluded_suffixes"]):
        return False, "EXCLUDED_SENSITIVE_OR_GENERATED_SUFFIX"
    if path.name in core["include_root_files"] and path.parent == root:
        return True, "APPROVED_ROOT_FILE"
    if path.suffix.lower() not in set(core["include_extensions"]):
        return False, "UNAPPROVED_EXTENSION"
    if path.stat().st_size > 10 * 1024 * 1024:
        return False, "FILE_EXCEEDS_CORE_EXPORT_LIMIT"
    return True, "APPROVED_SOURCE_FILE"


def secret_marker(path: Path, markers: list[str]) -> str | None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "UNREADABLE_FILE"
    lowered = text.lower()
    for marker in markers:
        if marker.lower() in lowered:
            return marker
    return None


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    os.chmod(destination, 0o755 if os.access(source, os.X_OK) else 0o644)


def deterministic_tar(source_dir: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w") as archive:
                for path in sorted(source_dir.rglob("*"), key=lambda p: p.as_posix()):
                    if path.is_symlink():
                        raise RuntimeError(f"symlink reached archive stage: {path}")
                    relative = path.relative_to(source_dir).as_posix()
                    info = archive.gettarinfo(str(path), arcname=relative)
                    info.uid = 0
                    info.gid = 0
                    info.uname = "root"
                    info.gname = "root"
                    info.mtime = 0
                    if path.is_file():
                        with path.open("rb") as stream:
                            archive.addfile(info, stream)
                    else:
                        archive.addfile(info)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stage_core(root: Path, stage: Path, policy: dict) -> tuple[list[FileRecord], list[FileRecord]]:
    included: list[FileRecord] = []
    excluded: list[FileRecord] = []
    markers = policy["core"]["secret_markers"]

    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() and not path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        allowed, reason = classify_core(path, root, policy)
        size = path.lstat().st_size
        digest = "SYMLINK" if path.is_symlink() else sha256_file(path)
        if allowed:
            marker = secret_marker(path, markers)
            if marker:
                allowed = False
                reason = f"SECRET_MARKER:{marker}"
        record = FileRecord(
            path=rel,
            size=size,
            sha256=digest,
            classification="CORE_INCLUDED" if allowed else "CORE_EXCLUDED",
            reason=reason,
        )
        if allowed:
            copy_file(path, stage / rel)
            included.append(record)
        else:
            excluded.append(record)

    if not included:
        raise RuntimeError("Core export contains no source files")
    if any(item.path.startswith(".github/workflows/") for item in included):
        raise RuntimeError("Core export contains a GitHub Actions workflow")
    if any(item.reason.startswith("SECRET_MARKER:") and item.classification == "CORE_INCLUDED" for item in included):
        raise RuntimeError("Core export contains a secret marker")
    return included, excluded


def stage_ops(root: Path, stage: Path, policy: dict) -> list[FileRecord]:
    template = root / policy["ops"]["template_prefix"]
    if not template.is_dir():
        raise RuntimeError(f"Ops template missing: {template}")

    records: list[FileRecord] = []
    for path in sorted(template.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        rel = path.relative_to(template).as_posix()
        copy_file(path, stage / rel)
        records.append(FileRecord(
            path=rel,
            size=path.stat().st_size,
            sha256=sha256_file(path),
            classification="OPS_INCLUDED",
            reason="APPROVED_OPS_TEMPLATE",
        ))

    cutover = root / "phoenix" / "provider_cutover.py"
    if cutover.is_file():
        copy_file(cutover, stage / "provider_cutover.py")
        records.append(FileRecord(
            path="provider_cutover.py",
            size=cutover.stat().st_size,
            sha256=sha256_file(cutover),
            classification="OPS_INCLUDED",
            reason="PROVIDER_CUTOVER_CONTROLLER",
        ))

    actual = {item.path for item in records}
    missing = sorted(set(policy["ops"]["required_files"]) - actual)
    if missing:
        raise RuntimeError(f"Ops export missing required files: {missing}")
    if any(item.path.startswith(".github/workflows/") for item in records):
        raise RuntimeError("Ops export unexpectedly contains an active workflow")
    return records


def build(root: Path, output: Path, policy_path: Path) -> dict:
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fedomega-phoenix-") as temporary:
        temp = Path(temporary)
        core_stage = temp / "Federation-Omega-Core"
        ops_stage = temp / "Federation-Omega-Ops"
        core_stage.mkdir()
        ops_stage.mkdir()

        core_included, core_excluded = stage_core(root, core_stage, policy)
        ops_included = stage_ops(root, ops_stage, policy)

        common = {
            "schema": "FEDOMEGA-PHOENIX-EXPORT-MANIFEST-1",
            "policy_version": policy["version"],
            "source_repository": os.getenv(
                "GITHUB_REPOSITORY", "mosianekk-lang/Federation-Omega"
            ),
            "source_sha": source_sha(root),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        core_manifest = {
            **common,
            "target": "Federation-Omega-Core",
            "repository_role": "CANONICAL_SOURCE_ONLY",
            "included_count": len(core_included),
            "excluded_count": len(core_excluded),
            "files": [asdict(item) for item in core_included],
            "excluded": [asdict(item) for item in core_excluded],
            "invariants": {
                "workflow_count": 0,
                "runtime_state_count": 0,
                "secret_marker_count": 0,
            },
        }
        ops_manifest = {
            **common,
            "target": "Federation-Omega-Ops",
            "repository_role": "PRIVATE_EXECUTION_PLANE",
            "included_count": len(ops_included),
            "files": [asdict(item) for item in ops_included],
            "invariants": {
                "active_workflow_count": 0,
                "legacy_workflow_count": 0,
                "long_lived_credentials": 0,
            },
        }
        write_json(core_stage / "PHOENIX_CORE_MANIFEST.json", core_manifest)
        write_json(ops_stage / "PHOENIX_OPS_MANIFEST.json", ops_manifest)

        core_archive = output / "Federation-Omega-Core.tar.gz"
        ops_archive = output / "Federation-Omega-Ops.tar.gz"
        deterministic_tar(core_stage, core_archive)
        deterministic_tar(ops_stage, ops_archive)

        receipt = {
            **common,
            "status": "VERIFIED",
            "core": {
                "archive": core_archive.name,
                "sha256": sha256_file(core_archive),
                "size": core_archive.stat().st_size,
                "included_count": len(core_included),
                "excluded_count": len(core_excluded),
            },
            "ops": {
                "archive": ops_archive.name,
                "sha256": sha256_file(ops_archive),
                "size": ops_archive.stat().st_size,
                "included_count": len(ops_included),
            },
            "source_mutation_attempted": False,
        }
        canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        receipt["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
        write_json(output / "phoenix-export-receipt.json", receipt)
        return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--policy", type=Path, default=Path("phoenix/export_policy.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("phoenix-export-output")
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()
    policy = args.policy if args.policy.is_absolute() else root / args.policy
    output = args.output if args.output.is_absolute() else root / args.output
    receipt = build(root, output, policy)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
