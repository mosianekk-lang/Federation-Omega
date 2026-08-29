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
DEPLOYER_SA = f"superior-logic-deployer@{PROJECT}.iam.gserviceaccount.com"
CANDIDATE_ROLES = {
    "roles/owner",
    "roles/resourcemanager.projectIamAdmin",
    "roles/iam.securityAdmin",
}
TEST_PERMISSIONS = [
    "resourcemanager.projects.getIamPolicy",
    "resourcemanager.projects.setIamPolicy",
]
WIF_ROLE = "roles/iam.workloadIdentityUser"
TOKEN_CREATOR_ROLE = "roles/iam.serviceAccountTokenCreator"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def safe_member(member: str) -> dict[str, object]:
    kind, _, value = member.partition(":")
    if kind == "serviceAccount":
        return {"type": kind, "principal": value}
    return {"type": kind or "unknown", "principal_sha256": digest(value or member)}


def load_sa_policy(principal: str) -> dict[str, object]:
    proc = run(
        "gcloud", "iam", "service-accounts", "get-iam-policy", principal,
        "--project", PROJECT, "--format=json",
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return {"readable": False, "bindings": []}
    try:
        policy = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"readable": False, "bindings": []}
    return {"readable": True, "bindings": policy.get("bindings") or []}


def role_members(policy: dict[str, object], role: str) -> tuple[str, ...]:
    members: set[str] = set()
    for binding in policy.get("bindings") or []:
        if isinstance(binding, dict) and binding.get("role") == role:
            members.update(str(x) for x in (binding.get("members") or []))
    return tuple(sorted(members))


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
    service_roles: dict[str, set[str]] = {}
    for binding in policy.get("bindings", []):
        role = str(binding.get("role", ""))
        if role not in CANDIDATE_ROLES:
            continue
        for member in binding.get("members") or []:
            member = str(member)
            entry = {"role": role, **safe_member(member)}
            candidates.append(entry)
            if entry.get("type") == "serviceAccount" and entry.get("principal"):
                service_roles.setdefault(str(entry["principal"]), set()).add(role)

    deployer_policy = load_sa_policy(DEPLOYER_SA)
    canonical_wif_members = role_members(deployer_policy, WIF_ROLE)
    canonical_wif_hashes = [digest(x) for x in canonical_wif_members]

    qualified: list[dict[str, object]] = []
    direct_wif_candidates: list[str] = []
    for principal in sorted(service_roles):
        candidate_policy = load_sa_policy(principal)
        candidate_wif_members = role_members(candidate_policy, WIF_ROLE)
        candidate_token_creator_members = role_members(candidate_policy, TOKEN_CREATOR_ROLE)
        exact_wif_intersection = sorted(set(canonical_wif_members) & set(candidate_wif_members))
        github_pool_wif_members = [
            member for member in candidate_wif_members
            if "workloadIdentityPools/github-federation-omega" in member
        ]
        direct_wif_trust = bool(exact_wif_intersection)
        if direct_wif_trust:
            direct_wif_candidates.append(principal)

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
                "project_roles": sorted(service_roles[principal]),
                "service_account_policy_readable": bool(candidate_policy.get("readable")),
                "direct_current_wif_trust": direct_wif_trust,
                "exact_current_wif_member_match_count": len(exact_wif_intersection),
                "github_pool_wif_binding_count": len(github_pool_wif_members),
                "candidate_wif_member_sha256": [digest(x) for x in candidate_wif_members],
                "token_creator_binding_count": len(candidate_token_creator_members),
                "impersonation_from_deployer_verified": impersonation_ok,
                "test_iam_http_status": status,
                "granted_permissions": granted,
                "project_set_iam_policy": "resourcemanager.projects.setIamPolicy" in granted,
            }
        )

    receipt = {
        "schema": "SOVARA_PROJECT_IAM_AUTHORITY_CENSUS_V2",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_id": PROJECT,
        "project_number": PROJECT_NUMBER,
        "deployer_service_account": DEPLOYER_SA,
        "candidate_roles": sorted(CANDIDATE_ROLES),
        "candidate_count": len(candidates),
        "unique_service_account_candidate_count": len(service_roles),
        "candidates": candidates,
        "canonical_deployer_wif_policy_readable": bool(deployer_policy.get("readable")),
        "canonical_deployer_wif_member_count": len(canonical_wif_members),
        "canonical_deployer_wif_member_sha256": canonical_wif_hashes,
        "service_account_qualification": qualified,
        "verified_reusable_admin_service_accounts": [
            x["principal"] for x in qualified if x["project_set_iam_policy"]
        ],
        "direct_current_wif_admin_candidates": sorted(direct_wif_candidates),
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
        "unique_service_account_candidate_count": receipt["unique_service_account_candidate_count"],
        "verified_reusable_admin_service_accounts": receipt["verified_reusable_admin_service_accounts"],
        "direct_current_wif_admin_candidates": receipt["direct_current_wif_admin_candidates"],
        "receipt_sha256": receipt["receipt_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
