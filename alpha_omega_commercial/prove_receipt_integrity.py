from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from receipt_integrity import CommercialReceiptIntegrityReconciler


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output
    if not (root / "commercial-c10-c15-receipt.json").is_file():
        raise FileNotFoundError("run prove_c10_c15.py before receipt reconciliation")

    canary = root.parent / f"{root.name}-rollback-canary"
    if canary.exists():
        shutil.rmtree(canary)
    shutil.copytree(root, canary)

    integrity = CommercialReceiptIntegrityReconciler(root).reconcile()
    if integrity["status"] != "CANONICAL_RECEIPT_INTEGRITY_VERIFIED":
        raise SystemExit(1)

    canary_reconciler = CommercialReceiptIntegrityReconciler(canary)
    canary_integrity = canary_reconciler.reconcile()
    rollback = canary_reconciler.rollback()
    rollback_proof = {
        "status": rollback["status"],
        "integrity_before_rollback": canary_integrity["status"],
        "manifest_sha256": rollback["manifest_sha256"],
        "restored": rollback["restored"],
        "truth_boundary": "Rollback proof runs on an isolated artifact copy and does not revert the promoted canonical output.",
    }
    write_json(root / "canonical-receipt-rollback-proof.json", rollback_proof)
    shutil.rmtree(canary)

    if rollback["status"] != "CANONICAL_RECEIPT_ROLLBACK_VERIFIED":
        raise SystemExit(1)
    if not all(rollback["restored"].values()):
        raise SystemExit(1)

    print(json.dumps({"integrity": integrity, "rollback": rollback_proof}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
