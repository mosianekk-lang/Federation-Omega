#!/usr/bin/env python3
"""Apply and verify the Federation Omega Main Airlock provider controls.

Dry-run is the default. Apply requires GH_ADMIN_TOKEN and performs no source
write to main. A temporary branch and temporary ruleset are used for the
negative direct-update canary; both are removed before the canonical ruleset is
created or updated. Credential values are never printed or persisted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API = "https://api.github.com"
API_VERSION = "2022-11-28"
EXPECTED_RULE_TYPES = {
    "deletion",
    "non_fast_forward",
    "required_linear_history",
    "required_signatures",
    "pull_request",
    "required_status_checks",
}
HEX40 = re.compile(r"^[0-9a-f]{40}$")


class ActivationError(RuntimeError):
    pass


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def write_receipt(path: Path, payload: dict[str, Any]) -> None:
    body = dict(payload)
    body.pop("receipt_sha256", None)
    body["receipt_sha256"] = canonical_sha256(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_ruleset(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("name") != "Federation Omega Main Airlock":
        raise ActivationError("unexpected ruleset name")
    if payload.get("target") != "branch" or payload.get("enforcement") != "active":
        raise ActivationError("ruleset must target branches with active enforcement")
    if payload.get("bypass_actors") != []:
        raise ActivationError("ruleset must have zero bypass actors")
    conditions = payload.get("conditions", {}).get("ref_name", {})
    if conditions.get("include") != ["~DEFAULT_BRANCH"] or conditions.get("exclude") != []:
        raise ActivationError("ruleset must target only the default branch")
    rules = payload.get("rules")
    if not isinstance(rules, list):
        raise ActivationError("rules must be a list")
    by_type = {item.get("type"): item for item in rules if isinstance(item, dict)}
    missing = EXPECTED_RULE_TYPES - set(by_type)
    if missing:
        raise ActivationError(f"ruleset missing required rule types: {sorted(missing)}")
    pr = by_type["pull_request"].get("parameters", {})
    if pr.get("required_approving_review_count") != 0:
        raise ActivationError("sole-owner ruleset must require zero approvals")
    if pr.get("require_code_owner_review") is not False:
        raise ActivationError("code-owner review must remain disabled until a second reviewer exists")
    if pr.get("require_last_push_approval") is not False:
        raise ActivationError("latest-push approval must remain disabled until a second reviewer exists")
    if pr.get("required_review_thread_resolution") is not True:
        raise ActivationError("review-thread resolution must be required")
    checks = by_type["required_status_checks"].get("parameters", {})
    if checks.get("strict_required_status_checks_policy") is not True:
        raise ActivationError("required status checks must be strict")
    if checks.get("required_status_checks") != [{"context": "admission"}]:
        raise ActivationError("admission must be the sole required status context")
    return payload


def canonical_ruleset_view(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: payload.get(key)
        for key in ("name", "target", "enforcement", "bypass_actors", "conditions", "rules")
    }


def canary_ruleset(desired: dict[str, Any], branch: str) -> dict[str, Any]:
    result = json.loads(json.dumps(desired))
    result["name"] = f"Federation Omega Airlock Canary {branch.rsplit('-', 1)[-1]}"
    result["conditions"] = {
        "ref_name": {"include": [f"refs/heads/{branch}"], "exclude": []}
    }
    return result


class GitHubAPI:
    def __init__(self, token: str):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "federation-omega-provider-airlock-activator",
        }

    def request_raw(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(API + path, data=data, method=method, headers=self.headers)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
                return response.status, json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                parsed: Any = json.loads(body) if body else None
            except json.JSONDecodeError:
                parsed = {"message": body[:1000]}
            return exc.code, parsed

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200, 201, 204),
    ) -> Any:
        status, body = self.request_raw(method, path, payload)
        if status not in expected:
            detail = body.get("message") if isinstance(body, dict) else body
            raise ActivationError(f"GitHub API {method} {path} failed with {status}: {detail}")
        return body


def detect_authority(api: GitHubAPI, owner: str, repo: str) -> dict[str, Any]:
    status, user = api.request_raw("GET", "/user")
    if status == 200:
        if user.get("login") != owner:
            raise ActivationError(f"authenticated user must be {owner}")
        mode = "USER_SCOPED"
        principal = user.get("login")
    else:
        installations = api.request("GET", "/installation/repositories?per_page=100")
        names = {item.get("full_name") for item in installations.get("repositories", [])}
        if f"{owner}/{repo}" not in names:
            raise ActivationError("installation token does not include the target repository")
        mode = "INSTALLATION_SCOPED"
        principal = "GITHUB_APP_INSTALLATION"
    metadata = api.request("GET", f"/repos/{owner}/{repo}")
    if metadata.get("default_branch") != "main":
        raise ActivationError("default branch must be main")
    if metadata.get("permissions", {}).get("admin") is not True:
        raise ActivationError("authenticated principal lacks repository admin standing")
    return {"authority_mode": mode, "principal": principal, "repository_admin": True}


def ref_sha(api: GitHubAPI, owner: str, repo: str, branch: str) -> str:
    ref = api.request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{urllib.parse.quote(branch, safe='')}")
    sha = ref.get("object", {}).get("sha", "")
    if not HEX40.fullmatch(sha):
        raise ActivationError(f"invalid branch SHA for {branch}")
    return sha


def active_rule_types(api: GitHubAPI, owner: str, repo: str, branch: str) -> set[str]:
    rules = api.request(
        "GET", f"/repos/{owner}/{repo}/rules/branches/{urllib.parse.quote(branch, safe='')}"
    )
    if not isinstance(rules, list):
        raise ActivationError("branch rules readback is not a list")
    return {item.get("type") for item in rules if isinstance(item, dict)}


def create_or_update_main_ruleset(
    api: GitHubAPI, owner: str, repo: str, desired: dict[str, Any]
) -> tuple[int, str]:
    existing = api.request("GET", f"/repos/{owner}/{repo}/rulesets?includes_parents=false")
    match = next((item for item in existing if item.get("name") == desired["name"]), None)
    if match:
        ruleset_id = int(match["id"])
        api.request("PUT", f"/repos/{owner}/{repo}/rulesets/{ruleset_id}", desired)
        return ruleset_id, "UPDATED"
    created = api.request("POST", f"/repos/{owner}/{repo}/rulesets", desired)
    return int(created["id"]), "CREATED"


def run_negative_canary(api: GitHubAPI, owner: str, repo: str, main_sha: str, desired: dict[str, Any]) -> dict[str, Any]:
    suffix = uuid.uuid4().hex[:12]
    branch = f"phoenix-ruleset-canary-{suffix}"
    temporary_ruleset_id: int | None = None
    update_status: int | None = None
    cleanup_errors: list[str] = []
    try:
        api.request("POST", f"/repos/{owner}/{repo}/git/refs", {"ref": f"refs/heads/{branch}", "sha": main_sha})
        temporary = api.request("POST", f"/repos/{owner}/{repo}/rulesets", canary_ruleset(desired, branch))
        temporary_ruleset_id = int(temporary["id"])
        applied = active_rule_types(api, owner, repo, branch)
        missing = EXPECTED_RULE_TYPES - applied
        if missing:
            raise ActivationError(f"temporary canary ruleset missing active rules: {sorted(missing)}")
        commit = api.request("GET", f"/repos/{owner}/{repo}/git/commits/{main_sha}")
        tree_sha = commit.get("tree", {}).get("sha")
        if not tree_sha:
            raise ActivationError("unable to resolve main tree for negative canary")
        candidate = api.request(
            "POST",
            f"/repos/{owner}/{repo}/git/commits",
            {
                "message": f"Phoenix ruleset negative canary {suffix}",
                "tree": tree_sha,
                "parents": [main_sha],
            },
        )
        candidate_sha = candidate.get("sha")
        if not isinstance(candidate_sha, str) or not HEX40.fullmatch(candidate_sha):
            raise ActivationError("invalid negative-canary commit SHA")
        update_status, _ = api.request_raw(
            "PATCH",
            f"/repos/{owner}/{repo}/git/refs/heads/{urllib.parse.quote(branch, safe='')}",
            {"sha": candidate_sha, "force": False},
        )
        if update_status not in {403, 409, 422}:
            raise ActivationError(
                f"negative canary was not rejected by GitHub; ref update returned {update_status}"
            )
        return {
            "branch": branch,
            "temporary_ruleset_id": temporary_ruleset_id,
            "direct_update_rejected": True,
            "rejection_status": update_status,
            "main_mutation_attempted": False,
        }
    finally:
        if temporary_ruleset_id is not None:
            status, body = api.request_raw(
                "DELETE", f"/repos/{owner}/{repo}/rulesets/{temporary_ruleset_id}"
            )
            if status != 204:
                cleanup_errors.append(f"temporary_ruleset_delete:{status}:{body}")
        status, body = api.request_raw(
            "DELETE", f"/repos/{owner}/{repo}/git/refs/heads/{urllib.parse.quote(branch, safe='')}"
        )
        if status not in {204, 404}:
            cleanup_errors.append(f"temporary_branch_delete:{status}:{body}")
        if cleanup_errors and sys.exc_info()[0] is None:
            raise ActivationError("negative-canary cleanup failed: " + "; ".join(cleanup_errors))


def verify_provider_state(
    api: GitHubAPI,
    owner: str,
    repo: str,
    ruleset_id: int,
    desired: dict[str, Any],
    expected_main_sha: str,
) -> dict[str, Any]:
    actual = api.request("GET", f"/repos/{owner}/{repo}/rulesets/{ruleset_id}")
    workflow = api.request("GET", f"/repos/{owner}/{repo}/actions/permissions/workflow")
    rules = active_rule_types(api, owner, repo, "main")
    current_main_sha = ref_sha(api, owner, repo, "main")
    checks = {
        "ruleset_exact": canonical_ruleset_view(actual) == canonical_ruleset_view(desired),
        "workflow_permissions_read": workflow.get("default_workflow_permissions") == "read",
        "actions_cannot_approve_reviews": workflow.get("can_approve_pull_request_reviews") is False,
        "main_rules_complete": EXPECTED_RULE_TYPES.issubset(rules),
        "main_sha_unchanged": current_main_sha == expected_main_sha,
    }
    return {
        "checks": checks,
        "active_rule_types": sorted(rules),
        "main_sha": current_main_sha,
        "verified": all(checks.values()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner", default="mosianekk-lang")
    parser.add_argument("--repo", default="Federation-Omega")
    parser.add_argument(
        "--ruleset",
        type=Path,
        default=Path("governance/federation_omega_main_airlock.ruleset.json"),
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--receipt", type=Path, default=Path("provider-airlock-activation-receipt.json")
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    desired = validate_ruleset(json.loads(args.ruleset.read_text(encoding="utf-8")))
    receipt: dict[str, Any] = {
        "schema": "FEDOMEGA-PROVIDER-AIRLOCK-ACTIVATION-1",
        "mode": "APPLY" if args.apply else "DRY_RUN",
        "repository": f"{args.owner}/{args.repo}",
        "ruleset_sha256": canonical_sha256(canonical_ruleset_view(desired)),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "credential_source_env": "GH_ADMIN_TOKEN",
        "credential_value_recorded": False,
        "main_mutation_attempted": False,
    }
    if not args.apply:
        receipt.update(
            {
                "status": "DRY_RUN_VERIFIED",
                "required_provider_operations": [
                    "authority_preflight",
                    "temporary_branch_negative_canary",
                    "create_or_update_main_ruleset",
                    "set_workflow_permissions_read_only",
                    "provider_readback",
                ],
            }
        )
        write_receipt(args.receipt, receipt)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0

    token = os.getenv("GH_ADMIN_TOKEN", "")
    if not token:
        raise SystemExit("GH_ADMIN_TOKEN is required with --apply; no mutation attempted.")
    api = GitHubAPI(token)
    try:
        authority = detect_authority(api, args.owner, args.repo)
        main_sha = ref_sha(api, args.owner, args.repo, "main")
        canary = run_negative_canary(api, args.owner, args.repo, main_sha, desired)
        ruleset_id, operation = create_or_update_main_ruleset(
            api, args.owner, args.repo, desired
        )
        api.request(
            "PUT",
            f"/repos/{args.owner}/{args.repo}/actions/permissions/workflow",
            {
                "default_workflow_permissions": "read",
                "can_approve_pull_request_reviews": False,
            },
        )
        readback = verify_provider_state(
            api, args.owner, args.repo, ruleset_id, desired, main_sha
        )
        if not readback["verified"]:
            raise ActivationError("provider readback failed")
        receipt.update(
            {
                "status": "VERIFIED",
                "authority": authority,
                "ruleset_id": ruleset_id,
                "ruleset_operation": operation,
                "negative_canary": canary,
                "provider_readback": readback,
            }
        )
        write_receipt(args.receipt, receipt)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        receipt.update({"status": "FAILED", "error_type": type(exc).__name__, "error": str(exc)[:1200]})
        write_receipt(args.receipt, receipt)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
