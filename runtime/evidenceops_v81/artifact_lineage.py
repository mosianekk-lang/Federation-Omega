#!/usr/bin/env python3
"""Immutable artifact lineage, state-integrity and rollback controls.

GitHub repository state is not used as the ProofLoop runtime database. A
successful workflow publishes one immutable state artifact. Later provider
cycles may restore the latest successful artifact for the same branch, verify
its exact semantic state, append one new cycle and publish another immutable
artifact.

No repository write, external legal action or provider-admin mutation occurs.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from proofloop import digest, now_utc, verify_release_state

RESTORE_SCHEMA = "EVIDENCEOPS_V81_ARTIFACT_RESTORE_RECEIPT_V1"
ROLLBACK_SCHEMA = "EVIDENCEOPS_V81_ROLLBACK_RECEIPT_V1"
ARTIFACT_PREFIX = "evidenceops-v81-proofloop-"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def tree_manifest(root: Path, excluded: Iterable[str] = ()) -> list[dict[str, Any]]:
    excluded_set = set(excluded)
    result: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in excluded_set:
            continue
        result.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return result


def tree_sha256(root: Path, excluded: Iterable[str] = ()) -> str:
    return digest(tree_manifest(root, excluded))


def verify_matter_state_hash(state_dir: Path) -> str:
    path = state_dir / "matter_twin.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    supplied = state.pop("state_sha256", None)
    if not isinstance(supplied, str) or len(supplied) != 64:
        raise RuntimeError("matter-twin state hash is absent or malformed")
    observed = digest(state)
    if observed != supplied:
        raise RuntimeError("matter-twin state hash mismatch")
    return supplied


def verify_optional_receipt(path: Path, hash_field: str) -> None:
    if not path.exists():
        return
    receipt = json.loads(path.read_text(encoding="utf-8"))
    supplied = receipt.pop(hash_field, None)
    if not isinstance(supplied, str) or len(supplied) != 64:
        raise RuntimeError(f"{path.name}: receipt hash is absent or malformed")
    if digest(receipt) != supplied:
        raise RuntimeError(f"{path.name}: receipt hash mismatch")


def guard_state(state_dir: Path) -> dict[str, Any]:
    release = verify_release_state(state_dir)
    verify_matter_state_hash(state_dir)
    verify_optional_receipt(
        state_dir / "restore_receipt.json", "restore_receipt_sha256"
    )
    verify_optional_receipt(
        state_dir / "rollback_receipt.json", "rollback_receipt_sha256"
    )
    return release


def _request_json(url: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "EvidenceOps-v8.1-ProofLoop",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub API response was not an object")
    return payload


def _request_bytes(url: str, token: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "EvidenceOps-v8.1-ProofLoop",
        },
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def _safe_zip_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    safe: list[zipfile.ZipInfo] = []
    for member in archive.infolist():
        path = PurePosixPath(member.filename)
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError(
                f"unsafe path in prior state artifact: {member.filename}"
            )
        safe.append(member)
    return safe


def _restore_zip(payload: bytes, state_dir: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = _safe_zip_members(archive)
        if state_dir.exists():
            shutil.rmtree(state_dir)
        state_dir.mkdir(parents=True, exist_ok=True)
        archive.extractall(state_dir, members=members)


def clean_start_receipt(
    state_dir: Path, reason: str, branch: str, event_name: str
) -> dict[str, Any]:
    state_dir.mkdir(parents=True, exist_ok=True)
    receipt: dict[str, Any] = {
        "schema": RESTORE_SCHEMA,
        "observed_at_utc": now_utc(),
        "state": "NO_PRIOR_ARTIFACT_CLEAN_START",
        "reason": reason,
        "branch": branch,
        "event_name": event_name,
        "prior_run_id": None,
        "artifact_id": None,
        "artifact_digest": None,
        "semantic_readback": False,
        "external_effects": 0,
        "truth_boundary": (
            "No previous compatible immutable state artifact was admitted. "
            "The current cycle starts from the controlled manifest."
        ),
    }
    receipt["restore_receipt_sha256"] = digest(receipt)
    atomic_write_json(state_dir / "restore_receipt.json", receipt)
    return receipt


def restore_previous_artifact(
    state_dir: Path,
    *,
    repository: str,
    workflow_file: str,
    token: str,
    current_run_id: int,
    branch: str,
    event_name: str,
) -> dict[str, Any]:
    if event_name == "pull_request":
        return clean_start_receipt(
            state_dir,
            "pull-request cycles do not inherit provider state",
            branch,
            event_name,
        )
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required for artifact restoration")
    api = f"https://api.github.com/repos/{repository}"
    encoded_workflow = urllib.parse.quote(workflow_file, safe="")
    runs = _request_json(
        f"{api}/actions/workflows/{encoded_workflow}/runs?status=success&per_page=50",
        token,
    ).get("workflow_runs", [])
    for run in runs:
        if int(run.get("id", 0)) == current_run_id:
            continue
        if run.get("head_branch") != branch:
            continue
        artifacts = _request_json(
            f"{api}/actions/runs/{run['id']}/artifacts?per_page=100",
            token,
        ).get("artifacts", [])
        candidates = [
            item
            for item in artifacts
            if str(item.get("name", "")).startswith(ARTIFACT_PREFIX)
            and not item.get("expired")
        ]
        if not candidates:
            continue
        artifact = sorted(
            candidates,
            key=lambda item: str(item.get("created_at", "")),
            reverse=True,
        )[0]
        payload = _request_bytes(artifact["archive_download_url"], token)
        observed_archive_sha256 = sha256_bytes(payload)
        _restore_zip(payload, state_dir)
        restored_release = guard_state(state_dir)
        receipt: dict[str, Any] = {
            "schema": RESTORE_SCHEMA,
            "observed_at_utc": now_utc(),
            "state": "PRIOR_IMMUTABLE_ARTIFACT_RESTORED_VERIFIED",
            "repository": repository,
            "workflow_file": workflow_file,
            "branch": branch,
            "event_name": event_name,
            "prior_run_id": run["id"],
            "prior_head_sha": run.get("head_sha"),
            "artifact_id": artifact["id"],
            "artifact_name": artifact["name"],
            "artifact_api_digest": artifact.get("digest"),
            "downloaded_archive_sha256": observed_archive_sha256,
            "restored_release_receipt_sha256": restored_release[
                "receipt_sha256"
            ],
            "restored_value_cycle_sha256": restored_release[
                "value_cycle_sha256"
            ],
            "semantic_readback": True,
            "external_effects": 0,
            "truth_boundary": (
                "This receipt proves restoration and semantic readback of a "
                "prior immutable workflow artifact for the same branch. It "
                "does not grant consequential authority."
            ),
        }
        receipt["restore_receipt_sha256"] = digest(receipt)
        atomic_write_json(state_dir / "restore_receipt.json", receipt)
        return receipt
    return clean_start_receipt(
        state_dir,
        "no successful compatible artifact was found for the same branch",
        branch,
        event_name,
    )


def rollback_drill(state_dir: Path) -> dict[str, Any]:
    release_before = guard_state(state_dir)
    excluded = {"rollback_receipt.json"}
    manifest_before = tree_manifest(state_dir, excluded)
    tree_before = digest(manifest_before)
    with tempfile.TemporaryDirectory() as temporary:
        archive_path = Path(temporary) / "proofloop-state.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            for item in manifest_before:
                archive.add(
                    state_dir / item["path"],
                    arcname=item["path"],
                    recursive=False,
                )
        archive_sha256 = sha256_file(archive_path)
        backup = archive_path.read_bytes()
        shutil.rmtree(state_dir)
        state_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(backup), mode="r:gz") as archive:
            for member in archive.getmembers():
                path = PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts:
                    raise RuntimeError(
                        f"unsafe rollback member: {member.name}"
                    )
            archive.extractall(state_dir)
    release_after = guard_state(state_dir)
    manifest_after = tree_manifest(state_dir, excluded)
    tree_after = digest(manifest_after)
    if manifest_before != manifest_after or tree_before != tree_after:
        raise RuntimeError("rollback tree readback mismatch")
    if release_before["receipt_sha256"] != release_after["receipt_sha256"]:
        raise RuntimeError("rollback semantic receipt mismatch")
    receipt: dict[str, Any] = {
        "schema": ROLLBACK_SCHEMA,
        "observed_at_utc": now_utc(),
        "state": "ROLLBACK_RESTORE_SEMANTIC_READBACK_VERIFIED",
        "archive_sha256": archive_sha256,
        "pre_restore_tree_sha256": tree_before,
        "post_restore_tree_sha256": tree_after,
        "release_receipt_sha256": release_after["receipt_sha256"],
        "semantic_readback": True,
        "external_effects": 0,
        "truth_boundary": (
            "The local workflow state was archived, removed, restored and "
            "independently verified. No external legal or provider effect "
            "occurred."
        ),
    }
    receipt["rollback_receipt_sha256"] = digest(receipt)
    atomic_write_json(state_dir / "rollback_receipt.json", receipt)
    verify_optional_receipt(
        state_dir / "rollback_receipt.json", "rollback_receipt_sha256"
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("restore", "guard", "rollback"))
    parser.add_argument("--state-dir", required=True)
    parser.add_argument(
        "--workflow-file", default="evidenceops-v81-proofloop.yml"
    )
    args = parser.parse_args()
    state_dir = Path(args.state_dir)
    if args.mode == "restore":
        result = restore_previous_artifact(
            state_dir,
            repository=os.getenv("GITHUB_REPOSITORY", ""),
            workflow_file=args.workflow_file,
            token=os.getenv("GITHUB_TOKEN", ""),
            current_run_id=int(os.getenv("GITHUB_RUN_ID", "0") or 0),
            branch=os.getenv("GITHUB_REF_NAME", "local"),
            event_name=os.getenv("GITHUB_EVENT_NAME", "local"),
        )
    elif args.mode == "guard":
        release = guard_state(state_dir)
        result = {
            "state": "EXACT_STATE_READBACK_VERIFIED",
            "release_receipt_sha256": release["receipt_sha256"],
            "matter_twin_state_sha256": verify_matter_state_hash(state_dir),
            "external_effects": 0,
        }
    else:
        result = rollback_drill(state_dir)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
