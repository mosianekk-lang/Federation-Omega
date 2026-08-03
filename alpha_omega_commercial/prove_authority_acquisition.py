from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict
from pathlib import Path

from authority_acquisition import (
    AuthorityAcquisitionFabric,
    AuthorityEvidence,
    AuthorityRequirement,
    contains_secret_material,
    digest,
)


def load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--programme", required=True)
    parser.add_argument("--requirements", required=True)
    parser.add_argument("--observations", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    programme = load_json(args.programme)
    config = load_json(args.requirements)
    observations = load_json(args.observations)
    out = Path(args.output)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    runtime = out / "authority-acquisition-runtime"
    fabric = AuthorityAcquisitionFabric(runtime)
    requirements: list[AuthorityRequirement] = []
    for row in config["requirements"]:
        requirement = AuthorityRequirement(
            domain=row["domain"],
            stage=row["stage"],
            provider=row["provider"],
            purpose=row["purpose"],
            required_scopes=tuple(row["required_scopes"]),
            required_proofs=tuple(row["required_proofs"]),
            max_age_seconds=int(row["max_age_seconds"]),
            owner_reserved_actions=tuple(row.get("owner_reserved_actions", [])),
            depends_on=tuple(row.get("depends_on", [])),
        )
        fabric.register_requirement(requirement)
        requirements.append(requirement)

    stage_numbers = [int(requirement.stage[1:]) for requirement in requirements]
    strict_stage_order = stage_numbers == sorted(stage_numbers)
    base_authority = programme["external_evidence_admission"]["provider_authority"]
    handoffs = {
        domain: fabric.build_handoff(
            domain,
            base_authority.get(domain, "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"),
        )
        for domain in fabric.requirements
    }

    by_domain = {row["domain"]: row for row in observations["observations"]}
    admitted = {}
    for domain in ("github_actions", "google_drive_document_release"):
        observation = by_domain[domain]
        requirement = fabric.requirements[domain]
        proof_map = {name: True for name in requirement.required_proofs}
        evidence = AuthorityEvidence(
            evidence_id=f"acquisition-{observation['observation_id']}",
            domain=domain,
            provider=observation["provider"],
            provider_native=bool(observation["provider_native"]),
            state=observation["state"],
            locator=observation["locator"],
            observed_at=observation["observed_at"],
            captured_at=observations["captured_at"],
            scopes=tuple(observation["scope"]),
            proofs=proof_map,
            content_sha256=observation["content_sha256"],
            owner_confirmations=(),
            evidence=observation["evidence"],
        )
        admitted[domain] = fabric.admit_authority(evidence, now=observations["captured_at"])

    conformance = {}
    for requirement in requirements:
        if requirement.domain in admitted:
            continue
        conformance[requirement.domain] = fabric.record_conformance(
            requirement.domain,
            provider="github-actions-reference",
            provider_native=True,
            scopes=requirement.required_scopes,
            proofs={name: True for name in requirement.required_proofs},
        )

    payment_requirement = fabric.requirements["payment_provider"]
    blocked_payment = fabric.admit_authority(
        AuthorityEvidence(
            evidence_id="blocked-payment-authority-attempt",
            domain="payment_provider",
            provider="payment-provider",
            provider_native=True,
            state="FRESH_AUTHORITY_VERIFIED",
            locator="provider://payment/authority-attempt",
            observed_at=observations["captured_at"],
            captured_at=observations["captured_at"],
            scopes=payment_requirement.required_scopes,
            proofs={name: True for name in payment_requirement.required_proofs},
            content_sha256="f" * 64,
            owner_confirmations=(),
            evidence={"mode": "contract-conformance-only", "settled_payment": False},
        ),
        now=observations["captured_at"],
    )

    projection = fabric.project(base_authority, now=observations["captured_at"])
    reloaded = AuthorityAcquisitionFabric(runtime)
    reloaded.requirements = fabric.requirements
    second_projection = reloaded.project(base_authority, now=observations["captured_at"])
    restart_readback = projection == second_projection and reloaded.verify_ledger()

    snapshot = out / "rollback-snapshot"
    shutil.copytree(runtime, snapshot)
    target = runtime / "handoffs" / "cloud_run.json"
    original_hash = digest(json.loads(target.read_text(encoding="utf-8")))
    target.write_text(json.dumps({"corrupted": True}) + "\n", encoding="utf-8")
    shutil.rmtree(runtime)
    shutil.copytree(snapshot, runtime)
    restored_hash = digest(
        json.loads((runtime / "handoffs" / "cloud_run.json").read_text(encoding="utf-8"))
    )
    rollback_verified = original_hash == restored_hash

    manifest = {
        "programme_id": programme["programme_id"],
        "proof_scope": "C03_C05_C07_C09_C10_C11_C12_C13_C14_C15_AUTHORITY_ACQUISITION",
        "requirements": [asdict(requirement) for requirement in requirements],
        "handoffs": {domain: handoff["handoff_sha256"] for domain, handoff in handoffs.items()},
        "owner_reserved_authority": programme["owner_reserved_authority"],
        "truth_boundary": (
            "This package prepares exact provider authority handoffs and proves conformance on authorised GitHub Actions "
            "and Google Drive document-readback surfaces. It does not grant Cloud Run, payment, customer, partner, "
            "attestation, binary transfer, live operations or production-scale authority."
        ),
    }
    manifest["manifest_sha256"] = digest(manifest)
    (out / "provider-authority-acquisition-handoff.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out / "provider-authority-acquisition-projection.json").write_text(
        json.dumps(projection, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    blocked_expected = {
        "google_drive_binary_artifact_transfer",
        "cloud_run",
        "payment_provider",
        "customer_market",
        "partner_market",
        "external_attestation",
        "live_cloud_operations",
        "production_scale",
    }
    gates = {
        "strict_stage_order": strict_stage_order,
        "all_requirements_packaged": set(handoffs) == set(fabric.requirements),
        "handoffs_hash_bound": all(
            handoff["handoff_sha256"]
            == digest({key: value for key, value in handoff.items() if key != "handoff_sha256"})
            for handoff in handoffs.values()
        ),
        "no_secret_material": not contains_secret_material(manifest)
        and not any(contains_secret_material(handoff) for handoff in handoffs.values()),
        "authorised_provider_evidence_admitted": all(row["admitted"] for row in admitted.values()),
        "alternate_provider_conformance_verified": all(row["contract_pass"] for row in conformance.values()),
        "alternate_conformance_does_not_grant_authority": all(
            not row["authority_granted"] for row in conformance.values()
        ),
        "blocked_payment_owner_gate_enforced": not blocked_payment["admitted"]
        and any(reason.startswith("OWNER_CONFIRMATION_REQUIRED") for reason in blocked_payment["reasons"]),
        "blocked_domains_preserved": blocked_expected <= set(projection["blocked_or_unverified_domains"]),
        "external_gates_unchanged": projection["external_gate_effect"] == "UNCHANGED"
        and not programme["external_gate_evidence"],
        "owner_authority_unchanged": projection["owner_authority_effect"] == "UNCHANGED"
        and bool(projection["owner_decision_queue"]),
        "ledger_integrity": fabric.verify_ledger(),
        "restart_readback": restart_readback,
        "rollback_verified": rollback_verified,
    }
    status = (
        "PROVIDER_AUTHORITY_ACQUISITION_PACKAGE_VERIFIED_BLOCKED_DOMAINS_UNCHANGED"
        if all(gates.values())
        else "PROVIDER_AUTHORITY_ACQUISITION_PACKAGE_FAILED"
    )
    receipt = {
        "programme_id": programme["programme_id"],
        "status": status,
        "proof_scope": manifest["proof_scope"],
        "gates": gates,
        "operational_domains": projection["operational_domains"],
        "blocked_or_unverified_domains": projection["blocked_or_unverified_domains"],
        "owner_decision_queue": projection["owner_decision_queue"],
        "manifest_sha256": manifest["manifest_sha256"],
        "ledger_head": json.loads(
            (runtime / "provider-authority-acquisition-state.json").read_text(encoding="utf-8")
        )["ledger_head"],
        "truth_boundary": manifest["truth_boundary"],
    }
    receipt["receipt_sha256"] = digest(receipt)
    (out / "provider-authority-acquisition-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out / "rollback-proof.json").write_text(
        json.dumps(
            {
                "status": (
                    "AUTHORITY_ACQUISITION_ROLLBACK_VERIFIED" if rollback_verified else "FAILED"
                ),
                "original_hash": original_hash,
                "restored_hash": restored_hash,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if not all(gates.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
