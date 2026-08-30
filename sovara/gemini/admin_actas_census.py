#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT = "sov-hybrid-suite"
PROJECT_NUMBER = "257649435135"
DEPLOYER_SA = f"superior-logic-deployer@{PROJECT}.iam.gserviceaccount.com"
ADMIN_ROLES = {
    "roles/owner",
    "roles/resourcemanager.projectIamAdmin",
    "roles/iam.securityAdmin",
}
ACT_AS_PERMISSION = "iam.serviceAccounts.actAs"
KNOWN_CONTROL_SERVICES = (
    ("architron9", "africa-south1"),
    ("federation-omega-operator", "us-central1"),
)


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def access_token() -> str:
    proc = run("gcloud", "auth", "print-access-token")
    return proc.stdout.strip() if proc.returncode == 0 else ""


def test_sa_permissions(token: str, service_account: str) -> tuple[int | None, list[str]]:
    resource = f"projects/{PROJECT}/serviceAccounts/{service_account}"
    url = f"https://iam.googleapis.com/v1/{resource}:testIamPermissions"
    body = json.dumps({"permissions": [ACT_AS_PERMISSION]}, separators=(",", ":")).encode()
    req = urllib.request.Request(
        url,
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
            return int(response.status), sorted(str(x) for x in (payload.get("permissions") or []))
    except urllib.error.HTTPError as exc:
        return int(exc.code), []
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, []


def runtime_identity(service: str, region: str) -> dict[str, object]:
    proc = run(
        "gcloud", "run", "services", "describe", service,
        "--project", PROJECT,
        "--region", region,
        "--platform", "managed",
        "--format=json",
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return {
            "service": service,
            "region": region,
            "readable": False,
            "service_account": "",
            "latest_ready_revision": "",
            "url": "",
        }
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "service": service,
            "region": region,
            "readable": False,
            "service_account": "",
            "latest_ready_revision": "",
            "url": "",
        }
    spec = data.get("spec") or {}
    template = spec.get("template") or {}
    template_spec = template.get("spec") or {}
    sa = (
        template_spec.get("serviceAccountName")
        or template.get("serviceAccount")
        or template.get("serviceAccountName")
        or ""
    )
    status = data.get("status") or {}
    return {
        "service": service,
        "region": region,
        "readable": True,
        "service_account": str(sa),
        "latest_ready_revision": str(status.get("latestReadyRevisionName") or ""),
        "url": str(status.get("url") or ""),
    }


def main() -> int:
    active = run("gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)")
    active_account = active.stdout.strip().splitlines()[0] if active.returncode == 0 and active.stdout.strip() else ""
    token = access_token()
    if active_account != DEPLOYER_SA or not token:
        raise SystemExit("canonical WIF deployer identity required")

    policy_proc = run("gcloud", "projects", "get-iam-policy", PROJECT, "--format=json")
    if policy_proc.returncode != 0:
        raise SystemExit("project IAM policy read failed")
    policy = json.loads(policy_proc.stdout)

    roles_by_sa: dict[str, set[str]] = {}
    for binding in policy.get("bindings") or []:
        if not isinstance(binding, dict):
            continue
        role = str(binding.get("role") or "")
        if role not in ADMIN_ROLES:
            continue
        for member in binding.get("members") or []:
            member = str(member)
            if member.startswith("serviceAccount:"):
                roles_by_sa.setdefault(member.split(":", 1)[1], set()).add(role)

    act_as_tests: dict[str, dict[str, object]] = {}
    for service_account in sorted(roles_by_sa):
        status, granted = test_sa_permissions(token, service_account)
        act_as_tests[service_account] = {
            "project_roles": sorted(roles_by_sa[service_account]),
            "test_http_status": status,
            "granted_permissions": granted,
            "deployer_can_act_as": ACT_AS_PERMISSION in granted,
        }

    control_services = [runtime_identity(service, region) for service, region in KNOWN_CONTROL_SERVICES]
    admin_runtime_matches = []
    for item in control_services:
        sa = str(item.get("service_account") or "")
        if sa and sa in roles_by_sa:
            admin_runtime_matches.append({
                **item,
                "project_roles": sorted(roles_by_sa[sa]),
                "deployer_can_act_as": bool(act_as_tests.get(sa, {}).get("deployer_can_act_as")),
            })

    reusable = sorted(
        service_account
        for service_account, result in act_as_tests.items()
        if result["deployer_can_act_as"]
    )
    receipt = {
        "schema": "SOVARA_ADMIN_ACTAS_CENSUS_V1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_id": PROJECT,
        "project_number": PROJECT_NUMBER,
        "active_account": active_account,
        "deployer_service_account": DEPLOYER_SA,
        "admin_service_account_count": len(roles_by_sa),
        "admin_act_as_tests": act_as_tests,
        "verified_admin_act_as_service_accounts": reusable,
        "known_control_services": control_services,
        "admin_control_runtime_matches": admin_runtime_matches,
        "automated_owner_worker_route_available": bool(reusable),
        "provider_mutation_performed": False,
        "credential_values_recorded": False,
        "secret_payload_accessed": False,
    }
    receipt["receipt_sha256"] = sha(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    out = Path(os.environ.get("SOVARA_RECEIPT_DIR", ".")) / "ADMIN_ACTAS_CENSUS.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "verified_admin_act_as_service_accounts": reusable,
        "admin_control_runtime_matches": admin_runtime_matches,
        "automated_owner_worker_route_available": receipt["automated_owner_worker_route_available"],
        "receipt_sha256": receipt["receipt_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
