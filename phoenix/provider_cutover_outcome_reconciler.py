#!/usr/bin/env python3
"""Reconstruct a Phoenix cutover receipt from provider-native GET readback only.

This command is for an authorization-use record already in ``APPLY_STARTED``
when the provider process did not leave a trustworthy receipt. It never retries
or performs the provider mutation. Exact archive contents, repository controls
and legacy quarantine must all match before a compatible receipt is emitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tarfile
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

API = "https://api.github.com"
API_VERSION = "2026-03-10"
RECEIPT_SCHEMA = "FEDOMEGA-PHOENIX-PROVIDER-CUTOVER-3"
RECONCILIATION_SCHEMA = "FEDOMEGA-PHOENIX-PROVIDER-OUTCOME-RECONCILIATION-1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ReconciliationError(RuntimeError):
    """Fail-closed provider readback or integrity error."""


class ReadOnlyProvider(Protocol):
    def get(self, path: str) -> Any: ...
    def optional(self, path: str) -> Any | None: ...


class GitHubReadOnlyAPI:
    """GET-only GitHub client; no write verb is exposed."""

    def __init__(self, token: str):
        if not token:
            raise ReconciliationError("read-only provider authority is required")
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "federation-omega-phoenix-outcome-reconciler",
        }

    def get(self, path: str) -> Any:
        request = urllib.request.Request(API + path, method="GET", headers=self.headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
                if response.status != 200:
                    raise ReconciliationError(
                        f"unexpected GitHub status {response.status} for GET {path}"
                    )
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ReconciliationError(
                f"GitHub API GET {path} failed with {exc.code}: {detail[:1200]}"
            ) from exc

    def optional(self, path: str) -> Any | None:
        try:
            return self.get(path)
        except ReconciliationError as exc:
            if " failed with 404:" in str(exc):
                return None
            raise


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def blob_sha1(content: bytes) -> str:
    return hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()


def safe_path(name: str) -> str:
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ReconciliationError(f"unsafe archive/provider path: {name}")
    normalized = path.as_posix().removeprefix("./")
    if not normalized or normalized == ".":
        raise ReconciliationError(f"invalid archive/provider path: {name}")
    return normalized


def archive_inventory(archive: Path, role: str) -> dict[str, Any]:
    if not archive.is_file():
        raise ReconciliationError(f"{role} archive is missing")
    files: dict[str, dict[str, Any]] = {}
    try:
        bundle = tarfile.open(archive, "r:gz")
    except (OSError, tarfile.TarError) as exc:
        raise ReconciliationError(f"{role} archive is unreadable") from exc
    with bundle:
        for member in bundle.getmembers():
            path = safe_path(member.name)
            if member.isdir():
                continue
            if not member.isfile() or member.issym() or member.islnk() or member.isdev():
                raise ReconciliationError(f"{role} has prohibited entry: {path}")
            if path in files:
                raise ReconciliationError(f"{role} has duplicate path: {path}")
            stream = bundle.extractfile(member)
            if stream is None:
                raise ReconciliationError(f"{role} cannot read: {path}")
            content = stream.read()
            if len(content) != member.size:
                raise ReconciliationError(f"{role} size mismatch: {path}")
            files[path] = {
                "sha": blob_sha1(content),
                "size": len(content),
                "mode": "100755" if member.mode & stat.S_IXUSR else "100644",
            }
    if not files:
        raise ReconciliationError(f"{role} archive is empty")
    return {
        "files": files,
        "file_count": len(files),
        "total_bytes": sum(item["size"] for item in files.values()),
    }


def provider_inventory(
    api: ReadOnlyProvider, owner: str, repo: str, head_sha: str
) -> dict[str, Any]:
    if not HEX40.fullmatch(head_sha):
        raise ReconciliationError(f"{owner}/{repo} returned invalid main SHA")
    payload = api.get(f"/repos/{owner}/{repo}/git/trees/{head_sha}?recursive=1")
    if not isinstance(payload, dict) or payload.get("truncated") is True:
        raise ReconciliationError(f"{owner}/{repo} tree is missing or truncated")
    tree = payload.get("tree")
    if not isinstance(tree, list):
        raise ReconciliationError(f"{owner}/{repo} tree is malformed")
    files: dict[str, dict[str, Any]] = {}
    for item in tree:
        if not isinstance(item, dict):
            raise ReconciliationError(f"{owner}/{repo} has malformed tree entry")
        if item.get("type") == "tree":
            continue
        path = safe_path(str(item.get("path", "")))
        mode = str(item.get("mode", ""))
        sha = str(item.get("sha", "")).lower()
        size = item.get("size")
        if item.get("type") != "blob" or mode not in {"100644", "100755"}:
            raise ReconciliationError(f"{owner}/{repo} has unsupported object: {path}")
        if not HEX40.fullmatch(sha) or not isinstance(size, int) or size < 0:
            raise ReconciliationError(f"{owner}/{repo} has invalid blob metadata: {path}")
        if path in files:
            raise ReconciliationError(f"{owner}/{repo} has duplicate path: {path}")
        files[path] = {"sha": sha, "size": size, "mode": mode}
    if not files:
        raise ReconciliationError(f"{owner}/{repo} tree contains no files")
    return {
        "files": files,
        "file_count": len(files),
        "total_bytes": sum(item["size"] for item in files.values()),
    }


def exact_match(expected: dict[str, Any], observed: dict[str, Any], role: str) -> dict[str, Any]:
    expected_files, observed_files = expected["files"], observed["files"]
    missing = sorted(set(expected_files) - set(observed_files))
    unexpected = sorted(set(observed_files) - set(expected_files))
    changed = sorted(
        path for path in set(expected_files) & set(observed_files)
        if expected_files[path] != observed_files[path]
    )
    if missing or unexpected or changed:
        raise ReconciliationError(
            f"{role} content mismatch: missing={missing[:10]}, "
            f"unexpected={unexpected[:10]}, changed={changed[:10]}"
        )
    return {
        "exact_file_inventory_match": True,
        "file_count": expected["file_count"],
        "total_bytes": expected["total_bytes"],
        "missing": [],
        "unexpected": [],
        "changed": [],
    }


def has_active_branch_ruleset(api: ReadOnlyProvider, owner: str, repo: str) -> bool:
    payload = api.get(f"/repos/{owner}/{repo}/rulesets?includes_parents=false")
    if not isinstance(payload, list):
        raise ReconciliationError(f"{owner}/{repo} ruleset list is malformed")
    return any(
        isinstance(item, dict)
        and item.get("enforcement") == "active"
        and item.get("target") == "branch"
        for item in payload
    )


def verify_repository(
    api: ReadOnlyProvider,
    *,
    owner: str,
    repo: str,
    expected_private: bool,
    expected_inventory: dict[str, Any],
) -> dict[str, Any]:
    metadata = api.get(f"/repos/{owner}/{repo}")
    actions = api.get(f"/repos/{owner}/{repo}/actions/permissions")
    workflow = api.get(f"/repos/{owner}/{repo}/actions/permissions/workflow")
    head = api.get(f"/repos/{owner}/{repo}/git/ref/heads/main")
    workflows = api.optional(f"/repos/{owner}/{repo}/contents/.github/workflows?ref=main")
    if not isinstance(metadata, dict) or not isinstance(head, dict):
        raise ReconciliationError(f"{owner}/{repo} readback is malformed")
    head_sha = str(head.get("object", {}).get("sha", "")).lower()
    content = exact_match(
        expected_inventory,
        provider_inventory(api, owner, repo, head_sha),
        f"{owner}/{repo}",
    )
    checks = {
        "repository_name_matches": metadata.get("full_name") == f"{owner}/{repo}",
        "owner_admin_authority": bool(metadata.get("permissions", {}).get("admin")),
        "default_branch_main": metadata.get("default_branch") == "main",
        "visibility_matches": bool(metadata.get("private")) == expected_private,
        "actions_disabled_at_bootstrap": actions.get("enabled") is False,
        "default_workflow_permissions_read": workflow.get("default_workflow_permissions") == "read",
        "actions_cannot_approve_reviews": workflow.get("can_approve_pull_request_reviews") is False,
        "workflow_directory_absent": workflows is None,
        "active_branch_ruleset": has_active_branch_ruleset(api, owner, repo),
        "exact_export_content": content["exact_file_inventory_match"],
    }
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise ReconciliationError(f"{owner}/{repo} readback failed: {failed}")
    return {
        "repository": metadata.get("full_name"),
        "private": metadata.get("private"),
        "default_branch": metadata.get("default_branch"),
        "main_head_sha": head_sha,
        "checks": checks,
        "content": content,
        "verified": True,
    }


def authority_preflight(
    api: ReadOnlyProvider, *, owner: str, legacy: str, requested: str
) -> dict[str, Any]:
    if requested not in {"auto", "user", "installation"}:
        raise ReconciliationError(f"unsupported authority mode: {requested}")
    user_error: Exception | None = None
    if requested in {"auto", "user"}:
        try:
            user = api.get("/user")
            source = api.get(f"/repos/{owner}/{legacy}")
            if str(user.get("login", "")).lower() != owner.lower():
                raise ReconciliationError("authenticated user does not match owner")
            if not bool(source.get("permissions", {}).get("admin")):
                raise ReconciliationError("user lacks legacy repository admin authority")
            return {
                "authority_model": "USER_SCOPED",
                "authenticated_login": user.get("login"),
                "read_only_reconciliation": True,
                "credential_value_recorded": False,
            }
        except Exception as exc:
            user_error = exc
            if requested == "user":
                raise
    try:
        installation = api.get("/installation/repositories?per_page=100")
        repos = installation.get("repositories", []) if isinstance(installation, dict) else []
        source = api.get(f"/repos/{owner}/{legacy}")
        accessible = {
            str(item.get("full_name", "")).lower()
            for item in repos
            if isinstance(item, dict)
        }
        if f"{owner}/{legacy}".lower() not in accessible:
            raise ReconciliationError("installation cannot access legacy repository")
        if not bool(source.get("permissions", {}).get("admin")):
            raise ReconciliationError("installation lacks legacy repository admin authority")
        return {
            "authority_model": "INSTALLATION_TEMPLATE",
            "authenticated_installation": True,
            "read_only_reconciliation": True,
            "credential_value_recorded": False,
        }
    except Exception as exc:
        if requested == "installation":
            raise
        raise ReconciliationError(
            f"no usable read-only authority; user={user_error}; installation={exc}"
        ) from exc


def validate_digest(path: Path, expected: str, role: str) -> str:
    expected = expected.lower()
    if not HEX64.fullmatch(expected):
        raise ReconciliationError(f"{role} expected SHA-256 is invalid")
    actual = sha256_file(path)
    if actual != expected:
        raise ReconciliationError(f"{role} SHA-256 mismatch: expected {expected}, got {actual}")
    return actual


def reconcile(
    api: ReadOnlyProvider,
    *,
    owner: str,
    legacy: str,
    core: str,
    ops: str,
    core_archive: Path,
    ops_archive: Path,
    expected_core_sha256: str,
    expected_ops_sha256: str,
    preflight: dict[str, Any],
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    if preflight.get("read_only_reconciliation") is not True:
        raise ReconciliationError("read-only authority preflight is required")
    if preflight.get("credential_value_recorded") is not False:
        raise ReconciliationError("credential boundary is invalid")
    core_digest = validate_digest(core_archive, expected_core_sha256, "Core archive")
    ops_digest = validate_digest(ops_archive, expected_ops_sha256, "Ops archive")
    core_readback = verify_repository(
        api,
        owner=owner,
        repo=core,
        expected_private=True,
        expected_inventory=archive_inventory(core_archive, "Core"),
    )
    ops_readback = verify_repository(
        api,
        owner=owner,
        repo=ops,
        expected_private=True,
        expected_inventory=archive_inventory(ops_archive, "Ops"),
    )
    source = api.get(f"/repos/{owner}/{legacy}")
    source_actions = api.get(f"/repos/{owner}/{legacy}/actions/permissions")
    if source_actions.get("enabled") is not False:
        raise ReconciliationError("legacy Actions disable readback failed")
    if source.get("is_template") is not False:
        raise ReconciliationError("legacy repository remains in template mode")
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "status": "VERIFIED",
        "mode": "READ_ONLY_PROVIDER_OUTCOME_RECONCILIATION",
        "reconciliation_schema": RECONCILIATION_SCHEMA,
        "owner": owner,
        "legacy": legacy,
        "core": core,
        "ops": ops,
        "core_private": True,
        "core_archive_sha256": core_digest,
        "ops_archive_sha256": ops_digest,
        "authority_preflight": preflight,
        "created_repositories": [],
        "core_operation": "OBSERVED_EXISTING",
        "ops_operation": "OBSERVED_EXISTING",
        "core_head_sha": core_readback["main_head_sha"],
        "ops_head_sha": ops_readback["main_head_sha"],
        "core_readback": core_readback,
        "ops_readback": ops_readback,
        "legacy_actions_disabled": True,
        "legacy_template_state_after": False,
        "legacy_archived": bool(source.get("archived")),
        "provider_apply_replayed": False,
        "provider_mutation_performed": False,
        "automatic_retry_performed": False,
        "credential_value_recorded": False,
        "external_commercial_gates_advanced": False,
        "reconciled_at": (observed_at or datetime.now(timezone.utc)).isoformat(),
        "rollback": {
            "legacy_history_rewritten": False,
            "temporary_template_state_restored": True,
            "automatic_repository_deletion": False,
            "source_archives_preserved": True,
        },
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
            stream.write((json.dumps(payload, indent=2, sort_keys=True) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner", default="mosianekk-lang")
    parser.add_argument("--legacy", default="Federation-Omega")
    parser.add_argument("--core", default="Federation-Omega-Core")
    parser.add_argument("--ops", default="Federation-Omega-Ops")
    parser.add_argument("--core-archive", type=Path, required=True)
    parser.add_argument("--ops-archive", type=Path, required=True)
    parser.add_argument("--expected-core-sha256", required=True)
    parser.add_argument("--expected-ops-sha256", required=True)
    parser.add_argument(
        "--authority-mode",
        choices=["auto", "user", "installation"],
        default="auto",
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path("phoenix-provider-cutover-v3-receipt.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.getenv("GH_ADMIN_TOKEN", "")
    if not token:
        print(
            "GH_ADMIN_TOKEN is required for readback; no mutation attempted.",
            file=os.sys.stderr,
        )
        return 2
    api = GitHubReadOnlyAPI(token)
    try:
        result = reconcile(
            api,
            owner=args.owner,
            legacy=args.legacy,
            core=args.core,
            ops=args.ops,
            core_archive=args.core_archive.resolve(),
            ops_archive=args.ops_archive.resolve(),
            expected_core_sha256=args.expected_core_sha256,
            expected_ops_sha256=args.expected_ops_sha256,
            preflight=authority_preflight(
                api,
                owner=args.owner,
                legacy=args.legacy,
                requested=args.authority_mode,
            ),
        )
    except ReconciliationError as exc:
        print(str(exc), file=os.sys.stderr)
        return 1
    write_atomic(args.receipt, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
