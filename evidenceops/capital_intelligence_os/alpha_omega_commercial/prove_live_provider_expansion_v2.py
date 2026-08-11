from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from live_provider_block import ProviderBlockEvidence, ProviderBlockLedger
from live_provider_expansion import LiveProviderExpansionFabric, ProviderObservation, digest, utc_now


def load_cloud_observation(path: Path) -> ProviderObservation:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ProviderObservation(
        observation_id=payload["observation_id"],
        provider=payload["provider"],
        provider_native=payload["provider_native"],
        scopes=tuple(payload["scopes"]),
        proofs=payload["proofs"],
        observed_at=payload["observed_at"],
        locator=payload["locator"],
        content_sha256=payload["content_sha256"],
        metadata=payload.get("metadata", {}),
    )


def load_cloud_block(path: Path) -> ProviderBlockEvidence:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ProviderBlockEvidence(
        block_id=payload["block_id"],
        provider=payload["provider"],
        reason=payload["reason"],
        provider_native=payload["provider_native"],
        observed_at=payload["observed_at"],
        locator=payload["locator"],
        attempted_scope=tuple(payload["attempted_scope"]),
        mutation_performed=payload["mutation_performed"],
        content_sha256=payload["content_sha256"],
        metadata=payload.get("metadata", {}),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--provider-register", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--cloud-observation")
    group.add_argument("--cloud-block")
    args = parser.parse_args()

    output = Path(args.output)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    now = utc_now()

    register = json.loads(Path(args.provider_register).read_text(encoding="utf-8"))
    fabric = LiveProviderExpansionFabric(output / "provider-state")
    adapter_decisions = fabric.import_certification_register(register, now=now)

    block_ledger = ProviderBlockLedger(output / "block-state")
    cloud_decision = None
    cloud_block_decision = None
    if args.cloud_observation:
        cloud_decision = fabric.admit(load_cloud_observation(Path(args.cloud_observation)), now=now)
    else:
        cloud_block_decision = block_ledger.record(load_cloud_block(Path(args.cloud_block)), now=now)

    base_projection = fabric.project(now=now)
    cloud_block_projection = block_ledger.latest("google_cloud_run", now=now)
    six_reversible = (
        len(adapter_decisions) == 6
        and all(row["admitted"] for row in adapter_decisions)
        and base_projection["live_provider_count"] >= 6
    )
    cloud_live = bool(cloud_decision and cloud_decision["admitted"])
    cloud_blocked_exactly = bool(
        cloud_block_decision
        and cloud_block_decision["admitted"]
        and cloud_block_projection
        and cloud_block_projection["fresh"]
        and cloud_block_projection["projected_state"]
        in {"PROVIDER_BLOCKED_WIF_TOKEN_EXCHANGE_FAILED", "PROVIDER_BLOCKED_WIF_INVALID_TARGET"}
        and not cloud_block_projection["mutation_performed"]
    )

    status = (
        "LIVE_PROVIDER_EXPANSION_VERIFIED_EXTERNAL_GATES_UNCHANGED"
        if six_reversible and cloud_live
        else "REVERSIBLE_PROVIDER_EXPANSION_VERIFIED_CLOUD_RUN_PROVIDER_BLOCKED"
        if six_reversible and cloud_blocked_exactly
        else "LIVE_PROVIDER_EXPANSION_FAILED"
    )

    snapshot = fabric.snapshot("pre-rollback-drill")
    before = fabric.state_file.read_bytes()
    fabric.record_probe_marker("temporary-provider-proof-marker")
    mutation_observed = fabric.state_file.read_bytes() != before
    rollback = fabric.restore(snapshot)
    rollback_exact = fabric.state_file.read_bytes() == before
    reloaded = LiveProviderExpansionFabric(output / "provider-state")
    replay_projection = reloaded.project(now=now)
    block_reloaded = ProviderBlockLedger(output / "block-state")

    provider_states = dict(base_projection["provider_states"])
    if cloud_blocked_exactly:
        provider_states["google_cloud_run"] = cloud_block_projection["projected_state"]

    stage_projection = {
        "C03": "LIVE_REVERSIBLE_PROVIDER_AUTHORITY_VERIFIED_CLOUD_RUN_WIF_BLOCK_RECORDED_OWNER_RESERVED_DOMAINS_HELD",
        "C06": (
            "LIVE_BOUNDED_OPERATION_HEALTH_PERSISTENCE_ROLLBACK_VERIFIED"
            if cloud_live
            else "REVERSIBLE_PROVIDER_OPERATIONS_VERIFIED_CLOUD_RUN_PROVIDER_BLOCKED"
        ),
        "C07": "SIX_LIVE_REVERSIBLE_PROVIDER_ADAPTERS_VERIFIED_EXTERNAL_PROVIDER_EXPANSION_OPEN",
        "C11": "SERVICE_ENABLED_REVERSIBLE_PROVIDER_OPERATIONS_VERIFIED_SELF_SERVICE_SEND_PAYMENT_AND_CLOUD_HELD",
        "C14": "REFERENCE_RELIABILITY_VERIFIED_CLOUD_RUN_AND_PRODUCTION_SCALE_PROOF_REQUIRED",
        "C15": "COMMERCIAL_READINESS_VERIFIED_REVERSIBLE_PROVIDER_EXPANSION_VERIFIED_EXTERNAL_MATURITY_GATES_OPEN",
    }

    gates = {
        "six_reversible_adapters_admitted": six_reversible,
        "cloud_authority_result_exact": cloud_live or cloud_blocked_exactly,
        "cloud_mutation_absent_when_blocked": not cloud_blocked_exactly or not cloud_block_projection["mutation_performed"],
        "provider_ledger_integrity": fabric.verify_ledger() and reloaded.verify_ledger(),
        "block_ledger_integrity": block_ledger.verify_ledger() and block_reloaded.verify_ledger(),
        "restart_readback": replay_projection["provider_states"] == base_projection["provider_states"],
        "rollback_mutation_observed": mutation_observed,
        "rollback_exact": rollback_exact and rollback["status"] == "ROLLBACK_RESTORED",
        "service_enabled_before_self_service": not base_projection["self_service_saas_claimed"],
        "send_payment_contract_revenue_boundaries_held": (
            base_projection["owner_reserved_effects"]["gmail_send"] == "HELD"
            and base_projection["owner_reserved_effects"]["outlook_send"] == "HELD"
            and base_projection["owner_reserved_effects"]["payment_provider"] == "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"
            and base_projection["verified_revenue_events"] == 0
        ),
        "external_market_gates_unchanged": not any(base_projection["external_maturity_gates"].values()),
    }

    receipt = {
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "proof_scope": "C03_C06_C07_C11_C14_C15_REVERSIBLE_PROVIDER_EXPANSION",
        "status": status,
        "verified_at": now,
        "gates": gates,
        "adapter_decisions": adapter_decisions,
        "cloud_run_decision": cloud_decision,
        "cloud_run_block_decision": cloud_block_decision,
        "cloud_run_block_projection": cloud_block_projection,
        "provider_states": provider_states,
        "stage_projection": stage_projection,
        "rollback": rollback,
        "truth_boundary": {
            "six_reversible_provider_operations_verified": six_reversible,
            "bounded_live_cloud_operation_verified": cloud_live,
            "cloud_run_provider_blocked": cloud_blocked_exactly,
            "cloud_mutation_performed_when_blocked": False,
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
    (output / "live-provider-expansion-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "provider-state-projection.json").write_text(
        json.dumps(provider_states, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if cloud_block_projection:
        (output / "cloud-run-provider-block.json").write_text(
            json.dumps(cloud_block_projection, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if status == "LIVE_PROVIDER_EXPANSION_FAILED" or not all(gates.values()):
        raise SystemExit("LIVE_PROVIDER_EXPANSION_FAILED")


if __name__ == "__main__":
    main()
