#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import urllib.error
import urllib.request
from collections import deque
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
MAX_GRAPH_DEPTH = 3


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def safe_member(member: str) -> dict[str, object]:
    kind, _, value = member.partition(":")
    if kind == "serviceAccount":
        return {"type": kind, "principal": value}
    if kind in {"principal", "principalSet"}:
        return {"type": kind, "principal_path": value}
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


def service_account_members(members: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({m.split(":", 1)[1] for m in members if m.startswith("serviceAccount:")}))


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


def impersonate(target: str, delegates: tuple[str, ...] = ()) -> tuple[bool, int | None, list[str]]:
    args = [
        "gcloud", "auth", "print-access-token",
        f"--impersonate-service-account={target}",
        "--lifetime=600",
    ]
    for delegate in delegates:
        args.append(f"--delegates={delegate}")
    proc = run(*args)
    token = proc.stdout.strip()
    if proc.returncode != 0 or not token:
        return False, None, []
    status, granted = test_permissions(token)
    return True, status, granted


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

    policies: dict[str, dict[str, object]] = {}
    graph: dict[str, set[str]] = {}
    q: deque[tuple[str, int]] = deque((principal, 0) for principal in service_roles)
    seen: set[str] = set()
    while q:
        principal, depth = q.popleft()
        if principal in seen or depth > MAX_GRAPH_DEPTH:
            continue
        seen.add(principal)
        p = load_sa_policy(principal)
        policies[principal] = p
        for delegator in service_account_members(role_members(p, TOKEN_CREATOR_ROLE)):
            graph.setdefault(delegator, set()).add(principal)
            if delegator not in seen:
                q.append((delegator, depth + 1))

    policies.setdefault(DEPLOYER_SA, deployer_policy)

    nodes: list[dict[str, object]] = []
    direct_wif_nodes: set[str] = set()
    for principal in sorted(policies):
        p = policies[principal]
        wif_members = role_members(p, WIF_ROLE)
        token_members = role_members(p, TOKEN_CREATOR_ROLE)
        exact_wif = sorted(set(canonical_wif_members) & set(wif_members))
        github_pool = [m for m in wif_members if "workloadIdentityPools/github-federation-omega" in m]
        if exact_wif:
            direct_wif_nodes.add(principal)
        nodes.append({
            "principal": principal,
            "project_roles": sorted(service_roles.get(principal, set())),
            "policy_readable": bool(p.get("readable")),
            "direct_current_wif_trust": bool(exact_wif),
            "exact_current_wif_member_match_count": len(exact_wif),
            "github_pool_wif_members": [safe_member(m) for m in github_pool],
            "token_creator_members": [safe_member(m) for m in token_members],
        })

    direct_tests: dict[str, dict[str, object]] = {}
    for principal in sorted(service_roles):
        ok, status, granted = impersonate(principal)
        direct_tests[principal] = {
            "impersonation_verified": ok,
            "test_iam_http_status": status,
            "granted_permissions": granted,
            "project_set_iam_policy": "resourcemanager.projects.setIamPolicy" in granted,
        }

    starts = {DEPLOYER_SA} | direct_wif_nodes
    delegation_tests: list[dict[str, object]] = []
    verified_paths: list[dict[str, object]] = []
    for start in sorted(starts):
        queue: deque[tuple[str, tuple[str, ...]]] = deque([(start, (start,))])
        visited_paths: set[tuple[str, ...]] = set()
        while queue:
            current, path = queue.popleft()
            if path in visited_paths or len(path) > MAX_GRAPH_DEPTH + 2:
                continue
            visited_paths.add(path)
            for target in sorted(graph.get(current, set())):
                new_path = path + (target,)
                if start == DEPLOYER_SA:
                    delegates = new_path[1:-1]
                    ok, status, granted = impersonate(target, delegates)
                    result = {
                        "start": start,
                        "target": target,
                        "delegates": list(delegates),
                        "path": list(new_path),
                        "impersonation_verified": ok,
                        "test_iam_http_status": status,
                        "granted_permissions": granted,
                        "project_set_iam_policy": "resourcemanager.projects.setIamPolicy" in granted,
                    }
                    delegation_tests.append(result)
                    if result["project_set_iam_policy"] and target in service_roles:
                        verified_paths.append(result)
                if target not in path:
                    queue.append((target, new_path))

    receipt = {
        "schema": "SOVARA_PROJECT_IAM_AUTHORITY_GRAPH_V1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_id": PROJECT,
        "project_number": PROJECT_NUMBER,
        "deployer_service_account": DEPLOYER_SA,
        "candidate_roles": sorted(CANDIDATE_ROLES),
        "candidate_binding_count": len(candidates),
        "admin_service_account_count": len(service_roles),
        "candidates": candidates,
        "canonical_deployer_wif_policy_readable": bool(deployer_policy.get("readable")),
        "canonical_deployer_wif_members": [safe_member(m) for m in canonical_wif_members],
        "authority_nodes": nodes,
        "token_creator_edges": [
            {"from": source, "to": target}
            for source in sorted(graph)
            for target in sorted(graph[source])
        ],
        "direct_impersonation_tests": direct_tests,
        "direct_current_wif_admin_candidates": sorted(direct_wif_nodes & set(service_roles)),
        "delegation_tests": delegation_tests,
        "verified_admin_delegation_paths": verified_paths,
        "verified_reusable_admin_service_accounts": sorted({
            principal for principal, result in direct_tests.items()
            if result["project_set_iam_policy"]
        } | {str(x["target"]) for x in verified_paths}),
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
        "candidate_binding_count": receipt["candidate_binding_count"],
        "admin_service_account_count": receipt["admin_service_account_count"],
        "direct_current_wif_admin_candidates": receipt["direct_current_wif_admin_candidates"],
        "verified_admin_delegation_paths": receipt["verified_admin_delegation_paths"],
        "verified_reusable_admin_service_accounts": receipt["verified_reusable_admin_service_accounts"],
        "receipt_sha256": receipt["receipt_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
