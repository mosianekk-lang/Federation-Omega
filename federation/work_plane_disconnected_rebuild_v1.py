"""Disconnected rebuild court for FUSE Work Plane v1.

The court composes existing SOVARA deterministic backup/restore with the admitted
Work Plane local runtime and generation-CAS source courts. It operates only in
fresh temporary workspaces, denies network socket creation in child Python
processes, verifies exact source digests after restore, runs compile/tests, and
proves local rollback by restoring a deliberately corrupted file.

It does not prove GCS, Cloud Run, Google identity, 24x7 persistence, cross-host
DR, production activation, or owner value.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Mapping

from federation_consolidation.sovara_sovereign_backup import (
    ArtifactClass,
    ArtifactInput,
    BackupEventType,
    build_backup_plan,
    restore_snapshot_chain,
    verify_archive,
)

SCHEMA = "FUSE-WORK-PLANE-DISCONNECTED-REBUILD-COURT-V1"
VERSION = "1.0.0"

TARGET_PATHS = (
    "federation/fuse_work_plane_runtime_v1.py",
    "respawn/work_plane_gcs_runtime.py",
    "tests/test_work_plane_gcs_runtime.py",
    "governance/fuse_work_plane_respawn_gcs_v1.json",
    "governance/fuse_work_plane_cloud_service_v1.json",
    "governance/proofos_omega_policy_extension_work_plane_respawn_gcs_v1.json",
)

NETWORK_BLOCK_MARKER = "WORK_PLANE_DISCONNECTED_NETWORK_BLOCKED"


def _digest_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _digest_json(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _git_sha(value: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 40 or any(c not in "0123456789abcdef" for c in text):
        raise ValueError("WORK_PLANE_REBUILD_SOURCE_SHA_INVALID")
    return text


@dataclass(frozen=True, slots=True)
class FileDigest:
    path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class CommandEvidence:
    argv: tuple[str, ...]
    returncode: int
    stdout_sha256: str
    stderr_sha256: str


@dataclass(frozen=True, slots=True)
class RebuildReceipt:
    schema: str
    version: str
    source_head_sha: str
    target_file_count: int
    source_files: tuple[FileDigest, ...]
    archive_sha256: str
    manifest_sha256: str
    archive_verified: bool
    first_restore_exact: bool
    second_restore_exact: bool
    network_guard_verified: bool
    compile_evidence: CommandEvidence
    test_evidence: CommandEvidence
    rollback_verified: bool
    disconnected_rebuild_proven: bool
    provider_effect_authorized: bool
    provider_runtime_proven: bool
    gcs_live_proven: bool
    cloud_run_proven: bool
    persistent_24x7_proven: bool
    cross_host_dr_proven: bool
    owner_value_proven: bool
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def collect_source_files(repo_root: str | os.PathLike[str]) -> tuple[FileDigest, ...]:
    root = Path(repo_root).resolve()
    out: list[FileDigest] = []
    for rel in TARGET_PATHS:
        path = (root / rel).resolve()
        if root not in path.parents or not path.is_file() or path.is_symlink():
            raise ValueError("WORK_PLANE_REBUILD_TARGET_INVALID:" + rel)
        raw = path.read_bytes()
        out.append(FileDigest(rel, len(raw), _digest_bytes(raw)))
    return tuple(out)


def build_source_snapshot(
    repo_root: str | os.PathLike[str],
    *,
    source_head_sha: str,
    created_at: str,
):
    root = Path(repo_root).resolve()
    source_head_sha = _git_sha(source_head_sha)
    artifacts = []
    for record in collect_source_files(root):
        artifacts.append(
            ArtifactInput(
                logical_name=record.path,
                content=(root / record.path).read_bytes(),
                media_type=(
                    "application/json" if record.path.endswith(".json") else "text/x-python"
                ),
                classification=ArtifactClass.PUBLIC_SAFE,
                source_ref=f"git:{source_head_sha}:{record.path}",
                email_eligible=False,
            )
        )
    plan = build_backup_plan(
        event_type=BackupEventType.MANUAL_CHECKPOINT,
        event_id="work-plane-disconnected-rebuild-v1",
        created_at=created_at,
        source_identity="FUSE_WORK_PLANE_SOURCE_SLICE",
        source_version=source_head_sha,
        artifacts=tuple(artifacts),
        checkpoint_every=7,
        force_full=True,
    )
    if plan.archive_bytes is None or plan.archive_sha256 is None:
        raise RuntimeError("WORK_PLANE_REBUILD_ARCHIVE_MISSING")
    verify_archive(plan)
    return plan


def _materialize(restored: Mapping[str, bytes], target: Path) -> None:
    if any(target.iterdir()):
        raise ValueError("WORK_PLANE_REBUILD_TARGET_NOT_EMPTY")
    for rel, raw in restored.items():
        if rel not in TARGET_PATHS:
            raise ValueError("WORK_PLANE_REBUILD_UNDECLARED_RESTORE_PATH:" + rel)
        dest = (target / rel).resolve()
        if target.resolve() not in dest.parents:
            raise ValueError("WORK_PLANE_REBUILD_PATH_ESCAPE")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)


def _exact(target: Path, expected: tuple[FileDigest, ...]) -> bool:
    actual = collect_source_files(target)
    return tuple((x.path, x.size_bytes, x.sha256) for x in actual) == tuple(
        (x.path, x.size_bytes, x.sha256) for x in expected
    )


def _write_network_guard(root: Path) -> Path:
    guard = root / ".network_guard"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(
        "import socket\n"
        f"_MARKER={NETWORK_BLOCK_MARKER!r}\n"
        "def _deny(*args, **kwargs):\n    raise RuntimeError(_MARKER)\n"
        "socket.create_connection=_deny\n"
        "_BaseSocket=socket.socket\n"
        "class _GuardedSocket(_BaseSocket):\n"
        "    def connect(self, *args, **kwargs):\n        raise RuntimeError(_MARKER)\n"
        "socket.socket=_GuardedSocket\n",
        encoding="utf-8",
    )
    return guard


def _run(root: Path, guard: Path, argv: tuple[str, ...]) -> CommandEvidence:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join((str(guard), str(root)))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    process = subprocess.run(
        argv,
        cwd=root,
        env=env,
        text=False,
        capture_output=True,
        timeout=240,
        check=False,
    )
    return CommandEvidence(
        argv=argv,
        returncode=process.returncode,
        stdout_sha256=_digest_bytes(process.stdout),
        stderr_sha256=_digest_bytes(process.stderr),
    )


def _network_probe(root: Path, guard: Path) -> bool:
    probe = root / "_network_probe.py"
    probe.write_text(
        "import socket\n"
        "try:\n"
        "    socket.create_connection(('127.0.0.1', 9), timeout=0.01)\n"
        "except RuntimeError as exc:\n"
        f"    raise SystemExit(0 if str(exc)=={NETWORK_BLOCK_MARKER!r} else 3)\n"
        "except Exception:\n"
        "    raise SystemExit(4)\n"
        "raise SystemExit(5)\n",
        encoding="utf-8",
    )
    try:
        evidence = _run(root, guard, (sys.executable, str(probe.name)))
        return evidence.returncode == 0
    finally:
        probe.unlink(missing_ok=True)


def execute_disconnected_rebuild(
    repo_root: str | os.PathLike[str],
    *,
    source_head_sha: str,
    created_at: str,
) -> RebuildReceipt:
    root = Path(repo_root).resolve()
    expected = collect_source_files(root)
    plan = build_source_snapshot(
        root, source_head_sha=source_head_sha, created_at=created_at
    )
    restored = restore_snapshot_chain((plan.archive_bytes,))
    archive_verified = verify_archive(plan)

    with tempfile.TemporaryDirectory(prefix="wp-disconnected-a-") as first_dir, tempfile.TemporaryDirectory(
        prefix="wp-disconnected-b-"
    ) as second_dir:
        first = Path(first_dir)
        second = Path(second_dir)
        _materialize(restored, first)
        _materialize(restored, second)
        first_exact = _exact(first, expected)
        second_exact = _exact(second, expected)

        guard = _write_network_guard(first)
        network_guard_verified = _network_probe(first, guard)

        compile_evidence = _run(
            first,
            guard,
            (
                sys.executable,
                "-m",
                "compileall",
                "-q",
                "federation",
                "respawn",
                "tests",
            ),
        )
        test_evidence = _run(
            first,
            guard,
            (sys.executable, "tests/test_work_plane_gcs_runtime.py"),
        )

        rollback_target = first / TARGET_PATHS[0]
        rollback_target.write_bytes(b"CORRUPTED_FOR_ROLLBACK_COURT\n")
        rollback_precondition = not _exact(first, expected)
        rollback_target.write_bytes(restored[TARGET_PATHS[0]])
        rollback_verified = rollback_precondition and _exact(first, expected)

    proven = all(
        (
            archive_verified,
            first_exact,
            second_exact,
            network_guard_verified,
            compile_evidence.returncode == 0,
            test_evidence.returncode == 0,
            rollback_verified,
        )
    )
    payload = {
        "schema": SCHEMA,
        "version": VERSION,
        "source_head_sha": _git_sha(source_head_sha),
        "target_file_count": len(expected),
        "source_files": [asdict(x) for x in expected],
        "archive_sha256": plan.archive_sha256,
        "manifest_sha256": plan.manifest_sha256,
        "archive_verified": archive_verified,
        "first_restore_exact": first_exact,
        "second_restore_exact": second_exact,
        "network_guard_verified": network_guard_verified,
        "compile_evidence": asdict(compile_evidence),
        "test_evidence": asdict(test_evidence),
        "rollback_verified": rollback_verified,
        "disconnected_rebuild_proven": proven,
        "provider_effect_authorized": False,
        "provider_runtime_proven": False,
        "gcs_live_proven": False,
        "cloud_run_proven": False,
        "persistent_24x7_proven": False,
        "cross_host_dr_proven": False,
        "owner_value_proven": False,
    }
    return RebuildReceipt(**payload, receipt_sha256=_digest_json(payload))
