#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ID = "sov-hybrid-suite"
REGION = "africa-south1"
SERVICE = "mosiane-live-thread"
SECRETS = (
    "openai-mosiane-live-thread-20260804",
    "openai-modisa-legal-v2-20260804",
)


def run(*args: str) -> tuple[int, str]:
    process = subprocess.run(args, text=True, capture_output=True)
    return process.returncode, process.stdout.strip()


def safe_secret_metadata(name: str) -> dict[str, Any]:
    code, output = run(
        "gcloud",
        "secrets",
        "describe",
        name,
        "--project",
        PROJECT_ID,
        "--format=json",
    )
    if code:
        return {"name": name, "found": False, "status": "NOT_FOUND_OR_DENIED"}
    obj = json.loads(output)
    return {
        "name": obj.get("name") or name,
        "found": True,
        "create_time": obj.get("createTime"),
        "labels": obj.get("labels") or {},
        "replication": obj.get("replication"),
        "payload_accessed": False,
        "status": "VERIFIED_METADATA",
    }


def main() -> int:
    output = Path(
        sys.argv[1] if len(sys.argv) > 1 else "provider-metadata-receipt.json"
    )
    account_code, account = run(
        "gcloud",
        "auth",
        "list",
        "--filter=status:ACTIVE",
        "--format=value(account)",
    )
    project_code, project_number = run(
        "gcloud",
        "projects",
        "describe",
        PROJECT_ID,
        "--format=value(projectNumber)",
    )
    run_code, run_output = run(
        "gcloud",
        "run",
        "services",
        "describe",
        SERVICE,
        "--project",
        PROJECT_ID,
        "--region",
        REGION,
        "--format=json",
    )
    revisions_code, revisions_output = run(
        "gcloud",
        "run",
        "revisions",
        "list",
        "--project",
        PROJECT_ID,
        "--region",
        REGION,
        "--service",
        SERVICE,
        "--format=json",
    )
    if not run_code:
        service = json.loads(run_output)
        status = service.get("status") or {}
        spec = service.get("spec") or {}
        template = spec.get("template") or {}
        template_spec = template.get("spec") or {}
        cloud_run = {
            "service": (service.get("metadata") or {}).get("name"),
            "url": status.get("url"),
            "latest_ready_revision": status.get("latestReadyRevisionName"),
            "runtime_service_account": template_spec.get("serviceAccountName"),
            "traffic": status.get("traffic") or [],
            "status": "VERIFIED_METADATA",
        }
    else:
        cloud_run = {"service": SERVICE, "status": "NOT_FOUND_OR_DENIED"}

    revisions: list[str | None] = []
    if not revisions_code:
        for item in json.loads(revisions_output):
            revisions.append((item.get("metadata") or {}).get("name"))

    receipt = {
        "schema": "FEDOMEGA-GCP-METADATA-PROBE-1",
        "active_account": account if not account_code else None,
        "project_id": PROJECT_ID,
        "project_number": project_number if not project_code else None,
        "secret_metadata": [safe_secret_metadata(name) for name in SECRETS],
        "cloud_run_metadata": cloud_run,
        "revision_names": revisions,
        "secret_payload_accessed": False,
        "raw_environment_recorded": False,
        "provider_mutation_performed": False,
        "credential_value_recorded": False,
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if account and project_number else 2


if __name__ == "__main__":
    raise SystemExit(main())
