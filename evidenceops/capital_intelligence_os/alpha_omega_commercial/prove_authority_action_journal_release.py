from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from authority_snapshot import digest


ROOT = Path(__file__).resolve().parent


def load(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def run(output: Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    release = load("authority_action_journal_release_receipt.json")
    checkpoint = load("authority_action_journal_release_checkpoint.json")
    contract = load("authority_action_journal_contract.json")
    implementation_checkpoint = load("authority_action_journal_checkpoint.json")
    api = load("canonical_commercial_api.json")
    programme = load("programme.json")
    institution = json.loads(
        (ROOT.parent / "alpha_omega_v30" / "maturity.json").read_text(
            encoding="utf-8"
        )
    )

    receipt_payload = dict(release)
    recorded_receipt_sha = receipt_payload.pop("receipt_sha256")
    workflows = release["final_head_workflows"]
    journal_revision = "AO-COMMERCIAL-AUTHORITY-ACTION-JOURNAL-V8"
    journal_class = "JournalSafeAtomicAuthoritySnapshotCommercialControlPlane"
    checks = {
        "release_receipt_integrity": digest(receipt_payload)
        == recorded_receipt_sha,
        "implementation_pr_and_merge_bound": (
            release["dependency"]["implementation_pull_request"] == 131
            and release["dependency"]["implementation_merge_commit"]
            == "921103b39494c7101744f55d66c3f5e37b5ec48f"
        ),
        "dependency_order_preserved": release["stage_scope"]
        == ["C03", "C11", "C12", "C13", "C15"],
        "final_provider_artifact_bound": (
            release["final_head_provider_proof"]["head_sha"]
            == "4e45e1c30852febc5f721128c577ceb8a6e7f132"
            and release["final_head_provider_proof"]["workflow_run"]
            == 30887326807
            and release["final_head_provider_proof"]["artifact_id"]
            == 8883598911
            and release["final_head_provider_proof"]["artifact_digest"]
            == "sha256:730c599ebf4bdeb24838409d1bf7da3e60e317464b835776d5a1eaacb5c73c8c"
            and release["final_head_provider_proof"]["receipt_file_sha256"]
            == "f4460b618c66c26c41fdb1ee354e0656e5e442ba8cb90cc3b314dfadacc4d7b0"
            and release["final_head_provider_proof"]["receipt_sha256"]
            == "611d04bf8264bf4b968d2c80b96e0fa30eab4f9a1030bb40eba0841ec98044c6"
            and release["final_head_provider_proof"]["checks_required"] == 12
            and release["final_head_provider_proof"]["checks_failed"] == 0
        ),
        "all_final_workflows_recorded": len(workflows) == 19
        and all(
            isinstance(run_id, int) and run_id > 0
            for run_id in workflows.values()
        ),
        "required_regression_workflows_bound": (
            workflows["C01_C05"] == 30887326743
            and workflows["C06_C09"] == 30887326671
            and workflows["C10_C15"] == 30887326696
            and workflows["authority_action_journal"] == 30887326807
            and workflows["authority_action_crash_recovery"] == 30887326682
            and workflows["authority_action_atomicity"] == 30887326693
            and workflows["github_control_plane"] == 30887326840
            and workflows["repository_leak_guard"] == 30887326656
            and workflows["superior_logic_ci"] == 30887326936
        ),
        "drive_release_exactly_bound": (
            release["google_drive_release"]["file_id"]
            == "1XXfR6s8g76tFlqZrEofmy4x7eSet1WsEg1sE8iGQh9Q"
            and release["google_drive_release"]["revision_id"] == "3"
            and release["google_drive_release"]["readback_sha256"]
            == "40f0a836a98848529df5a28a011587ca6a2a8b30dd2db4f0355764e407ff573a"
            and release["google_drive_release"]["readback_length"] == 4323
            and release["google_drive_release"]["readback_verified"] is True
            and release["google_drive_release"]["shared"] is False
            and release["google_drive_release"]["owner"]
            == "mosianekk@gmail.com"
        ),
        "checkpoint_matches_release": (
            checkpoint["implementation_release"]["pull_request"] == 131
            and checkpoint["implementation_release"]["merge_commit"]
            == release["dependency"]["implementation_merge_commit"]
            and checkpoint["implementation_release"]["release_receipt_sha256"]
            == recorded_receipt_sha
            and checkpoint["provider_proof"]["artifact_id"]
            == release["final_head_provider_proof"]["artifact_id"]
            and checkpoint["google_drive_release"]["file_id"]
            == release["google_drive_release"]["file_id"]
            and checkpoint["google_drive_release"]["readback_sha256"]
            == release["google_drive_release"]["readback_sha256"]
        ),
        "implementation_contract_bound": (
            contract["control_id"]
            == "AO-COMMERCIAL-AUTHORITY-ACTION-JOURNAL-V8"
            and contract["depends_on"]["pull_request"] == 130
            and contract["journal_rules"]["legacy_jsonl_prefix_frozen"]
            is True
            and contract["journal_rules"]["new_event_atomic_publication"]
            is True
            and contract["journal_rules"]["event_filename_hash_bound"]
            is True
            and contract["journal_rules"]["event_content_hash_bound"]
            is True
            and contract["journal_rules"]["torn_transaction_event_visible_after_process_crash"]
            is False
        ),
        "implementation_checkpoint_preserves_boundaries": (
            implementation_checkpoint["dependency_checkpoint"][
                "preceding_pull_request"
            ]
            == 130
            and all(
                value is False
                for value in implementation_checkpoint["external_gates"].values()
            )
            and implementation_checkpoint["commercial_truth"][
                "verified_live_revenue_events"
            ]
            == 0
        ),
        "canonical_api_revision_bound": (
            api["api_id"] == "AO-COMMERCIAL-CANONICAL-API-V3"
            and journal_revision in api["capability_lineage"]
            and journal_class in api["canonical_lineage"]
            and api["current_capability_revision"] in api["capability_lineage"]
            and api["current_canonical_class"] in api["canonical_lineage"]
            and api["capability_lineage"].index(
                api["current_capability_revision"]
            )
            <= api["capability_lineage"].index(journal_revision)
            and api["canonical_lineage"].index(api["current_canonical_class"])
            <= api["canonical_lineage"].index(journal_class)
            and api["authority_use"][
                "atomic_transaction_event_publication_required"
            ]
            is True
            and api["authority_use"][
                "torn_transaction_event_visible_after_process_crash"
            ]
            is False
        ),
        "service_first_strategy_preserved": (
            release["strategy"]
            == "SERVICE_ENABLED_PLATFORM_BEFORE_SELF_SERVICE_SAAS"
            and release["self_service_saas"] == "HELD"
            and api["service_first_strategy"]
            == "SERVICE_ENABLED_PLATFORM_BEFORE_SELF_SERVICE_SAAS"
        ),
        "external_gates_remain_false": all(
            value is False for value in release["external_gates"].values()
        )
        and not programme["external_gate_evidence"],
        "zero_revenue_preserved": (
            release["commercial_truth"]["verified_live_revenue_events"] == 0
            and checkpoint["commercial_truth"]["verified_live_revenue_events"]
            == 0
            and api["verified_live_revenue_events"] == 0
        ),
        "no_cloud_payment_or_distributed_atomicity_claim": (
            release["commercial_truth"]["cloud_run_operation_proven"] is False
            and release["commercial_truth"][
                "payment_provider_operation_proven"
            ]
            is False
            and release["effective_controls"][
                "distributed_provider_atomicity_proven"
            ]
            is False
        ),
        "owner_authority_preserved": all(
            value.startswith("OWNER_RESERVED")
            for value in release["owner_authority"].values()
        ),
        "institution_external_completion_still_blocked": (
            institution["phases"][-1]["id"] == "P15"
            and "BLOCKED" in institution["phases"][-1]["status"]
        ),
        "full_commercial_maturity_not_claimed": (
            release["commercial_truth"]["full_commercial_maturity"] is False
            and api["full_commercial_maturity"] is False
        ),
    }

    proof: dict[str, Any] = {
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "proof_id": "AO-COMMERCIAL-AUTHORITY-ACTION-JOURNAL-V8-RELEASE-PROOF",
        "status": (
            "AUTHORITY_ACTION_JOURNAL_RELEASE_RECONCILIATION_PROVIDER_PROOF_VERIFIED"
            if all(checks.values())
            else "AUTHORITY_ACTION_JOURNAL_RELEASE_RECONCILIATION_FAILED"
        ),
        "checks": checks,
        "checks_required": len(checks),
        "checks_failed": sum(not value for value in checks.values()),
        "release_receipt_sha256": recorded_receipt_sha,
        "implementation_merge_commit": release["dependency"][
            "implementation_merge_commit"
        ],
        "provider_artifact_id": release["final_head_provider_proof"][
            "artifact_id"
        ],
        "provider_artifact_digest": release["final_head_provider_proof"][
            "artifact_digest"
        ],
        "google_drive_file_id": release["google_drive_release"]["file_id"],
        "google_drive_revision_id": release["google_drive_release"][
            "revision_id"
        ],
        "google_drive_readback_sha256": release["google_drive_release"][
            "readback_sha256"
        ],
        "google_drive_readback_verified": True,
        "google_drive_shared": False,
        "verified_live_revenue_events": 0,
        "external_gate_effect": "UNCHANGED",
        "full_commercial_maturity": False,
    }
    proof["proof_sha256"] = digest(proof)
    output.write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not all(checks.values()):
        raise SystemExit(
            "authority action journal release reconciliation failed"
        )
    return proof


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "alpha_omega_commercial/artifacts/c15/authority-action-journal-release/reconciliation-receipt.json"
        ),
    )
    args = parser.parse_args()
    proof = run(args.output)
    print(json.dumps(proof, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
