#!/usr/bin/env python3
"""Read-only provider authority preflight for FEVX CSE.

This utility never mutates Google Cloud. It records only metadata, redacted error
messages, public operator health, and authenticated readback when an already-
authorised credential route exists.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ID = os.environ.get("PROJECT_ID", "sov-hybrid-suite")
PROJECT_NUMBER = os.environ.get("PROJECT_NUMBER", "257649435135")
REGION = os.environ.get("REGION", "africa-south1")
SERVICE = os.environ.get("SERVICE", "fevx-cse-shadow")
OPERATOR_URL = os.environ.get(
    "OPERATOR_URL",
    "https://federation-omega-operator-257649435135.africa-south1.run.app",
).rstrip("/")
DEPLOYER_SA = os.environ.get(
    "DEFAULT_DEPLOYER_SA",
    "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com",
)
RUNTIME_SA = os.environ.get(
    "RUNTIME_SA",
    "fo-automation-agent@sov-hybrid-suite.iam.gserviceaccount.com",
)
ARTIFACT_REPOSITORY = os.environ.get("ARTIFACT_REPOSITORY", "fo-runtime")
DATABASE_SECRET = os.environ.get("DATABASE_SECRET", "NEXUS_DATABASE_URL")
ARCHIVE_SHA256 = os.environ.get(
    "ARCHIVE_SHA256",
    "f4da04ac026628e022814f306acfe9e5303ee89a107359ab50a91fa04442ac50",
)
WHEEL_SHA256 = os.environ.get(
    "WHEEL_SHA256",
    "8c2832a9cd844af62a5fd403038bc2cebca4aa8967826295b34b6c9660c83022",
)
TOKEN = os.environ.get("OPERATOR_TOKEN", "")
OUTPUT = Path(
    os.environ.get(
        "OUTPUT_PATH",
        "deployments/fevx-cse/SCHEDULED_PROVIDER_PREFLIGHT_RECEIPT.json",
    )
)


def redact(value: Any) -> Any:
    sensitive = {
        "access_token",
        "refresh_token",
        "id_token",
        "authorization",
        "private_key",
        "client_secret",
        "secret_value",
        "credentials_json",
        "token",
    }
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if str(key).lower() in sensitive else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str) and TOKEN:
        return value.replace(TOKEN, "[REDACTED]")
    return value


def run(args: list[str]) -> dict[str, Any]:
    if shutil.which(args[0]) is None:
        return {
            "ok": False,
            "exit_code": 127,
            "stdout": "",
            "stderr": f"{args[0]} unavailable",
        }
    completed = subprocess.run(args, text=True, capture_output=True, check=False)
    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "stdout": completed.stdout.strip()[:10000],
        "stderr": completed.stderr.strip()[:3000],
    }


def gcloud(*args: str) -> dict[str, Any]:
    return run(["gcloud", *args, "--project", PROJECT_ID])


def call_operator(
    path: str,
    body: dict[str, Any] | None = None,
    authenticated: bool = False,
) -> dict[str, Any]:
    headers = {"accept": "application/json"}
    data = None
    if body is not None:
        headers["content-type"] = "application/json"
        data = json.dumps(body, separators=(",", ":")).encode()
    if authenticated and TOKEN:
        headers["x-fo-admin-token"] = TOKEN
    request = urllib.request.Request(
        OPERATOR_URL + path,
        data=data,
        headers=headers,
        method="POST" if body is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8", "replace")
            try:
                parsed: Any = json.loads(raw)
            except Exception:
                parsed = {"text": raw[:5000]}
            return {"http_status": response.status, "body": redact(parsed)}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"text": raw[:5000]}
        return {"http_status": exc.code, "body": redact(parsed)}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def load_pointer() -> tuple[dict[str, Any], str | None]:
    path = Path("deployments/fevx-cse/ARTIFACT_POINTER.json")
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}"


def main() -> int:
    pointer, pointer_error = load_pointer()
    public_health = call_operator("/health")
    public_contract = call_operator("/")
    authenticated_status = (
        call_operator(
            "/execute",
            {
                "action": "STATUS",
                "payload": {
                    "purpose": "FEVX CSE scheduled authority preflight",
                    "mutation": "NONE",
                },
            },
            authenticated=True,
        )
        if TOKEN
        else None
    )
    authenticated_baseline = (
        call_operator(
            "/execute",
            {
                "action": "READ_CLOUD_RUN_SERVICE",
                "payload": {
                    "project": PROJECT_ID,
                    "region": REGION,
                    "service": "architron9",
                    "purpose": "read-only baseline",
                },
            },
            authenticated=True,
        )
        if TOKEN
        else None
    )

    active_account = run(
        ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"]
    )
    project_read = gcloud(
        "projects",
        "describe",
        PROJECT_ID,
        "--format=json(projectId,projectNumber,lifecycleState)",
    )
    wif_read = gcloud(
        "iam",
        "workload-identity-pools",
        "providers",
        "describe",
        "github",
        "--workload-identity-pool",
        "github-federation-omega",
        "--location",
        "global",
        "--format=json(name,state,attributeCondition,attributeMapping)",
    )
    deployer_read = gcloud(
        "iam",
        "service-accounts",
        "describe",
        DEPLOYER_SA,
        "--format=json(email,disabled)",
    )
    runtime_read = gcloud(
        "iam",
        "service-accounts",
        "describe",
        RUNTIME_SA,
        "--format=json(email,disabled)",
    )
    repository_read = gcloud(
        "artifacts",
        "repositories",
        "describe",
        ARTIFACT_REPOSITORY,
        "--location",
        REGION,
        "--format=json(name,format,mode)",
    )
    database_secret_read = gcloud(
        "secrets",
        "describe",
        DATABASE_SECRET,
        "--format=json(name,replication)",
    )
    database_secret_version = gcloud(
        "secrets",
        "versions",
        "list",
        DATABASE_SECRET,
        "--filter=state=ENABLED",
        "--limit=1",
        "--format=value(name)",
    )
    target_read = gcloud(
        "run",
        "services",
        "describe",
        SERVICE,
        "--region",
        REGION,
        "--format=json(metadata.name,status.url,status.latestReadyRevisionName,status.traffic)",
    )

    try:
        wif_object = (
            json.loads(wif_read["stdout"])
            if wif_read["ok"] and wif_read["stdout"]
            else {}
        )
    except Exception:
        wif_object = {}

    checks = {
        "artifact_pointer": pointer_error is None,
        "archive_digest": (pointer.get("source_archive") or {}).get("sha256")
        == ARCHIVE_SHA256,
        "wheel_digest": (pointer.get("wheel") or {}).get("sha256")
        == WHEEL_SHA256,
        "operator_public_health": public_health.get("http_status") == 200
        and public_health.get("body", {}).get("ok") is True,
        "operator_contract": public_contract.get("http_status") == 200
        and "DEPLOY_SOLUTION5_LOCKED"
        in public_contract.get("body", {}).get("allowedActions", []),
        "active_gcloud_identity": active_account["ok"]
        and bool(active_account["stdout"]),
        "project_read": project_read["ok"],
        "project_number_match": project_read["ok"]
        and PROJECT_NUMBER in project_read["stdout"],
        "wif_provider_active": wif_read["ok"]
        and wif_object.get("state") == "ACTIVE",
        "deployer_service_account": deployer_read["ok"],
        "runtime_service_account": runtime_read["ok"],
        "artifact_repository": repository_read["ok"],
        "database_secret_metadata": database_secret_read["ok"],
        "database_secret_enabled_version": database_secret_version["ok"]
        and bool(database_secret_version["stdout"]),
        "operator_token_present": bool(TOKEN),
        "authenticated_status": authenticated_status is not None
        and authenticated_status.get("http_status") == 200
        and authenticated_status.get("body", {}).get("ok") is True,
        "authenticated_baseline": authenticated_baseline is not None
        and authenticated_baseline.get("http_status") == 200
        and authenticated_baseline.get("body", {}).get("ok") is True,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    receipt = {
        "receipt": "FEVX-CSE-SCHEDULED-PROVIDER-PREFLIGHT",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "classification": (
            "READY_FOR_PRIVATE_ZERO_TRAFFIC_SHADOW"
            if not blockers
            else "BLOCKED_PROVIDER_AUTHORITY_PREFLIGHT"
        ),
        "mutation_attempted": False,
        "secret_values_recorded": False,
        "auth_routes": {
            "service_account_key": os.environ.get("AUTH_KEY_OUTCOME", "skipped"),
            "repository_wif": os.environ.get("AUTH_REPO_WIF_OUTCOME", "skipped"),
            "canonical_wif": os.environ.get("AUTH_DEFAULT_WIF_OUTCOME", "skipped"),
            "setup_gcloud": os.environ.get("SETUP_GCLOUD_OUTCOME", "unknown"),
        },
        "checks": checks,
        "blockers": blockers,
        "artifact_pointer": pointer,
        "artifact_pointer_error": pointer_error,
        "active_account": active_account,
        "public_health": public_health,
        "public_contract": public_contract,
        "authenticated_status": authenticated_status,
        "authenticated_baseline": authenticated_baseline,
        "project_read": project_read,
        "wif_provider_read": wif_read,
        "deployer_service_account_read": deployer_read,
        "runtime_service_account_read": runtime_read,
        "artifact_repository_read": repository_read,
        "database_secret_read": database_secret_read,
        "database_secret_version_present": bool(database_secret_version["stdout"]),
        "target_service_read": target_read,
        "next_action": (
            "private zero-traffic shadow deployment"
            if not blockers
            else "repair only listed authority controls and repeat preflight"
        ),
        "external_effect": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(redact(receipt), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(redact(receipt), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
