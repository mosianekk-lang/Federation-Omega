from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from live_provider_expansion import LiveProviderExpansionFabric, ProviderObservation, digest, utc_now


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--provider-register", required=True)
    parser.add_argument("--cloud-observation", required=True)
    args = parser.parse_args()

    output = Path(args.output)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    now = utc_now()

    register = json.loads(Path(args.provider_register).read_text(encoding="utf-8"))
    cloud_payload = json.loads(Path(args.cloud_observation).read_text(encoding="utf-8"))
    cloud = ProviderObservation(
        observation_id=cloud_payload["observation_id"],
        provider=cloud_payload["provider"],
        provider_native=cloud_payload["provider_native"],
        scopes=tuple(cloud_payload["scopes"]),
        proofs=cloud_payload["proofs"],
        observed_at=cloud_payload["observed_at"],
        locator=cloud_payload["locator"],
        content_sha256=cloud_payload["content_sha256"],
        metadata=cloud_payload.get("metadata", {}),
    )

    fabric = LiveProviderExpansionFabric(output / "state")
    adapter_decisions = fabric.import_certification_register(register, now=now)
    cloud_decision = fabric.admit(cloud, now=now)
    projection = fabric.project(now=now)

    snapshot = fabric.snapshot("pre-rollback-drill")
    before = fabric.state_file.read_bytes()
    fabric.record_probe_marker("temporary-provider-proof-marker")
    mutation_observed = fabric.state_file.read_bytes() != before
    rollback = fabric.restore(snapshot)
    rollback_exact = fabric.state_file.read_bytes() == before
    reloaded = LiveProviderExpansionFabric(output / "state")
    replay_projection = reloaded.project(now=now)

    gates = {
        "six_reversible_adapters_admitted": len(adapter_decisions) == 6 and all(row["admitted"] for row in adapter_decisions),
        "cloud_run_provider_native_admitted": cloud_decision["admitted"],
        "execution_readback_health_persistence_rollback": all(cloud.proofs.get(name) for name in ("execution", "readback", "health", "persistence", "rollback", "private_invocation")),
        "seven_live_provider_operations": projection["live_provider_count"] == 7,
        "service_enabled_before_self_service": not projection["self_service_saas_claimed"],
        "send_payment_contract_revenue_boundaries_held": (
            projection["owner_reserved_effects"]["gmail_send"] == "HELD"
            and projection["owner_reserved_effects"]["outlook_send"] == "HELD"
            and projection["owner_reserved_effects"]["payment_provider"] == "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"
            and projection["verified_revenue_events"] == 0
        ),
        "external_market_gates_unchanged": not any(projection["external_maturity_gates"].values()),
        "ledger_integrity": fabric.verify_ledger() and reloaded.verify_ledger(),
        "restart_readback": replay_projection["provider_states"] == projection["provider_states"],
        "rollback_mutation_observed": mutation_observed,
        "rollback_exact": rollback_exact and rollback["status"] == "ROLLBACK_RESTORED",
    }
    status = "LIVE_PROVIDER_EXPANSION_VERIFIED_EXTERNAL_GATES_UNCHANGED" if all(gates.values()) else "LIVE_PROVIDER_EXPANSION_FAILED"
    receipt = {
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "proof_scope": "C03_C06_C07_C11_C14_C15_LIVE_PROVIDER_EXPANSION",
        "status": status,
        "verified_at": now,
        "gates": gates,
        "adapter_decisions": adapter_decisions,
        "cloud_run_decision": cloud_decision,
        "projection": projection,
        "rollback": rollback,
        "truth_boundary": {
            "bounded_live_cloud_operation_verified": cloud_decision["admitted"],
            "customer_demand_proven": False,
            "signed_contract_proven": False,
            "payment_or_revenue_proven": False,
            "subscription_or_invoice_proven": False,
            "enterprise_attestation_proven": False,
            "partner_adoption_proven": False,
            "external_case_study_proven": False,
            "production_scale_proven": False,
            "owner_reserved_authority_bypassed": False,
        },
    }
    receipt["receipt_sha256"] = digest(receipt)
    (output / "live-provider-expansion-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "live-provider-projection.json").write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "cloud-run-observation.json").write_text(json.dumps(cloud_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if status.endswith("FAILED"):
        raise SystemExit(status)


if __name__ == "__main__":
    main()
