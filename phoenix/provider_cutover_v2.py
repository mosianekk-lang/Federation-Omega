#!/usr/bin/env python3
"""Provider-authorised Federation Omega Phoenix cutover v2.

Dry-run is the default. Apply mode requires a user-scoped GitHub credential in
GH_ADMIN_TOKEN. Installation-only credentials are rejected because the target
repositories are owned by a personal account and are created through /user/repos.
No credential value is printed or written to a receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

API = "https://api.github.com"
API_VERSION = "2026-03-10"


class CutoverError(RuntimeError):
    pass


class GitHubAPI:
    def __init__(self, token: str):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "federation-omega-phoenix-cutover-v2",
        }

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200, 201, 204),
    ) -> tuple[int, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            API + path,
            data=data,
            method=method,
            headers=self.headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
                body = json.loads(raw) if raw else None
                if response.status not in expected:
                    raise CutoverError(
                        f"Unexpected GitHub status {response.status} for {method} {path}"
                    )
                return response.status, body
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code in expected:
                return exc.code, json.loads(detail) if detail else None
            raise CutoverError(
                f"GitHub API {method} {path} failed with {exc.code}: {detail[:1200]}"
            ) from exc

    def optional(self, path: str) -> dict[str, Any] | list[Any] | None:
        try:
            return self.request("GET", path)[1]
        except CutoverError as exc:
            if " failed with 404:" in str(exc):
                return None
            raise


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_expected_digest(path: Path, expected: str | None) -> str:
    actual = sha256_file(path)
    if expected and actual.lower() != expected.lower():
        raise CutoverError(
            f"Archive digest mismatch for {path.name}: expected {expected}, got {actual}"
        )
    return actual


def safe_extract(archive: Path, destination: Path) -> None:
    if not archive.is_file():
        raise CutoverError(f"Archive not found: {archive}")
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        if not members:
            raise CutoverError(f"Archive is empty: {archive}")
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise CutoverError(f"Unsafe archive path: {member.name}")
            if member.issym() or member.islnk() or member.isdev():
                raise CutoverError(f"Links and device entries are prohibited: {member.name}")
        bundle.extractall(destination, filter="data")


def file_inventory(root: Path, role: str) -> dict[str, Any]:
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        raise CutoverError(f"{role} export contains no files")
    relative = [path.relative_to(root).as_posix() for path in files]
    workflows = [path for path in relative if path.startswith(".github/workflows/")]
    if workflows:
        raise CutoverError(f"{role} export contains workflow files: {workflows[:5]}")
    if role == "Core":
        runtime = [
            path
            for path in relative
            if path == "runtime" or path.startswith("runtime/")
        ]
        if runtime:
            raise CutoverError(f"Core export contains runtime state: {runtime[:5]}")
    return {
        "file_count": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
        "workflow_count": len(workflows),
    }


def run(
    command: list[str],
    cwd: Path,
    environment: dict[str, str] | None = None,
) -> str:
    process = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
    )
    if process.returncode:
        raise CutoverError(
            f"Command failed ({process.returncode}): {' '.join(command)}\n"
            f"{process.stderr[-2000:]}"
        )
    return process.stdout.strip()


def authority_preflight(
    api: GitHubAPI,
    owner: str,
    legacy: str,
) -> dict[str, Any]:
    try:
        user = api.request("GET", "/user")[1]
    except CutoverError as exc:
        raise CutoverError(
            "GH_ADMIN_TOKEN must be user-scoped. Installation-only credentials "
            "cannot create repositories for a personal account."
        ) from exc

    login = str(user.get("login", ""))
    if login.lower() != owner.lower():
        raise CutoverError(
            f"Authenticated user {login!r} does not match expected owner {owner!r}"
        )

    legacy_repo = api.request("GET", f"/repos/{owner}/{legacy}")[1]
    admin = bool(legacy_repo.get("permissions", {}).get("admin"))
    if not admin:
        raise CutoverError(f"User lacks admin authority over {owner}/{legacy}")

    api.request("GET", f"/repos/{owner}/{legacy}/actions/permissions")
    api.request("GET", f"/repos/{owner}/{legacy}/rulesets?includes_parents=false")
    return {
        "authenticated_login": login,
        "user_identity_verified": True,
        "legacy_repository_admin": True,
        "repository_creation_endpoint": "/user/repos",
        "actions_administration_readback": True,
        "ruleset_administration_readback": True,
        "credential_value_recorded": False,
    }


def repository_payload(name: str, private: bool, description: str) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "private": private,
        "has_issues": True,
        "has_projects": False,
        "has_wiki": False,
        "has_discussions": False,
        "auto_init": False,
    }


def ensure_repository(
    api: GitHubAPI,
    owner: str,
    name: str,
    private: bool,
    description: str,
) -> tuple[str, dict[str, Any]]:
    existing = api.optional(f"/repos/{owner}/{name}")
    if existing is not None:
        if bool(existing.get("private")) != private:
            raise CutoverError(f"Existing {owner}/{name} has unexpected visibility")
        return "EXISTING", existing
    created = api.request(
        "POST",
        "/user/repos",
        repository_payload(name, private, description),
    )[1]
    return "CREATED", created


def git_push(
    token: str,
    owner: str,
    repo: str,
    source: Path,
    replace_existing_main: bool,
) -> str:
    remote = f"https://github.com/{owner}/{repo}.git"
    with tempfile.TemporaryDirectory(prefix="phoenix-askpass-") as temp:
        askpass = Path(temp) / "askpass.sh"
        askpass.write_text(
            "#!/bin/sh\n"
            "case \"$1\" in\n"
            "  *Username*) printf '%s\\n' 'x-access-token' ;;\n"
            "  *) printf '%s\\n' \"$PHOENIX_GIT_TOKEN\" ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        askpass.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        env = os.environ.copy()
        env.update(
            {
                "GIT_ASKPASS": str(askpass),
                "GIT_TERMINAL_PROMPT": "0",
                "PHOENIX_GIT_TOKEN": token,
            }
        )
        refs = run(["git", "ls-remote", "--heads", remote, "main"], source, env)
        if refs and not replace_existing_main:
            raise CutoverError(f"Refusing to replace existing main in {owner}/{repo}")
        run(["git", "init", "-b", "main"], source, env)
        run(["git", "config", "user.name", "Federation Omega Phoenix"], source)
        run(
            ["git", "config", "user.email", "phoenix@users.noreply.github.com"],
            source,
        )
        run(["git", "add", "--all"], source)
        run(
            [
                "git",
                "commit",
                "-m",
                "Establish verified Federation Omega Phoenix baseline",
            ],
            source,
        )
        run(["git", "remote", "add", "origin", remote], source)
        push = ["git", "push", "--set-upstream", "origin", "main"]
        if refs and replace_existing_main:
            push.append("--force-with-lease")
        run(push, source, env)
        return run(["git", "rev-parse", "HEAD"], source)


def configure_repository(api: GitHubAPI, owner: str, repo: str) -> None:
    api.request(
        "PATCH",
        f"/repos/{owner}/{repo}",
        {
            "allow_squash_merge": True,
            "allow_merge_commit": False,
            "allow_rebase_merge": False,
            "delete_branch_on_merge": True,
            "web_commit_signoff_required": True,
        },
    )
    api.request(
        "PUT",
        f"/repos/{owner}/{repo}/actions/permissions/workflow",
        {
            "default_workflow_permissions": "read",
            "can_approve_pull_request_reviews": False,
        },
    )
    api.request(
        "PUT",
        f"/repos/{owner}/{repo}/actions/permissions",
        {"enabled": False},
    )


def ruleset_payload(name: str, require_second_reviewer: bool) -> dict[str, Any]:
    return {
        "name": name,
        "target": "branch",
        "enforcement": "active",
        "conditions": {
            "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}
        },
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "required_linear_history"},
            {"type": "required_signatures"},
            {
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": (
                        1 if require_second_reviewer else 0
                    ),
                    "dismiss_stale_reviews_on_push": require_second_reviewer,
                    "require_code_owner_review": require_second_reviewer,
                    "require_last_push_approval": require_second_reviewer,
                    "required_review_thread_resolution": True,
                },
            },
        ],
        "bypass_actors": [],
    }


def ensure_ruleset(
    api: GitHubAPI,
    owner: str,
    repo: str,
    name: str,
    require_second_reviewer: bool,
) -> int:
    existing = api.request(
        "GET", f"/repos/{owner}/{repo}/rulesets?includes_parents=false"
    )[1]
    desired = ruleset_payload(name, require_second_reviewer)
    match = next((item for item in existing if item.get("name") == name), None)
    if match:
        ruleset_id = int(match["id"])
        api.request("PUT", f"/repos/{owner}/{repo}/rulesets/{ruleset_id}", desired)
        return ruleset_id
    created = api.request("POST", f"/repos/{owner}/{repo}/rulesets", desired)[1]
    return int(created["id"])


def verify_repository(
    api: GitHubAPI,
    owner: str,
    repo: str,
    expected_private: bool,
    expected_head: str,
    ruleset_id: int,
) -> dict[str, Any]:
    metadata = api.request("GET", f"/repos/{owner}/{repo}")[1]
    actions = api.request("GET", f"/repos/{owner}/{repo}/actions/permissions")[1]
    workflow = api.request(
        "GET", f"/repos/{owner}/{repo}/actions/permissions/workflow"
    )[1]
    head = api.request("GET", f"/repos/{owner}/{repo}/git/ref/heads/main")[1]
    ruleset = api.request(
        "GET", f"/repos/{owner}/{repo}/rulesets/{ruleset_id}"
    )[1]
    workflow_directory = api.optional(
        f"/repos/{owner}/{repo}/contents/.github/workflows?ref=main"
    )
    checks = {
        "default_branch_main": metadata.get("default_branch") == "main",
        "visibility_matches": bool(metadata.get("private")) == expected_private,
        "main_head_matches_export": head.get("object", {}).get("sha") == expected_head,
        "actions_disabled_at_bootstrap": actions.get("enabled") is False,
        "default_workflow_permissions_read": (
            workflow.get("default_workflow_permissions") == "read"
        ),
        "actions_cannot_approve_reviews": (
            workflow.get("can_approve_pull_request_reviews") is False
        ),
        "workflow_directory_absent": workflow_directory is None,
        "ruleset_active": ruleset.get("enforcement") == "active",
        "ruleset_targets_branch": ruleset.get("target") == "branch",
    }
    return {
        "repository": metadata.get("full_name"),
        "private": metadata.get("private"),
        "default_branch": metadata.get("default_branch"),
        "ruleset_id": ruleset_id,
        "checks": checks,
        "verified": all(checks.values()),
    }


def write_receipt(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner", default="mosianekk-lang")
    parser.add_argument("--legacy", default="Federation-Omega")
    parser.add_argument("--core", default="Federation-Omega-Core")
    parser.add_argument("--ops", default="Federation-Omega-Ops")
    parser.add_argument("--core-archive", type=Path, required=True)
    parser.add_argument("--ops-archive", type=Path, required=True)
    parser.add_argument("--expected-core-sha256")
    parser.add_argument("--expected-ops-sha256")
    parser.add_argument("--core-public", action="store_true")
    parser.add_argument("--replace-existing-main", action="store_true")
    parser.add_argument("--require-second-reviewer", action="store_true")
    parser.add_argument("--archive-legacy", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--receipt", type=Path, default=Path("phoenix-provider-cutover-v2-receipt.json")
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    core_archive = args.core_archive.resolve()
    ops_archive = args.ops_archive.resolve()
    core_digest = validate_expected_digest(core_archive, args.expected_core_sha256)
    ops_digest = validate_expected_digest(ops_archive, args.expected_ops_sha256)

    plan: dict[str, Any] = {
        "schema": "FEDOMEGA-PHOENIX-PROVIDER-CUTOVER-2",
        "mode": "APPLY" if args.apply else "DRY_RUN",
        "owner": args.owner,
        "legacy": args.legacy,
        "core": args.core,
        "ops": args.ops,
        "core_private": not args.core_public,
        "core_archive_sha256": core_digest,
        "ops_archive_sha256": ops_digest,
        "require_second_reviewer": args.require_second_reviewer,
        "archive_legacy_requested": args.archive_legacy,
        "accepted_authority_models": [
            "GitHub App user access token",
            "fine-grained personal access token",
        ],
        "installation_only_credential_accepted": False,
        "credential_value_recorded": False,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    with tempfile.TemporaryDirectory(prefix="fedomega-phoenix-cutover-") as temp:
        root = Path(temp)
        core_dir = root / "core"
        ops_dir = root / "ops"
        safe_extract(core_archive, core_dir)
        safe_extract(ops_archive, ops_dir)
        plan["core_export"] = file_inventory(core_dir, "Core")
        plan["ops_export"] = file_inventory(ops_dir, "Ops")

        if not args.apply:
            plan["status"] = "DRY_RUN_VERIFIED"
            write_receipt(args.receipt, plan)
            print(json.dumps(plan, indent=2, sort_keys=True))
            return 0

        token = os.getenv("GH_ADMIN_TOKEN", "")
        if not token:
            print("GH_ADMIN_TOKEN is required with --apply; no mutation attempted.", file=sys.stderr)
            return 2

        api = GitHubAPI(token)
        created: list[str] = []
        preflight: dict[str, Any] | None = None
        try:
            preflight = authority_preflight(api, args.owner, args.legacy)
            core_operation, _ = ensure_repository(
                api,
                args.owner,
                args.core,
                private=not args.core_public,
                description="Canonical source-only Federation Omega Core",
            )
            ops_operation, _ = ensure_repository(
                api,
                args.owner,
                args.ops,
                private=True,
                description="Private Federation Omega execution and provider operations plane",
            )
            if core_operation == "CREATED":
                created.append(f"{args.owner}/{args.core}")
            if ops_operation == "CREATED":
                created.append(f"{args.owner}/{args.ops}")

            core_head = git_push(
                token,
                args.owner,
                args.core,
                core_dir,
                args.replace_existing_main,
            )
            ops_head = git_push(
                token,
                args.owner,
                args.ops,
                ops_dir,
                args.replace_existing_main,
            )
            configure_repository(api, args.owner, args.core)
            configure_repository(api, args.owner, args.ops)
            core_ruleset = ensure_ruleset(
                api,
                args.owner,
                args.core,
                "Federation Omega Core Main",
                args.require_second_reviewer,
            )
            ops_ruleset = ensure_ruleset(
                api,
                args.owner,
                args.ops,
                "Federation Omega Ops Main",
                args.require_second_reviewer,
            )
            core_readback = verify_repository(
                api,
                args.owner,
                args.core,
                expected_private=not args.core_public,
                expected_head=core_head,
                ruleset_id=core_ruleset,
            )
            ops_readback = verify_repository(
                api,
                args.owner,
                args.ops,
                expected_private=True,
                expected_head=ops_head,
                ruleset_id=ops_ruleset,
            )
            if not core_readback["verified"] or not ops_readback["verified"]:
                raise CutoverError("Core or Ops provider readback failed")

            api.request(
                "PUT",
                f"/repos/{args.owner}/{args.legacy}/actions/permissions",
                {"enabled": False},
            )
            legacy_actions = api.request(
                "GET", f"/repos/{args.owner}/{args.legacy}/actions/permissions"
            )[1]
            legacy_actions_disabled = legacy_actions.get("enabled") is False
            if not legacy_actions_disabled:
                raise CutoverError("Legacy Actions disable readback failed")

            legacy_archived = False
            if args.archive_legacy:
                api.request(
                    "PATCH",
                    f"/repos/{args.owner}/{args.legacy}",
                    {"archived": True},
                )
                legacy_archived = bool(
                    api.request("GET", f"/repos/{args.owner}/{args.legacy}")[1].get(
                        "archived"
                    )
                )
                if not legacy_archived:
                    raise CutoverError("Legacy archive readback failed")

            receipt = {
                **plan,
                "status": "VERIFIED",
                "authority_preflight": preflight,
                "created_repositories": created,
                "core_operation": core_operation,
                "ops_operation": ops_operation,
                "core_head_sha": core_head,
                "ops_head_sha": ops_head,
                "core_readback": core_readback,
                "ops_readback": ops_readback,
                "legacy_actions_disabled": legacy_actions_disabled,
                "legacy_archived": legacy_archived,
                "rollback": {
                    "legacy_history_rewritten": False,
                    "automatic_repository_deletion": False,
                    "source_archives_preserved": True,
                },
            }
        except Exception as exc:
            receipt = {
                **plan,
                "status": "FAILED_CLOSED",
                "authority_preflight": preflight,
                "created_repositories": created,
                "error": str(exc),
                "automatic_destructive_rollback_attempted": False,
            }

    write_receipt(args.receipt, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
