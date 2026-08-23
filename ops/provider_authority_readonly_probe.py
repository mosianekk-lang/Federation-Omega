#!/usr/bin/env python3
"""Read-only Google provider-authority probe.

The probe accepts only public identifiers and gcloud's ambient credential
context. It never accepts key-file JSON, bearer tokens, secret values or
provider-mutation instructions. Access-token stdout is discarded.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable, Iterable

SCHEMA = "FEDOMEGA-GOOGLE-PROVIDER-AUTHORITY-READONLY-PROBE-2"
CANONICAL_PROJECT_ID = "sov-hybrid-suite"
CANONICAL_PROJECT_NUMBER = "257649435135"
CANONICAL_WIF_POOL = "github-federation-omega"
CANONICAL_WIF_PROVIDER = "github"
CANONICAL_REGION = "africa-south1"

SERVICE_ACCOUNTS = (
    "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com",
    "fo-operator-sa@sov-hybrid-suite.iam.gserviceaccount.com",
    "afeme-sovereign-runtime-v4@sov-hybrid-suite.iam.gserviceaccount.com",
    "fo-automation-agent@sov-hybrid-suite.iam.gserviceaccount.com",
)
REQUIRED_APIS = (
    "serviceusage.googleapis.com",
    "script.googleapis.com",
    "secretmanager.googleapis.com",
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
)
CLOUD_RUN_SERVICES = (
    "architron9",
    "federation-omega-operator",
    "afeme-sovereign-control-plane-v4",
)
SECRET_METADATA_NAMES = (
    "fo-operator-admin-token",
    "archon-admin-plane-token",
)


class ProbeError(RuntimeError):
    """Fail-closed probe error."""


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""

    def public(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "exit_code": self.exit_code,
            "stdout": self.stdout[:12000],
            "stderr": self.stderr[:4000],
        }


Runner = Callable[[list[str], bool], CommandResult]


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def subprocess_runner(args: list[str], discard_stdout: bool = False) -> CommandResult:
    if not args or args[0] != "gcloud":
        raise ProbeError("only gcloud commands are permitted")
    if shutil.which("gcloud") is None:
        return CommandResult(False, 127, "", "gcloud unavailable")
    try:
        completed = subprocess.run(
            args,
            text=True,
            stdout=subprocess.DEVNULL if discard_stdout else subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=45,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - exercised in provider runtime
        return CommandResult(False, 126, "", f"{type(exc).__name__}: {exc}")
    return CommandResult(
        completed.returncode == 0,
        completed.returncode,
        "" if discard_stdout else (completed.stdout or "").strip(),
        (completed.stderr or "").strip(),
    )


def _gcloud(
    runner: Runner,
    args: Iterable[str],
    *,
    project_id: str,
) -> CommandResult:
    return runner(
        ["gcloud", *args, f"--project={project_id}"],
        False,
    )


def _json_or_empty(result: CommandResult) -> Any:
    if not result.ok or not result.stdout:
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def _read_collection(
    runner: Runner,
    commands: dict[str, list[str]],
    *,
    project_id: str,
) -> dict[str, dict[str, Any]]:
    return {
        key: _gcloud(runner, command, project_id=project_id).public()
        for key, command in commands.items()
    }


def build_probe_receipt(
    *,
    runner: Runner = subprocess_runner,
    project_id: str = CANONICAL_PROJECT_ID,
    expected_project_number: str = CANONICAL_PROJECT_NUMBER,
    region: str = CANONICAL_REGION,
    recorded_at: datetime | None = None,
) -> dict[str, Any]:
    if project_id != CANONICAL_PROJECT_ID:
        raise ProbeError("non-canonical project target rejected")
    if expected_project_number != CANONICAL_PROJECT_NUMBER:
        raise ProbeError("non-canonical project number rejected")
    if region != CANONICAL_REGION:
        raise ProbeError("non-canonical region rejected")

    account = runner(
        [
            "gcloud",
            "auth",
            "list",
            "--filter=status:ACTIVE",
            "--format=value(account)",
        ],
        False,
    )
    # Token material is intentionally discarded at process level.
    token_check = runner(
        ["gcloud", "auth", "print-access-token"],
        True,
    )
    provider_authenticated = bool(
        account.ok and account.stdout.strip() and token_check.ok
    )

    skipped = {
        "ok": False,
        "exit_code": None,
        "stdout": "",
        "stderr": "SKIPPED_NO_VALID_PROVIDER_AUTH",
    }

    if provider_authenticated:
        project_read = runner(
            [
                "gcloud",
                "projects",
                "describe",
                project_id,
                "--format=json(projectId,projectNumber,lifecycleState)",
            ],
            False,
        )
        canonical_wif = _gcloud(
            runner,
            [
                "iam",
                "workload-identity-pools",
                "providers",
                "describe",
                CANONICAL_WIF_PROVIDER,
                f"--workload-identity-pool={CANONICAL_WIF_POOL}",
                "--location=global",
                "--format=json(name,state,attributeCondition,attributeMapping)",
            ],
            project_id=project_id,
        )
        service_accounts = _read_collection(
            runner,
            {
                email: [
                    "iam",
                    "service-accounts",
                    "describe",
                    email,
                    "--format=json(email,disabled,oauth2ClientId)",
                ]
                for email in SERVICE_ACCOUNTS
            },
            project_id=project_id,
        )
        api_states = _read_collection(
            runner,
            {
                api: [
                    "services",
                    "describe",
                    api,
                    "--format=json(config.name,state)",
                ]
                for api in REQUIRED_APIS
            },
            project_id=project_id,
        )
        cloud_run = _read_collection(
            runner,
            {
                service: [
                    "run",
                    "services",
                    "describe",
                    service,
                    f"--region={region}",
                    "--format=json(metadata.name,status.url,status.latestReadyRevisionName,status.traffic,spec.template.spec.serviceAccountName)",
                ]
                for service in CLOUD_RUN_SERVICES
            },
            project_id=project_id,
        )
        secret_metadata = _read_collection(
            runner,
            {
                secret: [
                    "secrets",
                    "describe",
                    secret,
                    "--format=json(name,createTime,replication)",
                ]
                for secret in SECRET_METADATA_NAMES
            },
            project_id=project_id,
        )
    else:
        project_read = CommandResult(
            False,
            1,
            "",
            "SKIPPED_NO_VALID_PROVIDER_AUTH",
        )
        canonical_wif = CommandResult(
            False,
            1,
            "",
            "SKIPPED_NO_VALID_PROVIDER_AUTH",
        )
        service_accounts = {key: dict(skipped) for key in SERVICE_ACCOUNTS}
        api_states = {key: dict(skipped) for key in REQUIRED_APIS}
        cloud_run = {key: dict(skipped) for key in CLOUD_RUN_SERVICES}
        secret_metadata = {
            key: dict(skipped) for key in SECRET_METADATA_NAMES
        }

    project_object = _json_or_empty(project_read)
    actual_project_id = str(project_object.get("projectId") or "")
    actual_project_number = str(project_object.get("projectNumber") or "")
    canonical_identity_verified = all(
        (
            provider_authenticated,
            actual_project_id == project_id,
            actual_project_number == expected_project_number,
        )
    )

    classification = (
        "GOOGLE_PROVIDER_AUTH_VERIFIED_READ_ONLY"
        if canonical_identity_verified
        else "TRUSTED_PROVIDER_AUTHORITY_STILL_BLOCKED"
    )
    status = "VERIFIED" if canonical_identity_verified else "BLOCKED"

    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "recorded_at": (
            recorded_at or datetime.now(timezone.utc)
        ).isoformat(),
        "status": status,
        "classification": classification,
        "expected_project_id": project_id,
        "expected_project_number": expected_project_number,
        "actual_project_id": actual_project_id or None,
        "actual_project_number": actual_project_number or None,
        "provider_authenticated": provider_authenticated,
        "active_account": (
            account.stdout.strip() if provider_authenticated else None
        ),
        "access_token_check": {
            "ok": token_check.ok,
            "exit_code": token_check.exit_code,
            "stdout_discarded": True,
            "stderr": token_check.stderr[:1200],
        },
        "project_read": project_read.public(),
        "canonical_wif_read": canonical_wif.public(),
        "service_accounts": service_accounts,
        "api_states": api_states,
        "cloud_run_services": cloud_run,
        "secret_metadata": secret_metadata,
        "provider_mutation_attempted": False,
        "source_write_attempted": False,
        "secret_values_accessed": False,
        "credential_values_recorded": False,
        "truth_boundary": (
            "Read-only Google authority observation only. No IAM, API, "
            "deployment, traffic, secret-version, Apps Script, scheduler, "
            "Cloud Run or repository mutation is performed."
        ),
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def write_receipt(
    receipt: dict[str, Any],
    output: Path,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-id",
        default=CANONICAL_PROJECT_ID,
    )
    parser.add_argument(
        "--expected-project-number",
        default=CANONICAL_PROJECT_NUMBER,
    )
    parser.add_argument(
        "--region",
        default=CANONICAL_REGION,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    receipt = build_probe_receipt(
        project_id=args.project_id,
        expected_project_number=args.expected_project_number,
        region=args.region,
    )
    write_receipt(receipt, args.output)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "classification": receipt["classification"],
                "provider_authenticated": receipt["provider_authenticated"],
                "actual_project_number": receipt["actual_project_number"],
                "receipt_sha256": receipt["receipt_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if receipt["status"] == "VERIFIED" else 3


if __name__ == "__main__":
    raise SystemExit(main())
