from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from external_evidence import EvidenceEnvelope, ExternalEvidenceAdmissionController, digest


PROOF_NOW = "2026-08-04T00:05:00Z"


def sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def execute(output: Path) -> dict:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    authority = {
        "github_actions": {
            "state": "FRESH_VERIFIED",
            "scope": ["source_read", "ci_execution", "artifact_upload"],
            "evidence": "provider-native pull-request workflows",
        },
        "google_drive_document_release": {
            "state": "FRESH_VERIFIED_READBACK",
            "scope": ["document_release_readback"],
            "file_id": "1UYV6hyyR68v_WPSfZIEP7mzMGJ07-XKKTyAJsSTW2-c",
            "modified_at": "2026-08-03T23:18:35.544Z",
        },
        "google_drive_binary_artifact_transfer": {
            "state": "PROVIDER_BLOCKED_FILE_EGRESS",
            "scope": ["binary_artifact_transfer"],
        },
        "customer_market": {"state": "MARKET_PROOF_REQUIRED"},
        "payment_provider": {"state": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"},
        "cloud_run": {"state": "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE"},
        "external_attestation": {"state": "UNVERIFIED"},
        "partner_market": {"state": "MARKET_PROOF_REQUIRED"},
        "live_cloud_operations": {"state": "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE"},
        "owner_decision": {"state": "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED"},
    }

    runtime = output / "external-evidence-runtime"
    controller = ExternalEvidenceAdmissionController(runtime, authority)

    candidates = [
        EvidenceEnvelope(
            evidence_id="mock-demand-001",
            gate="customer_demand",
            provider="github-actions-reference",
            locator="artifact://commercial/mock-demand-001",
            observed_at="2026-08-03T23:40:00Z",
            content_sha256=sha("mock-demand-001"),
            evidence_class="MOCK_CONFORMANCE",
            claims={"customer_identity_verified": True, "price_accepted": True},
        ),
        EvidenceEnvelope(
            evidence_id="blocked-payment-001",
            gate="payment_provider_revenue",
            provider="payment-provider",
            locator="provider://payment/blocked-payment-001",
            observed_at="2026-08-03T23:40:00Z",
            content_sha256=sha("blocked-payment-001"),
            evidence_class="EXTERNAL_PROVIDER_NATIVE",
            claims={"settled": True, "currency": "ZAR", "amount": 1000.0},
            owner_confirmed=True,
        ),
        EvidenceEnvelope(
            evidence_id="blocked-cloud-001",
            gate="live_cloud_provider",
            provider="cloud-run",
            locator="provider://cloud-run/blocked-cloud-001",
            observed_at="2026-08-03T23:40:00Z",
            content_sha256=sha("blocked-cloud-001"),
            evidence_class="EXTERNAL_PROVIDER_NATIVE",
            claims={
                "deployment_id": "blocked-revision",
                "readback": True,
                "health": True,
                "persistence": True,
                "rollback": True,
            },
        ),
        EvidenceEnvelope(
            evidence_id="internal-case-study-001",
            gate="external_case_study",
            provider="github-actions-reference",
            locator="artifact://commercial/internal-case-study-001",
            observed_at="2026-08-03T23:40:00Z",
            content_sha256=sha("internal-case-study-001"),
            evidence_class="REFERENCE_PROVIDER",
            claims={
                "customer_consent": True,
                "externally_observed": True,
                "outcome_evidence_complete": True,
            },
            owner_confirmed=True,
        ),
    ]
    decisions = [controller.admit(candidate, now=PROOF_NOW) for candidate in candidates]
    projection = controller.project_maturity()
    authority_readback = controller.authority_readback()

    gates = {
        "all_unverified_candidates_rejected": all(item["status"] == "REJECTED" for item in decisions),
        "synthetic_evidence_rejected": "NON_EXTERNAL_OR_SYNTHETIC_EVIDENCE" in decisions[0]["reasons"],
        "payment_provider_authority_enforced": (
            "PROVIDER_AUTHORITY_NOT_VERIFIED:payment_provider" in decisions[1]["reasons"]
        ),
        "boolean_owner_confirmation_rejected": (
            "BOOLEAN_OWNER_CONFIRMATION_NOT_ACCEPTED" in decisions[1]["reasons"]
        ),
        "owner_decision_receipt_required": (
            "OWNER_DECISION_RECEIPT_REQUIRED" in decisions[1]["reasons"]
        ),
        "cloud_provider_authority_enforced": (
            "PROVIDER_AUTHORITY_NOT_VERIFIED:cloud_run" in decisions[2]["reasons"]
        ),
        "external_case_study_origin_enforced": (
            "NON_EXTERNAL_OR_SYNTHETIC_EVIDENCE" in decisions[3]["reasons"]
        ),
        "external_case_study_owner_receipt_required": (
            "OWNER_DECISION_RECEIPT_REQUIRED" in decisions[3]["reasons"]
        ),
        "external_maturity_gates_unchanged": not any(projection["external_gates"].values()),
        "full_commercial_maturity_not_claimed": not projection["full_commercial_maturity"],
        "ledger_integrity": controller.verify_ledger() and projection["ledger_integrity"],
        "state_persistence": (runtime / "external-evidence-state.json").is_file(),
        "owner_receipt_consumption_empty": projection["consumed_owner_receipts"] == {},
        "drive_release_scope_exact": (
            authority["google_drive_document_release"]["state"] == "FRESH_VERIFIED_READBACK"
            and authority["google_drive_binary_artifact_transfer"]["state"] == "PROVIDER_BLOCKED_FILE_EGRESS"
        ),
        "cloud_payment_and_owner_decision_remain_blocked": (
            authority["cloud_run"]["state"] == "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE"
            and authority["payment_provider"]["state"] == "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"
            and authority["owner_decision"]["state"] == "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED"
        ),
    }

    receipt = {
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "proof_scope": "C12_C13_C15_EXTERNAL_EVIDENCE_AND_OWNER_AUTHORITY_RECEIPTS",
        "status": (
            "OWNER_AUTHORITY_RECEIPT_CONTROL_VERIFIED_GATES_UNCHANGED"
            if all(gates.values())
            else "OWNER_AUTHORITY_RECEIPT_CONTROL_FAILED"
        ),
        "verified_at": PROOF_NOW,
        "gates": gates,
        "decisions": decisions,
        "projection": projection,
        "provider_authority": authority,
        "authority_readback": authority_readback,
        "owner_reserved_authority": [
            "financial commitments",
            "contracts",
            "external communications",
            "consequential releases",
            "revenue recognition confirmation",
        ],
        "truth_boundary": (
            "This proof verifies fail-closed external-evidence admission and rejects caller-set owner "
            "confirmation booleans. Owner-reserved gates require a fresh provider-backed, hash-valid, "
            "evidence-bound owner decision receipt. No owner decision, customer demand, contract, payment, "
            "revenue, subscription, Cloud Run operation, enterprise attestation, partner adoption, external "
            "case study or production-scale operation is established."
        ),
    }
    receipt["receipt_sha256"] = digest(receipt)

    write_json(output / "external-evidence-admission-receipt.json", receipt)
    write_json(output / "commercial-provider-authority.json", authority)
    write_json(output / "external-maturity-projection.json", projection)
    if not all(gates.values()):
        raise SystemExit(1)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
