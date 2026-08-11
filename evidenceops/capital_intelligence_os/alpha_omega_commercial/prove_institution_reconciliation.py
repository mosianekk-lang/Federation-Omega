from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .institution_reconciliation import (
        digest,
        file_sha256,
        load_json,
        verify_institution_reconciliation,
    )
except ImportError:  # direct script execution
    from institution_reconciliation import (
        digest,
        file_sha256,
        load_json,
        verify_institution_reconciliation,
    )


ROOT = Path(__file__).resolve().parents[1]
COMMERCIAL_ROOT = ROOT / "alpha_omega_commercial"
INSTITUTION_ROOT = ROOT / "alpha_omega_v30"

SOURCE_PATHS = {
    "commercial_programme": COMMERCIAL_ROOT / "programme.json",
    "governed_release": COMMERCIAL_ROOT / "governed_authority_release_receipt.json",
    "governed_checkpoint": COMMERCIAL_ROOT / "governed_authority_checkpoint.json",
    "institution_programme": INSTITUTION_ROOT / "programme.json",
    "institution_checkpoint": INSTITUTION_ROOT / "checkpoint_20260803.json",
}


def build_proof(output: Path) -> dict:
    sources = {name: load_json(path) for name, path in SOURCE_PATHS.items()}
    reconciliation = verify_institution_reconciliation(
        sources["commercial_programme"],
        sources["governed_release"],
        sources["governed_checkpoint"],
        sources["institution_programme"],
        sources["institution_checkpoint"],
    )
    if not all(reconciliation["checks"].values()):
        raise SystemExit("institution reconciliation checks did not all pass")

    receipt = {
        **reconciliation,
        "source_file_sha256": {
            name: file_sha256(path) for name, path in SOURCE_PATHS.items()
        },
    }
    receipt["receipt_sha256"] = digest(receipt)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    readback = load_json(output)
    readback_hash = readback.pop("receipt_sha256")
    if readback_hash != digest(readback):
        raise SystemExit("institution reconciliation receipt readback hash mismatch")
    readback["receipt_sha256"] = readback_hash
    if readback != receipt:
        raise SystemExit("institution reconciliation receipt readback mismatch")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=COMMERCIAL_ROOT
        / "artifacts/c15/institution-reconciliation/institution-reconciliation-receipt.json",
    )
    args = parser.parse_args()
    print(json.dumps(build_proof(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
