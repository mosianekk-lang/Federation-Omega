from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from alpha_omega_commercial.effective_state import (
    EffectiveStateError,
    build_effective_state,
    digest,
    file_sha256,
    load_json,
)


ROOT = Path(__file__).resolve().parent
SOURCE_PATHS = {
    "programme": ROOT / "programme.json",
    "governed_release": ROOT / "governed_authority_release_receipt.json",
    "governed_checkpoint": ROOT / "governed_authority_checkpoint.json",
    "institution_checkpoint": ROOT.parent / "alpha_omega_v30" / "checkpoint_20260803.json",
    "institution_reconciliation": ROOT / "institution_reconciliation_checkpoint.json",
    "drive_observation": ROOT / "institution_reconciliation_drive_observation.json",
    "effective_state": ROOT / "effective_programme_state.json",
}


def _core_state(value: dict[str, Any]) -> tuple[dict[str, Any], dict[str, bool]]:
    result = dict(value)
    checks = result.pop("checks", {})
    if not isinstance(checks, dict):
        raise EffectiveStateError("effective-state checks must be an object")
    return result, checks


def build_proof(output_path: str | Path) -> dict[str, Any]:
    sources = {name: load_json(path) for name, path in SOURCE_PATHS.items()}
    calculated = build_effective_state(
        sources["programme"],
        sources["governed_release"],
        sources["governed_checkpoint"],
        sources["institution_checkpoint"],
        sources["institution_reconciliation"],
        sources["drive_observation"],
    )
    core, checks = _core_state(calculated)
    committed = sources["effective_state"]
    if core != committed:
        raise EffectiveStateError("committed effective programme state does not match calculated state")
    state_for_hash = dict(committed)
    expected_state_hash = state_for_hash.pop("state_sha256", None)
    if expected_state_hash != digest(state_for_hash):
        raise EffectiveStateError("effective programme state hash mismatch")
    if not checks or not all(checks.values()):
        raise EffectiveStateError("one or more effective-state proof gates failed")

    receipt: dict[str, Any] = {
        "programme_id": committed["programme_id"],
        "status": "EFFECTIVE_PROGRAMME_STATE_PROVIDER_PROOF_VERIFIED",
        "effective_state_status": committed["status"],
        "effective_state_sha256": committed["state_sha256"],
        "checks": checks,
        "source_file_sha256": {
            name: file_sha256(path) for name, path in SOURCE_PATHS.items()
        },
        "provider_evidence": {
            "institution_reconciliation_pull_request": committed["control_chain"][
                "institution_reconciliation"
            ]["pull_request"],
            "institution_reconciliation_merge_commit": committed["control_chain"][
                "institution_reconciliation"
            ]["merge_commit"],
            "institution_reconciliation_workflow_run": committed["control_chain"][
                "institution_reconciliation"
            ]["workflow_run"],
            "institution_reconciliation_artifact_id": committed["control_chain"][
                "institution_reconciliation"
            ]["artifact_id"],
            "google_drive_release_file_id": committed["control_chain"][
                "google_drive_release"
            ]["file_id"],
            "google_drive_release_readback_verified": committed["control_chain"][
                "google_drive_release"
            ]["readback_verified"],
        },
        "external_gates": committed["external_gates"],
        "commercial_truth": committed["commercial_truth"],
        "owner_authority": committed["owner_authority"],
        "truth_boundary": committed["truth_boundary"],
    }
    receipt["receipt_sha256"] = digest(receipt)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    readback = json.loads(path.read_text(encoding="utf-8"))
    readback_hash = readback.pop("receipt_sha256", None)
    if readback_hash != digest(readback):
        raise EffectiveStateError("effective-state proof receipt readback mismatch")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(
            ROOT
            / "artifacts"
            / "c15"
            / "effective-state"
            / "effective-state-receipt.json"
        ),
    )
    args = parser.parse_args()
    receipt = build_proof(args.output)
    print(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
