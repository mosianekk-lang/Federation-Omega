#!/usr/bin/env python3
"""Idempotently apply and verify the Federation Omega GitHub Airlock ruleset.

Requires a fine-grained token with repository Administration: write. The token
is read from GH_ADMIN_TOKEN and is never printed or persisted.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.github.com"
DEFAULT_RULESET = Path(__file__).resolve().parents[1] / "governance" / "federation_omega_main_airlock.ruleset.json"


class GitHubAPI:
    def __init__(self, token: str, api_version: str):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": api_version,
            "User-Agent": "federation-omega-airlock-v2",
        }

    def request(self, method: str, path: str, payload: dict | None = None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            API + path, data=data, method=method, headers=self.headers
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API {method} {path} failed: {exc.code} {body[:1000]}") from exc


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default="mosianekk-lang/Federation-Omega")
    parser.add_argument("--ruleset", type=Path, default=DEFAULT_RULESET)
    parser.add_argument("--api-version", default="2022-11-28")
    parser.add_argument("--receipt", type=Path, default=Path("airlock-activation-receipt.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.getenv("GH_ADMIN_TOKEN", "")
    if not token:
        print("GH_ADMIN_TOKEN is required; no mutation attempted.", file=sys.stderr)
        return 2

    try:
        owner, repo = args.repository.split("/", 1)
    except ValueError:
        raise SystemExit("--repository must be owner/name")

    desired = json.loads(args.ruleset.read_text(encoding="utf-8"))
    api = GitHubAPI(token, args.api_version)

    _, existing = api.request("GET", f"/repos/{owner}/{repo}/rulesets?includes_parents=false")
    match = next((item for item in existing if item.get("name") == desired["name"]), None)
    if match:
        ruleset_id = int(match["id"])
        api.request("PUT", f"/repos/{owner}/{repo}/rulesets/{ruleset_id}", desired)
        operation = "UPDATED"
    else:
        _, created = api.request("POST", f"/repos/{owner}/{repo}/rulesets", desired)
        ruleset_id = int(created["id"])
        operation = "CREATED"

    api.request(
        "PUT",
        f"/repos/{owner}/{repo}/actions/permissions/workflow",
        {
            "default_workflow_permissions": "read",
            "can_approve_pull_request_reviews": False,
        },
    )

    _, ruleset_readback = api.request("GET", f"/repos/{owner}/{repo}/rulesets/{ruleset_id}")
    _, permission_readback = api.request("GET", f"/repos/{owner}/{repo}/actions/permissions/workflow")

    checks = {
        "ruleset_name": ruleset_readback.get("name") == desired["name"],
        "ruleset_active": ruleset_readback.get("enforcement") == "active",
        "target_branch": ruleset_readback.get("target") == "branch",
        "default_workflow_permissions_read": permission_readback.get("default_workflow_permissions") == "read",
        "workflow_review_approval_disabled": permission_readback.get("can_approve_pull_request_reviews") is False,
    }
    receipt = {
        "schema": "FEDOMEGA-GITHUB-AIRLOCK-ACTIVATION-2",
        "repository": args.repository,
        "ruleset_id": ruleset_id,
        "operation": operation,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "secret_values_recorded": False,
        "checks": checks,
        "status": "VERIFIED" if all(checks.values()) else "READBACK_FAILED",
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
