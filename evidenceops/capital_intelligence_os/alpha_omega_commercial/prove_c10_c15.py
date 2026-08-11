from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from commercial_assurance import CommercialAssuranceControlPlane, EvidenceReference


def evidence(reference_id: str, evidence_class: str = "REFERENCE_PROVIDER") -> EvidenceReference:
    return EvidenceReference(
        reference_id=reference_id,
        provider="github-actions-reference",
        locator=f"artifact://alpha-omega-commercial/{reference_id}",
        sha256=hashlib.sha256(f"{reference_id}:{evidence_class}".encode()).hexdigest(),
        observed_at="2026-08-03T13:30:00Z",
        evidence_class=evidence_class,
    )


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def execute(output: Path) -> dict:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    state_dir = output / "reference-state"
    plane = CommercialAssuranceControlPlane(state_dir)

    # C10: evidence-bound controls, retention, privacy completion and DR drill.
    for family in ("ACCESS", "AUDIT", "PRIVACY", "RETENTION", "RECOVERY"):
        plane.register_control(
            f"AO-{family}-001",
            family,
            f"Alpha Omega reference {family.lower()} control",
            "commercial-service-owner",
            [evidence(f"c10-{family.lower()}")],
        )
    plane.set_retention_policy("AO-RETENTION-001", "operational-metadata", 365, "ARCHIVE")
    plane.open_privacy_request("AO-PRIVACY-001", "reference-tenant", "subject-reference-001", "ACCESS")
    plane.complete_privacy_request("AO-PRIVACY-001", [evidence("c10-privacy-fulfilment")], "FULFILLED")
    dr = plane.run_disaster_recovery_drill(
        "AO-DR-001",
        {"tenant": "reference-tenant", "revision": 1, "objects": 12},
        {"tenant": "reference-tenant", "revision": 1, "objects": 12},
        recovery_seconds=12.0,
        rto_target_seconds=30.0,
    )
    assurance = plane.assurance_pack()

    # C11: service-enabled request execution, exact readback and rollback.
    service_target = state_dir / "reference-service-object.json"
    plane.submit_service_request(
        "AO-SERVICE-001",
        "reference-tenant",
        "workspace.provision",
        {"workspace_id": "reference-workspace-001", "mode": "service-enabled"},
        "reference-operator",
    )

    def handler(payload: dict) -> dict:
        write_json(service_target, payload)
        readback = json.loads(service_target.read_text(encoding="utf-8"))
        return {
            "target": str(service_target),
            "payload_sha256": hashlib.sha256(service_target.read_bytes()).hexdigest(),
            "readback_pass": readback == payload,
            "health_pass": service_target.is_file(),
        }

    def rollback(execution: dict) -> dict:
        service_target.unlink(missing_ok=True)
        return {"target": execution["target"], "rollback_pass": not service_target.exists()}

    service = plane.execute_reference_service_request("AO-SERVICE-001", handler, rollback)
    owner_reserved = plane.submit_service_request(
        "AO-SUBSCRIPTION-001",
        "reference-tenant",
        "subscription.change",
        {"requested_offer": "AO-DEPARTMENT"},
        "reference-operator",
    )

    # C12: evidence framework, deliberately using internal reference evidence.
    study = plane.register_outcome_study(
        "AO-STUDY-001",
        "reference-tenant",
        "process_cycle_time",
        baseline=100.0,
        outcome=58.0,
        unit="minutes",
        lower_is_better=True,
        evidence=[evidence("c12-reference-study")],
        evidence_origin="REFERENCE_PROVIDER_SYNTHETIC",
    )
    case_report = plane.case_study_report("AO-STUDY-001")

    # C13: internal funnel and quote controls only; no external send or commitment.
    plane.create_lead("AO-LEAD-001", "reference-organisation", "internal-reference", "manual process delay")
    plane.advance_lead("AO-LEAD-001", "QUALIFIED", "artifact://c13-reference-qualification")
    quote = plane.create_quote_draft("AO-QUOTE-001", "AO-LEAD-001", "AO-PILOT", "ZAR", 560000.0, 12)
    revenue_dashboard = plane.revenue_operations_dashboard()

    # C14: deterministic reference load, recovery and unit-economics evidence.
    scale = plane.run_scale_evaluation(
        "AO-SCALE-001",
        "service.request.submit",
        latencies_ms=[28, 31, 33, 36, 38, 41, 43, 46, 49, 52, 55, 58, 61, 65, 70, 74, 80, 88, 96, 110],
        request_count=2000,
        failure_count=3,
        concurrency=40,
        recovery_seconds=16.0,
        monthly_revenue_zar=75000.0,
        monthly_delivery_cost_zar=28000.0,
        support_hours=24.0,
        targets={
            "max_p95_latency_ms": 110.0,
            "max_error_rate": 0.005,
            "max_recovery_seconds": 30.0,
            "min_gross_margin": 0.55,
            "max_support_hours": 30.0,
        },
    )

    # C15: portable succession package and exact completion boundary.
    succession = plane.export_succession_package(
        "AO-COMMERCIAL-C10-C15-001",
        {
            "restore": "Verify package hash, restore state, verify ledger chain and rerun proof.",
            "incident": "Fail closed, preserve evidence, classify the provider boundary and use rollback.",
            "commercial_release": "Require owner approval for commitments, contracts, communications and consequential releases.",
        },
        {
            "financial_commitments": "OWNER_RESERVED",
            "contracts": "OWNER_RESERVED",
            "external_communications": "OWNER_RESERVED",
            "consequential_releases": "OWNER_RESERVED",
            "cloud_provider_mutation": "FRESH_PROVIDER_AUTHORITY_REQUIRED",
            "payment_recognition": "PAYMENT_PROVIDER_RECEIPT_AND_OWNER_CONFIRMATION_REQUIRED",
        },
    )
    maturity = plane.maturity_snapshot()
    ledger = plane.verify_ledger()

    receipt = {
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "proof_scope": "C10-C15_REFERENCE_SERVICE_PLATFORM",
        "provider": "github-actions-reference",
        "stages": {
            "C10": {"status": assurance["status"], "proof": assurance, "dr": dr},
            "C11": {"status": service["status"], "proof": service, "owner_reserved": owner_reserved["status"]},
            "C12": {"status": study["status"], "proof": case_report},
            "C13": {
                "status": "REFERENCE_REVOPS_VERIFIED_ZERO_REVENUE",
                "quote_status": quote["status"],
                "proof": revenue_dashboard,
            },
            "C14": {"status": scale["status"], "proof": scale},
            "C15": {"status": maturity["canonical_status"], "proof": succession, "maturity": maturity},
        },
        "ledger": ledger,
        "truth_boundaries": {
            "customer_demand": "NOT_PROVEN",
            "revenue": "ZERO_VERIFIED_EVENTS",
            "subscriptions": "NO_PAYMENT_OR_SUBSCRIPTION_PROVIDER",
            "invoices": "NO_INVOICE_ISSUED",
            "enterprise_assurance": "REFERENCE_CONTROLS_ONLY_EXTERNAL_ATTESTATION_REQUIRED",
            "partner_adoption": "NOT_PROVEN",
            "cloud_run": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
            "external_case_study": "MARKET_PROOF_REQUIRED",
            "service_platform": "REFERENCE_HANDLER_EXECUTION_VERIFIED_AND_ROLLED_BACK",
        },
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    write_json(output / "commercial-c10-c15-receipt.json", receipt)
    write_json(output / "commercial-maturity.json", maturity)
    write_json(output / "revenue-operations-dashboard.json", revenue_dashboard)
    write_json(output / "external-gates.json", maturity["external_gates"])
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = execute(args.output)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
