from __future__ import annotations

import argparse
import json
from pathlib import Path

from owner_authority_reconciliation import (
    STATUS as OWNER_AUTHORITY_RECONCILIATION_STATUS,
    verify_from_paths as verify_owner_authority_from_paths,
)
from programme_integrity import verify_from_paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the commercial programme register against the canonical C15 proof artifact."
    )
    parser.add_argument("--programme", default="alpha_omega_commercial/programme.json")
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--owner-authority-checkpoint",
        default="alpha_omega_commercial/owner_authority_programme_checkpoint.json",
    )
    parser.add_argument(
        "--owner-authority-contract",
        default="alpha_omega_commercial/owner_authority_receipt_contract.json",
    )
    parser.add_argument(
        "--authority-manifest",
        default="sol_61_runtime/canonical_live_authority_manifest.json",
    )
    args = parser.parse_args()

    result = verify_from_paths(args.programme, args.artifact_root)
    output = Path(args.output) if args.output else Path(args.artifact_root) / "programme-register-integrity.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    owner_authority = verify_owner_authority_from_paths(
        args.programme,
        args.owner_authority_checkpoint,
        args.owner_authority_contract,
        args.authority_manifest,
    )
    owner_output = output.parent / "owner-authority-programme-reconciliation.json"
    owner_output.write_text(
        json.dumps(owner_authority, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    combined = {
        "programme_register": result,
        "owner_authority_reconciliation": owner_authority,
    }
    print(json.dumps(combined, indent=2, sort_keys=True))

    if result["status"] != "PROGRAMME_REGISTER_INTEGRITY_VERIFIED":
        raise SystemExit(1)
    if owner_authority["status"] != OWNER_AUTHORITY_RECONCILIATION_STATUS:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
