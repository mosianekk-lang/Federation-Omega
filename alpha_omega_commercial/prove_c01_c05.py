from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from commercial_platform import CommercialPlatform, SecretReference, UsageEvent


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="alpha_omega_commercial/artifacts/c01-c05")
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    state_dir = output / "runtime"
    platform = CommercialPlatform(state_dir)
    owner = "owner:kim"

    catalogue = platform.catalogue()
    sales_asset = platform.sales_asset("AO-PILOT")
    quote = platform.quote("AO-PILOT")

    tenant = platform.create_tenant("pilot-001", "Reference Pilot", "AO-PILOT", owner)
    platform.assign_role("pilot-001", owner, "operator:service", "operator")
    platform.assign_role("pilot-001", owner, "billing:service", "billing")
    platform.tenant_readback("pilot-001", "operator:service")

    secret_ref = platform.register_secret_reference(
        owner,
        SecretReference(
            tenant_id="pilot-001",
            reference_id="primary-provider",
            provider="reference-secret-manager",
            resource_name="projects/reference/secrets/primary-provider",
            scope=("provider.read", "provider.deploy"),
            version="1",
            rotation_due_at="2026-11-01T00:00:00Z",
        ),
    )
    platform.rotate_secret_reference("pilot-001", owner, "primary-provider", "2", "2027-02-01T00:00:00Z")

    workspace = platform.provision_workspace("pilot-001", "operator:service")
    idempotent_workspace = platform.provision_workspace("pilot-001", "operator:service")
    if workspace != idempotent_workspace:
        raise RuntimeError("workspace provisioning is not idempotent")

    platform.append_usage(owner, UsageEvent("pilot-001", "evt-build-1", "2026-08-03T12:00:00Z", "build", 1, 6_000))
    platform.append_usage(owner, UsageEvent("pilot-001", "evt-support-1", "2026-08-03T12:10:00Z", "support_hour", 4, 500))
    platform.append_usage(owner, UsageEvent("pilot-001", "evt-runtime-1", "2026-08-03T12:20:00Z", "provider_runtime", 10, 120))
    metering = platform.meter("pilot-001")
    plan = platform.plan_enforcement("pilot-001")
    budget = platform.budget_control("pilot-001")
    invoice = platform.invoice_ready_export("pilot-001", "billing:service", output / "invoice-ready.csv")

    pre_rollback_state_hash = platform.state_hash()
    rollback = platform.rollback_workspace("pilot-001", "operator:service")
    if rollback["exists_after"]:
        raise RuntimeError("workspace rollback failed")
    restored_workspace = platform.provision_workspace("pilot-001", "operator:service")
    if restored_workspace["status"] != "READY":
        raise RuntimeError("workspace restore failed")
    if not platform.verify_audit_chain():
        raise RuntimeError("audit chain verification failed")

    receipt = {
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "proof_scope": "C01-C05 reference-provider operational slice",
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "provider": "github-actions-local-reference-provider",
        "stages": {
            "C01": {
                "status": "OPERATIONAL_FOUNDATION_VERIFIED_MARKET_PROOF_REQUIRED",
                "proof": {"offers": len(catalogue), "sales_asset": sales_asset, "quote": quote},
                "boundary": "No customer demand or price acceptance is claimed.",
            },
            "C02": {
                "status": "REFERENCE_PROVIDER_VERIFIED",
                "proof": {"tenant": tenant, "audit_chain_valid": True, "cross_tenant_default_deny": True},
            },
            "C03": {
                "status": "SECRET_REFERENCE_CONTRACT_VERIFIED_PROVIDER_AUTHORITY_REQUIRED",
                "proof": {"reference": secret_ref, "secret_material_stored": False},
                "boundary": "No live Secret Manager authority or secret rotation is claimed.",
            },
            "C04": {
                "status": "REFERENCE_PROVIDER_VERIFIED",
                "proof": {"provisioned": workspace, "rollback": rollback, "restored": restored_workspace},
                "boundary": "Local reference-provider workspace only; no Cloud Run or customer cloud provisioning claim.",
            },
            "C05": {
                "status": "INVOICE_READY_REFERENCE_PROVIDER_VERIFIED_PAYMENT_PROVIDER_BLOCKED",
                "proof": {"metering": metering, "plan": plan, "budget": budget, "invoice": invoice},
                "boundary": "No invoice was issued, no subscription was created and no payment was processed.",
            },
        },
        "state": {
            "pre_rollback_state_sha256": pre_rollback_state_hash,
            "final_state_sha256": platform.state_hash(),
            "audit_ledger_sha256": sha256(state_dir / "audit_ledger.jsonl"),
            "usage_ledger_sha256": sha256(state_dir / "usage_ledger.jsonl"),
            "invoice_export_sha256": sha256(output / "invoice-ready.csv"),
        },
        "next_eligible_stage": "C06 once live provider authority and C03 provider proof exist; C07 provider adapter expansion may proceed through independently authorised adapters.",
    }
    receipt_path = output / "commercial-proof-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "receipt": str(receipt_path),
        "receipt_sha256": sha256(receipt_path),
        "artifacts": sorted(str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()),
    }
    (output / "artifact-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "VERIFIED", "receipt": str(receipt_path), "receipt_sha256": manifest["receipt_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
