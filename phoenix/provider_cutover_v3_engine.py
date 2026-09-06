#!/usr/bin/env python3
"""Idempotent provider-side Phoenix repository cutover.

Dry-run is the default. Mutations require --apply and GH_ADMIN_TOKEN.
The token is never printed, written into Git configuration, or persisted in a
receipt. The program creates clean Core and private Ops repositories, pushes
prepared export directories, applies baseline governance, disables Actions in
the legacy repository, verifies provider readback, and optionally archives the
legacy repository only after all earlier gates pass.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API = "https://api.github.com"
API_VERSION = "2022-11-28"


class ProviderError(RuntimeError):
    pass


class GitHubAPI:
    def __init__(self, token: str):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "federation-omega-phoenix-cutover",
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
            API + path, data=data, method=method, headers=self.headers
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
                parsed = json.loads(body) if body else None
                if response.status not in expected:
                    raise ProviderError(
                        f"Unexpected GitHub status {response.status} for {method} {path}"
                    )
                return response.status, parsed
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code in expected:
                return exc.code, json.loads(body) if body else None
            raise ProviderError(
                f"GitHub API {method} {path} failed with {exc.code}: {body[:1200]}"
            ) from exc

    def get_optional(self, path: str) -> dict[str, Any] | None:
        try:
            _, payload = self.request("GET", path)
            return payload
        except ProviderError as exc:
            if " failed with 404:" in str(exc):
                return None
            raise


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    process = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
    )
    if process.returncode:
        raise ProviderError(
            f"Command failed ({process.returncode}): {' '.join(command)}\n"
            f"{process.stderr[-2000:]}"
        )
    return process.stdout.strip()


def validate_export(path: Path, role: str) -> dict[str, Any]:
    if not path.is_dir():
        raise ProviderError(f"{role} export directory missing: {path}")
    files = sorted(item for item in path.rglob("*") if item.is_file())
    if not files:
        raise ProviderError(f"{role} export directory is empty: {path}")
    if any(item.is_symlink() for item in path.rglob("*")):
        raise ProviderError(f"{role} export contains a symlink")
    workflows = [
        item for item in files
        if item.relative_to(path).as_posix().startswith(".github/workflows/")
    ]
    if workflows:
        raise ProviderError(f"{role} export unexpectedly contains active workflows")
    return {
        "path": str(path.resolve()),
        "file_count": len(files),
        "total_bytes": sum(item.stat().st_size for item in files),
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
) -> tuple[dict[str, Any], str]:
    existing = api.get_optional(f"/repos/{owner}/{name}")
    if existing:
        if bool(existing.get("private")) != private:
            raise ProviderError(
                f"Existing repository {owner}/{name} has unexpected visibility"
            )
        return existing, "EXISTING"
    _, created = api.request(
        "POST", "/user/repos", repository_payload(name, private, description)
    )
    return created, "CREATED"


def configure_repository(api: GitHubAPI, owner: str, name: str) -> None:
    api.request(
        "PATCH",
        f"/repos/{owner}/{name}",
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
        f"/repos/{owner}/{name}/actions/permissions/workflow",
        {
            "default_workflow_permissions": "read",
            "can_approve_pull_request_reviews": False,
        },
    )


def ruleset_payload(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "target": "branch",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "include": ["~DEFAULT_BRANCH"],
                "exclude": [],
            }
        },
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "required_linear_history"},
            {"type": "required_signatures"},
            {
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": 1,
                    "dismiss_stale_reviews_on_push": True,
                    "require_code_owner_review": True,
                    "require_last_push_approval": True,
                    "required_review_thread_resolution": True,
                },
            },
        ],
        "bypass_actors": [],
    }


def ensure_ruleset(api: GitHubAPI, owner: str, repo: str, name: str) -> int:
    _, existing = api.request(
        "GET", f"/repos/{owner}/{repo}/rulesets?includes_parents=false"
    )
    match = next((item for item in existing if item.get("name") == name), None)
    desired = ruleset_payload(name)
    if match:
        ruleset_id = int(match["id"])
        api.request(
            "PUT", f"/repos/{owner}/{repo}/rulesets/{ruleset_id}", desired
        )
        return ruleset_id
    _, created = api.request("POST", f"/repos/{owner}/{repo}/rulesets", desired)
    return int(created["id"])


def push_export(
    token: str,
    owner: str,
    repo: str,
    source: Path,
    allow_existing_main: bool,
) -> str:
    remote = f"https://github.com/{owner}/{repo}.git"
    with tempfile.TemporaryDirectory(prefix="phoenix-git-auth-") as temporary:
        askpass = Path(temporary) / "askpass.sh"
        askpass.write_text(
            "#!/bin/sh\n"
            "case \"$1\" in\n"
            "  *Username*) printf '%s\\n' 'x-access-token' ;;\n"
            "  *) printf '%s\\n' \"$PHOENIX_GIT_TOKEN\" ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        askpass.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        environment = os.environ.copy()
        environment.update(
            {
                "GIT_ASKPASS": str(askpass),
                "GIT_TERMINAL_PROMPT": "0",
                "PHOENIX_GIT_TOKEN": token,
            }
        )
        refs = run(["git", "ls-remote", "--heads", remote, "main"], source, environment)
        if refs and not allow_existing_main:
            raise ProviderError(
                f"Refusing to replace existing main branch in {owner}/{repo}"
            )
        if not (source / ".git").exists():
            run(["git", "init", "-b", "main"], source, environment)
        run(["git", "config", "user.name", "Federation Omega Phoenix"], source)
        run(
            ["git", "config", "user.email", "phoenix@users.noreply.github.com"],
            source,
        )
        run(["git", "add", "--all"], source)
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=source
        ).returncode != 0
        if staged:
            run(
                [
                    "git",
                    "commit",
                    "-m",
                    "Establish verified Federation Omega Phoenix baseline",
                ],
                source,
            )
        remotes = run(["git", "remote"], source)
        if "origin" in remotes.splitlines():
            run(["git", "remote", "set-url", "origin", remote], source)
        else:
            run(["git", "remote", "add", "origin", remote], source)
        arguments = ["git", "push", "--set-upstream", "origin", "main"]
        if refs and allow_existing_main:
            arguments.append("--force-with-lease")
        run(arguments, source, environment)
        return run(["git", "rev-parse", "HEAD"], source)


def disable_legacy_actions(api: GitHubAPI, owner: str, legacy: str) -> None:
    api.request(
        "PUT",
        f"/repos/{owner}/{legacy}/actions/permissions",
        {"enabled": False},
    )


def verify_repository(
    api: GitHubAPI,
    owner: str,
    repo: str,
    ruleset_id: int,
) -> dict[str, Any]:
    _, metadata = api.request("GET", f"/repos/{owner}/{repo}")
    _, workflow = api.request(
        "GET", f"/repos/{owner}/{repo}/actions/permissions/workflow"
    )
    _, ruleset = api.request(
        "GET", f"/repos/{owner}/{repo}/rulesets/{ruleset_id}"
    )
    checks = {
        "default_branch_main": metadata.get("default_branch") == "main",
        "default_workflow_permissions_read": (
            workflow.get("default_workflow_permissions") == "read"
        ),
        "actions_cannot_approve_reviews": (
            workflow.get("can_approve_pull_request_reviews") is False
        ),
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner", default="mosianekk-lang")
    parser.add_argument("--legacy", default="Federation-Omega")
    parser.add_argument("--core", default="Federation-Omega-Core")
    parser.add_argument("--ops", default="Federation-Omega-Ops")
    parser.add_argument("--core-dir", type=Path, required=True)
    parser.add_argument("--ops-dir", type=Path, required=True)
    parser.add_argument("--core-public", action="store_true")
    parser.add_argument("--replace-existing-main", action="store_true")
    parser.add_argument("--archive-legacy", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--receipt", type=Path, default=Path("phoenix-provider-cutover-receipt.json")
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    core_info = validate_export(args.core_dir.resolve(), "Core")
    ops_info = validate_export(args.ops_dir.resolve(), "Ops")
    plan = {
        "schema": "FEDOMEGA-PHOENIX-PROVIDER-CUTOVER-1",
        "mode": "APPLY" if args.apply else "DRY_RUN",
        "owner": args.owner,
        "legacy": args.legacy,
        "core": args.core,
        "ops": args.ops,
        "core_private": not args.core_public,
        "core_export": core_info,
        "ops_export": ops_info,
        "archive_legacy_requested": args.archive_legacy,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "secret_values_recorded": False,
    }
    if not args.apply:
        plan["status"] = "DRY_RUN_VERIFIED"
        args.receipt.write_text(
            json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    token = os.getenv("GH_ADMIN_TOKEN", "")
    if not token:
        print("GH_ADMIN_TOKEN is required with --apply; no mutation attempted.", file=sys.stderr)
        return 2

    api = GitHubAPI(token)
    created: list[str] = []
    try:
        _, core_operation = ensure_repository(
            api,
            args.owner,
            args.core,
            private=not args.core_public,
            description="Canonical source-only Federation Omega Core",
        )
        _, ops_operation = ensure_repository(
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

        core_sha = push_export(
            token,
            args.owner,
            args.core,
            args.core_dir.resolve(),
            args.replace_existing_main,
        )
        ops_sha = push_export(
            token,
            args.owner,
            args.ops,
            args.ops_dir.resolve(),
            args.replace_existing_main,
        )
        configure_repository(api, args.owner, args.core)
        configure_repository(api, args.owner, args.ops)
        core_ruleset = ensure_ruleset(
            api, args.owner, args.core, "Federation Omega Core Main"
        )
        ops_ruleset = ensure_ruleset(
            api, args.owner, args.ops, "Federation Omega Ops Main"
        )
        core_readback = verify_repository(
            api, args.owner, args.core, core_ruleset
        )
        ops_readback = verify_repository(api, args.owner, args.ops, ops_ruleset)
        if not core_readback["verified"] or not ops_readback["verified"]:
            raise ProviderError("Core or Ops provider readback failed")

        disable_legacy_actions(api, args.owner, args.legacy)
        _, legacy_actions = api.request(
            "GET", f"/repos/{args.owner}/{args.legacy}/actions/permissions"
        )
        legacy_actions_disabled = legacy_actions.get("enabled") is False
        if not legacy_actions_disabled:
            raise ProviderError("Legacy Actions disable readback failed")

        legacy_archived = False
        if args.archive_legacy:
            api.request(
                "PATCH",
                f"/repos/{args.owner}/{args.legacy}",
                {"archived": True},
            )
            _, legacy_readback = api.request(
                "GET", f"/repos/{args.owner}/{args.legacy}"
            )
            legacy_archived = legacy_readback.get("archived") is True
            if not legacy_archived:
                raise ProviderError("Legacy archive readback failed")

        receipt = {
            **plan,
            "status": "VERIFIED",
            "created_repositories": created,
            "core_operation": core_operation,
            "ops_operation": ops_operation,
            "core_head_sha": core_sha,
            "ops_head_sha": ops_sha,
            "core_readback": core_readback,
            "ops_readback": ops_readback,
            "legacy_actions_disabled": legacy_actions_disabled,
            "legacy_archived": legacy_archived,
            "rollback": {
                "automatic_repository_deletion": False,
                "legacy_history_rewritten": False,
                "new_repositories_can_be_unarchived_or removed only by owner": True,
            },
        }
    except Exception as exc:
        receipt = {
            **plan,
            "status": "FAILED_CLOSED",
            "created_repositories": created,
            "error": str(exc),
            "automatic_destructive_rollback_attempted": False,
        }

    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
