from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from authority_refresh import AuthorityObservation, ProviderAuthorityFreshnessLedger, digest


def read_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--programme", required=True)
    parser.add_argument("--observations", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    programme = read_json(args.programme)
    bundle = read_json(args.observations)
    out = Path(args.output)
    if out.exists():
        shutil.rmtree(out)
    runtime = out / "authority-refresh-runtime"
    runtime.mkdir(parents=True)

    ledger = ProviderAuthorityFreshnessLedger(runtime, bundle["policies"])
    decisions = []
    for row in bundle["observations"]:
        item = dict(row)
        item["scope"] = tuple(item["scope"])
        decisions.append(ledger.admit(AuthorityObservation(**item), now=bundle["captured_at"]))

    projection = ledger.project(bundle["base_authority"], now=bundle["captured_at"])
    restarted = ProviderAuthorityFreshnessLedger(runtime, bundle["policies"])
    replay_projection = restarted.project(bundle["base_authority"], now=bundle["captured_at"])
    stale_projection = restarted.project(bundle["base_authority"], now="2026-08-12T20:01:49Z")

    declared = programme["provider_authority_freshness"]
    drive = projection["evidence"]["google_drive_document_release"]
    github = projection["evidence"]["github_actions"]
    gates = {
        "all_provider_native_observations_admitted": all(row["status"] == "ADMITTED" for row in decisions),
        "github_actions_fresh_verified": projection["states"]["github_actions"] == "FRESH_VERIFIED",
        "google_drive_release_fresh_verified": projection["states"]["google_drive_document_release"] == "FRESH_VERIFIED_READBACK",
        "latest_drive_release_readback": drive["evidence"]["file_id"] == "1dSKrl418Wjns8pbk3GzY-w4c6rnKmwvIokmWVtKvjGI",
        "latest_drive_content_hash_readback": drive["content_sha256"] == "923f8d582016e7a39e87d954fb6e776531b80771806f9c84b5e25f89e6cee956",
        "github_workflow_and_artifact_readback": github["evidence"]["workflow_run"] == 30844410098 and github["evidence"]["artifact_id"] == 8868069291,
        "blocked_domains_preserved": (
            projection["states"]["cloud_run"] == "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"
            and projection["states"]["payment_provider"] == "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"
            and projection["states"]["customer_market"] == "MARKET_PROOF_REQUIRED"
        ),
        "external_gates_unchanged": projection["external_gate_effect"] == "UNCHANGED" and not programme["external_gate_evidence"],
        "owner_authority_unchanged": projection["owner_authority_effect"] == "UNCHANGED",
        "ledger_integrity": projection["ledger_integrity"],
        "restart_readback": replay_projection["projection_sha256"] == projection["projection_sha256"],
        "freshness_expiry_enforced": (
            stale_projection["states"]["github_actions"] == "STALE_REVALIDATION_REQUIRED"
            and stale_projection["states"]["google_drive_document_release"] == "STALE_REVALIDATION_REQUIRED"
        ),
        "programme_status_updated": declared["status"] == "PROVIDER_AUTHORITY_FRESHNESS_RECONCILIATION_VERIFIED",
        "programme_evidence_matches": (
            declared["latest_verified"]["github_actions"]["observation_id"] == github["observation_id"]
            and declared["latest_verified"]["google_drive_document_release"]["observation_id"] == drive["observation_id"]
            and declared["latest_verified"]["google_drive_document_release"]["file_id"] == drive["evidence"]["file_id"]
        ),
    }

    receipt = {
        "programme_id": programme["programme_id"],
        "status": "PROVIDER_AUTHORITY_FRESHNESS_RECONCILIATION_VERIFIED" if all(gates.values()) else "PROVIDER_AUTHORITY_FRESHNESS_RECONCILIATION_FAILED",
        "proof_scope": "C03_C10_C12_C13_C15_PROVIDER_AUTHORITY_FRESHNESS",
        "captured_at": bundle["captured_at"],
        "gates": gates,
        "decisions": decisions,
        "projection": projection,
        "truth_boundary": (
            "This proof verifies fresh GitHub Actions and Google Drive document-release authority from provider-native readback, "
            "hash-linked persistence, expiry and exact blocked-provider preservation. It does not establish customer demand, "
            "a signed contract, payment, revenue, Cloud Run operation, enterprise attestation, partner adoption, an external "
            "case study or production-scale operation."
        ),
    }
    receipt["receipt_sha256"] = digest(receipt)

    out.mkdir(parents=True, exist_ok=True)
    (out / "provider-authority-freshness-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "provider-authority-projection.json").write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "provider-authority-observations.json").write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not all(gates.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
