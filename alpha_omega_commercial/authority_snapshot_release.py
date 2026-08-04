from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def valid_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except (TypeError, ValueError):
        return False
    return True


class AuthoritySnapshotReleaseVerifier:
    """Fail-closed reconciliation for the authority-snapshot release receipt."""

    EXPECTED_WORKFLOWS = {
        "c01_c05",
        "c06_c09",
        "c10_c15",
        "provider_authority_acquisition",
        "governed_authority",
        "institution_reconciliation",
        "effective_state",
        "github_control_plane",
        "superior_logic_ci",
        "repository_leak_guard",
    }

    EXPECTED_STAGES = {"C03", "C11", "C12", "C13", "C15"}

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def verify(self) -> dict[str, bool]:
        receipt = self._read("authority_snapshot_release_receipt.json")
        checkpoint = self._read("authority_snapshot_checkpoint.json")
        api = self._read("canonical_commercial_api.json")
        programme = self._read("programme.json")
        effective = self._read("effective_programme_state.json")

        unsigned = copy.deepcopy(receipt)
        recorded_hash = unsigned.pop("receipt_sha256", "")
        workflows = receipt.get("required_workflows", {})
        external = receipt.get("external_gates", {})
        truth = receipt.get("commercial_truth", {})
        owner = receipt.get("owner_authority", {})
        drive = receipt.get("google_drive_release", {})
        proof = receipt.get("final_head_provider_proof", {})

        checks = {
            "programme_identity": receipt.get("programme_id") == "AO-COMMERCIAL-MATURITY-V1",
            "release_status_exact": receipt.get("status") == "AUTHORITY_SNAPSHOT_RELEASE_VERIFIED_EXTERNAL_GATES_UNCHANGED",
            "scope_exact": set(receipt.get("scope", [])) == self.EXPECTED_STAGES,
            "receipt_hash_valid": valid_sha256(recorded_hash) and digest(unsigned) == recorded_hash,
            "merged_dependency_exact": (
                receipt.get("dependency_checkpoint", {}).get("pull_request") == 122
                and receipt.get("dependency_checkpoint", {}).get("merge_commit")
                == "c48f7db758895389fa12f3476efbe19aa2169535"
            ),
            "canonical_api_v3": (
                api.get("api_id") == "AO-COMMERCIAL-CANONICAL-API-V3"
                and api.get("canonical_class") == "AuthoritySnapshotCommercialControlPlane"
                and api.get("predecessor_class") == "GovernedCommercialAssuranceControlPlane"
                and api.get("authority_snapshot", {}).get("raw_authority_dictionary_grants_live_authority") is False
            ),
            "release_checkpoint_exact": (
                checkpoint.get("status")
                == "AUTHORITY_SNAPSHOT_RELEASE_RECONCILIATION_VERIFIED_EXTERNAL_GATES_UNCHANGED"
                and checkpoint.get("implementation", {}).get("pull_request") == 122
                and checkpoint.get("implementation", {}).get("merge_commit")
                == "c48f7db758895389fa12f3476efbe19aa2169535"
                and checkpoint.get("provider_proof", {}).get("artifact_id") == 8879850560
                and checkpoint.get("provider_proof", {}).get("implementation_proof_artifact_id") == 8879825940
                and checkpoint.get("release_receipt", {}).get("receipt_sha256") == recorded_hash
                and checkpoint.get("release_receipt", {}).get("google_drive_export_sha256")
                == drive.get("export_sha256")
            ),
            "final_head_provider_proof_exact": (
                proof.get("head_sha") == "273409929e85ecdf7202c36595270004451d1b92"
                and proof.get("workflow_run") == 30876921201
                and proof.get("workflow_job") == 91890168491
                and proof.get("artifact_id") == 8879850560
                and proof.get("artifact_digest")
                == "sha256:493811eeb57d4272b06244bb7c81cb2f91fc412fb8e508440eb0ee8d2e3a8f5c"
                and proof.get("job_steps_all_success") is True
            ),
            "required_workflows_complete": (
                set(workflows) == self.EXPECTED_WORKFLOWS
                and all(item.get("conclusion") == "success" for item in workflows.values())
                and all(isinstance(item.get("run"), int) and item["run"] > 0 for item in workflows.values())
            ),
            "drive_release_complete": (
                drive.get("file_id") == "1cTzy5o0kn4SzDBYm5cZRGKh6_kgZb-392H0dSMPSzRY"
                and drive.get("readback_verified") is True
                and drive.get("shared") is False
                and drive.get("owner") == "mosianekk@gmail.com"
                and drive.get("export_size_bytes") == 4501
                and drive.get("export_sha256")
                == "6e9f729df19691bcc08a0432365c9d5dbaa98a79aaad49621cd816a53c7508f2"
            ),
            "stage_projection_complete": set(receipt.get("stage_projection", {})) == self.EXPECTED_STAGES,
            "external_gates_unchanged": (
                len(external) == 8 and all(value is False for value in external.values())
            ),
            "zero_revenue_truth_preserved": truth.get("verified_live_revenue_events") == 0,
            "cloud_and_maturity_not_claimed": (
                truth.get("cloud_run_operation_proven") is False
                and truth.get("full_commercial_maturity") is False
            ),
            "owner_authority_preserved": owner == {
                "financial_commitments": "OWNER_RESERVED",
                "contracts": "OWNER_RESERVED",
                "external_communications": "OWNER_RESERVED",
                "consequential_releases": "OWNER_RESERVED",
                "revenue_recognition": "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED",
            },
            "canonical_programme_boundary_preserved": (
                programme.get("canonical_status")
                == "COMMERCIAL_READINESS_VERIFIED_EXTERNAL_MATURITY_GATES_OPEN"
                and not programme.get("external_gate_evidence")
            ),
            "effective_state_boundary_preserved": (
                effective.get("status")
                == "EFFECTIVE_PROGRAMME_STATE_VERIFIED_C15_INSTITUTION_RECONCILED_EXTERNAL_GATES_OPEN"
                and all(value is False for value in effective.get("external_gates", {}).values())
                and effective.get("commercial_truth", {}).get("verified_live_revenue_events") == 0
                and effective.get("commercial_truth", {}).get("full_commercial_maturity") is False
            ),
        }
        return checks

    def require_verified(self) -> dict[str, bool]:
        checks = self.verify()
        failed = sorted(name for name, passed in checks.items() if not passed)
        if failed:
            raise ValueError("authority snapshot release verification failed: " + ",".join(failed))
        return checks

    def _read(self, name: str) -> dict[str, Any]:
        return json.loads((self.root / name).read_text(encoding="utf-8"))
