from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping


HANDOFF_SCHEMA = "BUBBLES-COMMAND-RECEIPT-V1"
PROVIDER_RECEIPT_SCHEMA = "BUBBLES-PROVIDER-READBACK-V1"
REPOSITORY = "mosianekk-lang/Federation-Omega"
OWNER = "mosianekk-lang"
GOOGLE_PROJECT = "sov-hybrid-suite"
GOOGLE_PROJECT_NUMBER = "257649435135"
GOOGLE_REGION = "africa-south1"
GOOGLE_SERVICE = "architron9"
GOOGLE_PROVIDER = (
    "projects/257649435135/locations/global/workloadIdentityPools/"
    "github-federation-omega/providers/github"
)
GOOGLE_DEPLOYER = "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com"


class ProviderWorkerError(ValueError):
    pass


def load_json(path: str | Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProviderWorkerError(f"Expected JSON object in {path}")
    return value


def validate_handoff(event: Mapping[str, object], handoff: Mapping[str, object]) -> dict[str, object]:
    workflow_run = event.get("workflow_run")
    if not isinstance(workflow_run, Mapping):
        raise ProviderWorkerError("workflow_run event payload is required")

    if workflow_run.get("name") != "Bubbles Command Bus":
        raise ProviderWorkerError("Origin workflow is not Bubbles Command Bus")
    if workflow_run.get("conclusion") != "success":
        raise ProviderWorkerError("Origin Bubbles workflow did not conclude success")
    if workflow_run.get("event") != "pull_request":
        raise ProviderWorkerError("Provider handoff requires a pull_request-origin command")

    actor = workflow_run.get("actor")
    if not isinstance(actor, Mapping) or actor.get("login") != OWNER:
        raise ProviderWorkerError("Origin workflow actor is not the Bubbles owner")

    head_repository = workflow_run.get("head_repository")
    if not isinstance(head_repository, Mapping) or head_repository.get("full_name") != REPOSITORY:
        raise ProviderWorkerError("Origin head repository is not the canonical Federation repository")

    if handoff.get("schema") != HANDOFF_SCHEMA:
        raise ProviderWorkerError("Unsupported Bubbles handoff schema")
    if handoff.get("state") != "PROVIDER_PENDING":
        raise ProviderWorkerError("Bubbles handoff is not provider-pending")
    if handoff.get("actor") != OWNER:
        raise ProviderWorkerError("Handoff actor does not match owner")
    if handoff.get("event_name") != "pull_request":
        raise ProviderWorkerError("Handoff event is not pull_request")

    command_sha = handoff.get("command_sha256")
    if not isinstance(command_sha, str) or len(command_sha) != 64:
        raise ProviderWorkerError("Handoff command SHA-256 is missing or malformed")

    request = handoff.get("request")
    if not isinstance(request, Mapping):
        raise ProviderWorkerError("Handoff request object is missing")
    expected = {
        "adapter_id": "google_cloud_wif_plan",
        "action": "plan_wif",
        "effect": "READ",
        "target_alias": "GOOGLE_CLOUD_EXECUTION_PLANE",
    }
    for key, value in expected.items():
        if request.get(key) != value:
            raise ProviderWorkerError(f"Handoff request mismatch for {key}")

    return {
        "state": "VALIDATED",
        "command_sha256": command_sha,
        "origin_run_id": workflow_run.get("id"),
        "origin_head_sha": workflow_run.get("head_sha"),
        "origin_actor": OWNER,
        "origin_repository": REPOSITORY,
        "provider_operation": "GOOGLE_CLOUD_WIF_PLAN_READ_ONLY",
    }


def build_provider_receipt(
    *,
    validation: Mapping[str, object],
    auth_outcome: str,
    setup_outcome: str,
    plan_outcome: str,
    plan_payload: Mapping[str, object] | None,
    provider_run_id: str,
    provider_ref: str,
) -> dict[str, object]:
    base: dict[str, object] = {
        "schema": PROVIDER_RECEIPT_SCHEMA,
        "command_sha256": validation.get("command_sha256"),
        "origin_run_id": validation.get("origin_run_id"),
        "origin_head_sha": validation.get("origin_head_sha"),
        "provider_run_id": provider_run_id,
        "provider_ref": provider_ref,
        "provider": "Google Cloud",
        "operation": "WIF_PLAN_READ_ONLY",
        "project": GOOGLE_PROJECT,
        "project_number_expected": GOOGLE_PROJECT_NUMBER,
        "region": GOOGLE_REGION,
        "service": GOOGLE_SERVICE,
        "workload_identity_provider": GOOGLE_PROVIDER,
        "deployer_service_account": GOOGLE_DEPLOYER,
        "auth_outcome": auth_outcome,
        "setup_gcloud_outcome": setup_outcome,
        "plan_outcome": plan_outcome,
        "mutation_performed": False,
    }

    if auth_outcome != "success":
        return {
            **base,
            "state": "CONSTRAINT",
            "reason": "Google OIDC/WIF authentication did not succeed.",
            "provider_identity_verified": False,
            "provider_inventory_readback": False,
            "truth_boundary": "No Google mutation was requested or performed.",
        }

    if setup_outcome != "success" or plan_outcome != "success" or not plan_payload:
        return {
            **base,
            "state": "CONSTRAINT",
            "reason": "Google authentication succeeded but the read-only WIF plan did not complete.",
            "provider_identity_verified": True,
            "provider_inventory_readback": False,
            "truth_boundary": "Authentication proof is narrower than provider inventory proof; no mutation was performed.",
        }

    if plan_payload.get("receipt") != "FEDOMEGA-WIF-PLAN":
        raise ProviderWorkerError("Unexpected WIF plan receipt type")
    if plan_payload.get("mutation_performed") is not False:
        raise ProviderWorkerError("Read-only provider worker observed a mutation flag")
    if plan_payload.get("project") != GOOGLE_PROJECT:
        raise ProviderWorkerError("WIF plan project mismatch")
    if str(plan_payload.get("project_number_observed", "")) != GOOGLE_PROJECT_NUMBER:
        raise ProviderWorkerError("WIF plan project-number mismatch")
    if plan_payload.get("region") != GOOGLE_REGION or plan_payload.get("service") != GOOGLE_SERVICE:
        raise ProviderWorkerError("WIF plan target mismatch")
    if plan_payload.get("workload_identity_provider") != GOOGLE_PROVIDER:
        raise ProviderWorkerError("WIF provider resource mismatch")
    if plan_payload.get("deployer_service_account") != GOOGLE_DEPLOYER:
        raise ProviderWorkerError("WIF deployer identity mismatch")

    active_account = str(plan_payload.get("active_account", ""))
    if not active_account:
        raise ProviderWorkerError("WIF plan did not read back an active Google account")

    missing_controls = plan_payload.get("missing_controls", [])
    if not isinstance(missing_controls, list):
        raise ProviderWorkerError("WIF plan missing_controls is malformed")

    return {
        **base,
        "state": "SUCCESS",
        "provider_identity_verified": True,
        "provider_inventory_readback": True,
        "active_account": active_account,
        "wif_plan_state": plan_payload.get("state"),
        "missing_controls": missing_controls,
        "missing_apis": plan_payload.get("missing_apis", []),
        "provider_state": plan_payload.get("provider_state"),
        "pool_state": plan_payload.get("pool_state"),
        "service_exists": plan_payload.get("service_exists"),
        "artifact_repository_exists": plan_payload.get("artifact_repository_exists"),
        "truth_boundary": (
            "SUCCESS proves short-lived Google authentication plus read-only provider inventory readback for the exact "
            "configured project/WIF route. It does not prove deployment authority, write readiness, a successful "
            "provider mutation, or production cutover."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Bubbles provider handoffs and synthesize readback receipts.")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("--event", required=True)
    validate.add_argument("--handoff", required=True)
    validate.add_argument("--output", required=True)

    synthesize = sub.add_parser("synthesize")
    synthesize.add_argument("--validation", required=True)
    synthesize.add_argument("--plan")
    synthesize.add_argument("--auth-outcome", required=True)
    synthesize.add_argument("--setup-outcome", required=True)
    synthesize.add_argument("--plan-outcome", required=True)
    synthesize.add_argument("--provider-run-id", required=True)
    synthesize.add_argument("--provider-ref", required=True)
    synthesize.add_argument("--output", required=True)

    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if args.command == "validate":
        result = validate_handoff(load_json(args.event), load_json(args.handoff))
    else:
        plan = load_json(args.plan) if args.plan and Path(args.plan).exists() else None
        result = build_provider_receipt(
            validation=load_json(args.validation),
            auth_outcome=args.auth_outcome,
            setup_outcome=args.setup_outcome,
            plan_outcome=args.plan_outcome,
            plan_payload=plan,
            provider_run_id=args.provider_run_id,
            provider_ref=args.provider_ref,
        )

    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
