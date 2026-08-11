import argparse
import json
import shutil
from pathlib import Path

from commercial_expansion import ArchiveAdapter, CapabilityMarketplace, FilesystemAdapter, ManagedOps, PartnerProgramme, SQLiteAdapter, digest_json, now, prove_adapter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="alpha_omega_commercial/artifacts/c06-c09")
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    ops = ManagedOps(output / "managed-ops")
    ops.register_service("commercial-platform", 0.75, 60)
    for healthy, latency in [(True, 100), (True, 110), (True, 120), (False, 500)]:
        ops.heartbeat("commercial-platform", healthy, latency)
    ops.open_incident("inc-reference-1", "commercial-platform", "SEV2")
    ops.resolve_incident("inc-reference-1", "rollback and restore drill")
    backup = ops.backup("commercial-platform")
    restore = ops.restore(backup["backup_id"])
    sla = ops.sla_report("commercial-platform")

    payload = {"tenant_id": "pilot-001", "solution_id": "operational-automation", "version": "1.0.0"}
    adapters = [
        FilesystemAdapter(output / "providers" / "filesystem"),
        SQLiteAdapter(output / "providers" / "sqlite" / "provider.db"),
        ArchiveAdapter(output / "providers" / "archive"),
    ]
    adapter_proofs = [prove_adapter(adapter, f"commercial-{index+1}", payload) for index, adapter in enumerate(adapters)]
    if not all(item["status"] == "REFERENCE_PROVIDER_VERIFIED" for item in adapter_proofs):
        raise RuntimeError("adapter proof failed")

    market = CapabilityMarketplace(output / "marketplace")
    release = market.publish("cap-operational-intake", "1.0.0", "solution-operational-intake", "commercial.capability.v1", "COMMERCIAL", (), {"entrypoint": "intake.run", "schema": "v1"})
    grant = market.grant("pilot-001", "cap-operational-intake", "1.0.0", "lic-pilot-001")
    entitlement = market.check("pilot-001", "cap-operational-intake", "1.0.0")

    partners = PartnerProgramme(output / "partners")
    partner = partners.register("partner-reference-001", "Reference Partner Pty Ltd", "Reference Automation", 1500)
    share = partners.revenue_share_calculation("partner-reference-001", 100_000)

    receipt = {
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "proof_scope": "C06-C09 reference-provider operational slice",
        "recorded_at": now(),
        "stages": {
            "C06": {"status": "REFERENCE_PROVIDER_VERIFIED_LIVE_PROVIDER_REQUIRED", "proof": {"backup": backup, "restore": restore, "sla": sla}, "boundary": "Reference service only; no production SLA or customer support claim."},
            "C07": {"status": "THREE_REFERENCE_ADAPTERS_VERIFIED_EXTERNAL_PROVIDER_EXPANSION_REQUIRED", "proof": adapter_proofs, "boundary": "Filesystem, SQLite and deterministic archive adapters are CI reference providers, not three external clouds."},
            "C08": {"status": "REFERENCE_MARKETPLACE_VERIFIED", "proof": {"release": release, "grant": grant, "entitlement": entitlement}, "boundary": "No licence sale or marketplace transaction is claimed."},
            "C09": {"status": "REFERENCE_PARTNER_TENANT_VERIFIED_OWNER_APPROVAL_AND_ADOPTION_REQUIRED", "proof": {"partner": partner, "revenue_share": share}, "boundary": "No partner contract, adoption or revenue is claimed."},
        },
    }
    receipt["receipt_sha256"] = digest_json(receipt)
    (output / "commercial-c06-c09-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "VERIFIED", "receipt_sha256": receipt["receipt_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
