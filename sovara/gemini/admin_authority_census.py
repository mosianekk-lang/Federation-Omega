#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT = "sov-hybrid-suite"
PROJECT_NUMBER = "257649435135"
CANDIDATE_ROLES = {
    "roles/owner",
    "roles/resourcemanager.projectIamAdmin",
    "roles/iam.securityAdmin",
}
TEST_PERMISSIONS = [
    "resourcemanager.projects.getIamPolicy",
    "resourcemanager.projects.setIamPolicy",
]


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def safe_member(member: str) -> dict[str, object]:
    kind, _, value = member.partition(":")
    if kind == "serviceAccount":
        return {"type": kind, "principal": value}
    return {"type": kind or "unknown", "principal_sha256": digest(value or member)}


def test_permissions(token: str) -> tuple[int, list[str]]:
    body = json.dumps({"permissions": TEST_PERMISSIONS}, separators=(",", ":")).encode()
    req = urllib.request.Request(
        f"https://cloudresourcemanager.googleapis.com/v1/projects/{PROJECT}:testIamPermissions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Goog-User-Project": PROJECT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode() or "{}")
            return response.status, sorted(payload.get("permissions") or [])
    except urllib.error.HTTPError as exc:
        return exc.code, []


def main() -> int:
    policy_proc = run("gcloud", "projects", "get-iam-policy", PROJECT, "--format=json")
    if policy_proc.returncode != 0:
        raise SystemExit("project IAM policy read failed")
    policy = json.loads(policy_proc.stdout)

    candidates: list[dict[str, object]] = []
    for binding in policy.get("bindings", []):
        role = str(binding.get("role", ""))
        if role not in CANDIDATE_ROLES:
            continue
        for member in binding.get("members") or []:
            entry = {"role": role, **safe_member(str(member))}
            candidates.append(entry)

    service_candidates = [
        c for c in candidates if c.get("type") == "serviceAccount" and c.get("principal")
    ]
    qualified: list[dict[str, object]] = []
    for candidate in service_candidates:
        principal = str(candidate["principal"])
        token_proc = run(
            "gcloud",
            "auth",
            "print-access-token",
            f"--impersonate-service-account={principal}",
            "--lifetime=600",
        )
        impersonation_ok = token_proc.returncode == 0 and bool(token_proc.stdout.strip())
        granted: list[str] = []
        status = None
        if impersonation_ok:
            status, granted = test_permissions(token_proc.stdout.strip())
        qualified.append(
            {
                "principal": principal,
                "role": candidate["role"],
                "impersonation_verified": impersonation_ok,
                "test_iam_http_status": status,
                "granted_permissions": granted,
                "project_set_iam_policy": "resourcemanager.projects.setIamPolicy" in granted,
            }
        )

    receipt = {
        "schema": "SOVARA_PROJECT_IAM_AUTHORITY_CENSUS_V1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_id": PROJECT,
        "project_number": PROJECT_NUMBER,
        "candidate_roles": sorted(CANDIDATE_ROLES),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "service_account_qualification": qualified,
        "verified_reusable_admin_service_accounts": [
            x["principal"] for x in qualified if x["project_set_iam_policy"]
        ],
        "provider_mutation_performed": False,
        "credential_values_recorded": False,
        "secret_payload_accessed": False,
    }
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    receipt["receipt_sha256"] = digest(canonical)
    out = Path(__import__("os").environ.get("SOVARA_RECEIPT_DIR", ".")) / "PROJECT_IAM_AUTHORITY_CENSUS.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidate_count": receipt["candidate_count"],
        "verified_reusable_admin_service_accounts": receipt["verified_reusable_admin_service_accounts"],
        "receipt_sha256": receipt["receipt_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
