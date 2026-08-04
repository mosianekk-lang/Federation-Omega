from __future__ import annotations

import argparse
import json
from pathlib import Path

from canonical_api_reconciliation import require_verified


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts")
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    result = require_verified()
    target = output / "canonical-api-effective-v10-reconciliation-receipt.json"
    target.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(result["status"])
    print(f"checks={result['checks_required'] - result['checks_failed']}/{result['checks_required']}")
    print(f"proof_sha256={result['proof_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
