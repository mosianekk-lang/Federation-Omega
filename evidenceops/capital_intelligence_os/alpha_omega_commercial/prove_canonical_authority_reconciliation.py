from __future__ import annotations

import argparse
import json
from pathlib import Path

from canonical_authority_reconciliation import load_json, project_programme, reconcile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--programme", default="programme.json")
    parser.add_argument("--requirements", default="provider_authority_requirements.json")
    parser.add_argument("--manifest", default="../sol_61_runtime/canonical_live_authority_manifest.json")
    parser.add_argument("--provider-register", default="../sol_61_runtime/provider_certification_register.json")
    parser.add_argument("--workflow", default="../.github/workflows/alpha-omega-commercial-live-provider-expansion.yml")
    parser.add_argument("--output", default="artifacts/canonical-authority-reconciliation-proof")
    args = parser.parse_args()

    programme = load_json(args.programme)
    receipt = reconcile(
        programme,
        load_json(args.requirements),
        load_json(args.manifest),
        load_json(args.provider_register),
        Path(args.workflow).read_text(encoding="utf-8"),
    )
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    projected = project_programme(programme, receipt)
    (output / "canonical-authority-reconciliation-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "programme.updated.json").write_text(
        json.dumps(projected, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": receipt["status"], "receipt_sha256": receipt["receipt_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
