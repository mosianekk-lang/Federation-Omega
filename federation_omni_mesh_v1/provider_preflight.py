from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import argparse
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Sequence


WIF_PROVIDER_RE = re.compile(
    r"^projects/(?P<project_number>[0-9]+)/locations/global/"
    r"workloadIdentityPools/(?P<pool>[A-Za-z0-9._-]+)/"
    r"providers/(?P<provider>[A-Za-z0-9._-]+)$"
)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str

    def json_value(self) -> Any:
        if not self.stdout:
            return None
        try:
            return json.loads(self.stdout)
        except json.JSONDecodeError:
            return self.stdout


Runner = Callable[[Sequence[str]], CommandResult]


def subprocess_runner(
    args: Sequence[str],
    *,
    timeout_seconds: int = 60,
) -> CommandResult:
    completed = subprocess.run(
        list(args),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    return CommandResult(
        ok=completed.returncode == 0,
        exit_code=completed.returncode,
        stdout=completed.stdout.strip()[:20000],
        stderr=completed.stderr.strip()[:5000],
    )


def parse_wif_provider(resource: str) -> dict[str, str]:
    match = WIF_PROVIDER_RE.fullmatch(resource)
    if match is None:
        raise ValueError("invalid full WIF provider resource")
    return match.groupdict()


def _gcloud(
    runner: Runner,
    *args: str,
    project_id: str | None = None,
) -> CommandResult:
    command = ["gcloud", *args]
    if project_id is not None:
        command.extend(["--project", project_id])
    return runner(command)


def build_identity_receipt(
    *,
    project_id: str,
    expected_project_number: str,
    wif_provider: str,
    deployer_service_account: str,
    required_apis: Sequence[str],
    runner: Runner = subprocess_runner,
) -> dict[str, Any]:
    """Build a read-only Google identity receipt.

    The function never reads secret values and never mutates Google Cloud or
    the source repository. The caller owns placement of the resulting receipt
    in an immutable private evidence store.
    """

    if not project_id or not expected_project_number.isdigit():
        raise ValueError("project_id and numeric expected_project_number required")
    if "@" not in deployer_service_account:
        raise ValueError("deployer_service_account must be an email")
    provider_parts = parse_wif_provider(wif_provider)
    if provider_parts["project_number"] != expected_project_number:
        raise ValueError("WIF provider project number does not match expectation")

    active_account = _gcloud(
        runner,
        "auth",
        "list",
        "--filter=status:ACTIVE",
        "--format=json(account)",
    )
    project = _gcloud(
        runner,
        "projects",
        "describe",
        project_id,
        "--format=json(projectId,projectNumber,lifecycleState)",
        project_id=project_id,
    )
    provider = _gcloud(
        runner,
        "iam",
        "workload-identity-pools",
        "providers",
        "describe",
        provider_parts["provider"],
        f"--workload-identity-pool={provider_parts['pool']}",
        "--location=global",
        "--format=json(name,state,attributeMapping,attributeCondition)",
        project_id=project_id,
    )
    service_account = _gcloud(
        runner,
        "iam",
        "service-accounts",
        "describe",
        deployer_service_account,
        "--format=json(email,disabled,oauth2ClientId)",
        project_id=project_id,
    )
    service_account_policy = _gcloud(
        runner,
        "iam",
        "service-accounts",
        "get-iam-policy",
        deployer_service_account,
        "--format=json(bindings.role,bindings.members,etag,version)",
        project_id=project_id,
    )
    project_roles = _gcloud(
        runner,
        "projects",
        "get-iam-policy",
        project_id,
        "--flatten=bindings[].members",
        f"--filter=bindings.members:serviceAccount:{deployer_service_account}",
        "--format=json(bindings.role,bindings.members)",
        project_id=project_id,
    )
    enabled_apis = _gcloud(
        runner,
        "services",
        "list",
        "--enabled",
        "--format=json(config.name,state)",
        project_id=project_id,
    )

    project_value = project.json_value()
    observed_project_number = ""
    observed_project_id = ""
    if isinstance(project_value, dict):
        observed_project_number = str(project_value.get("projectNumber", ""))
        observed_project_id = str(project_value.get("projectId", ""))

    api_value = enabled_apis.json_value()
    enabled_api_names: set[str] = set()
    if isinstance(api_value, list):
        for item in api_value:
            if isinstance(item, dict):
                name = item.get("config", {}).get("name")
                if isinstance(name, str):
                    enabled_api_names.add(name)

    checks = {
        "active_account_readable": active_account.ok,
        "project_readable": project.ok,
        "project_id_match": observed_project_id == project_id,
        "project_number_match": (
            observed_project_number == expected_project_number
        ),
        "wif_provider_readable": provider.ok,
        "deployer_service_account_readable": service_account.ok,
        "service_account_policy_readable": service_account_policy.ok,
        "project_roles_readable": project_roles.ok,
        "enabled_apis_readable": enabled_apis.ok,
        "required_apis_enabled": all(
            api in enabled_api_names for api in required_apis
        ),
    }
    classification = (
        "PROVIDER_IDENTITY_PREFLIGHT_VERIFIED"
        if all(checks.values())
        else "PROVIDER_IDENTITY_PREFLIGHT_PARTIAL"
    )
    receipt: dict[str, Any] = {
        "receipt_type": "FEDERATION_OMNI_MESH_PROVIDER_IDENTITY_PREFLIGHT_V1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "mutation_attempted": False,
        "secret_values_read": False,
        "source_repository_mutated": False,
        "target": {
            "project_id": project_id,
            "expected_project_number": expected_project_number,
            "wif_provider": wif_provider,
            "deployer_service_account": deployer_service_account,
            "required_apis": list(required_apis),
        },
        "observations": {
            "active_account": active_account.__dict__,
            "project": project.__dict__,
            "wif_provider": provider.__dict__,
            "deployer_service_account": service_account.__dict__,
            "service_account_policy": service_account_policy.__dict__,
            "project_roles": project_roles.__dict__,
            "enabled_apis": enabled_apis.__dict__,
        },
        "checks": checks,
        "classification": classification,
    }
    receipt["receipt_sha256"] = sha256(
        _canonical_json(receipt).encode("utf-8")
    ).hexdigest()
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only provider identity preflight for Omni-Mesh"
    )
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--expected-project-number", required=True)
    parser.add_argument("--wif-provider", required=True)
    parser.add_argument("--deployer-service-account", required=True)
    parser.add_argument(
        "--required-api",
        action="append",
        default=[],
        dest="required_apis",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    receipt = build_identity_receipt(
        project_id=args.project_id,
        expected_project_number=args.expected_project_number,
        wif_provider=args.wif_provider,
        deployer_service_account=args.deployer_service_account,
        required_apis=args.required_apis,
    )
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return (
        0
        if receipt["classification"]
        == "PROVIDER_IDENTITY_PREFLIGHT_VERIFIED"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
