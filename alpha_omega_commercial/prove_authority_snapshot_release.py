from __future__ import annotations

import argparse
import json
from pathlib import Path

from authority_snapshot_release import AuthoritySnapshotReleaseVerifier, digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="alpha_omega_commercial/artifacts/c15/authority-snapshot-release/reconciliation-receipt.json",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    checks = AuthoritySnapshotReleaseVerifier(root).require_verified()
    release = json.loads(
        (root / "authority_snapshot_release_receipt.json").read_text(encoding="utf-8")
    )

    proof = {
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "control_id": "AO-COMMERCIAL-AUTHORITY-SNAPSHOT-RELEASE-RECONCILIATION-V1",
        "status": "AUTHORITY_SNAPSHOT_RELEASE_RECONCILIATION_PROVIDER_PROOF_VERIFIED",
        "checks": checks,
        "release_receipt_sha256": release["receipt_sha256"],
        "merge_commit": release["dependency_checkpoint"]["merge_commit"],
        "final_head_artifact_id": release["final_head_provider_proof"]["artifact_id"],
        "final_head_artifact_digest": release["final_head_provider_proof"]["artifact_digest"],
        "google_drive_file_id": release["google_drive_release"]["file_id"],
        "google_drive_export_sha256": release["google_drive_release"]["export_sha256"],
        "google_drive_readback_verified": release["google_drive_release"]["readback_verified"],
        "google_drive_shared": release["google_drive_release"]["shared"],
        "verified_live_revenue_events": 0,
        "external_gate_effect": "UNCHANGED",
        "full_commercial_maturity": False,
        "owner_authority": release["owner_authority"],
        "truth_boundary": release["truth_boundary"],
    }
    proof["proof_sha256"] = digest(proof)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(proof, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
