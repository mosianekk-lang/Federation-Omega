#!/usr/bin/env python3
"""CLI for the EvidenceOps v8.1 ProofLoop bounded cycle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from proofloop import run_bounded_cycle, verify_release_state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("run", "verify"))
    parser.add_argument("--manifest")
    parser.add_argument("--state-dir", required=True)
    args = parser.parse_args()
    state_dir = Path(args.state_dir)
    if args.mode == "run":
        if not args.manifest:
            parser.error("--manifest is required for run mode")
        result = run_bounded_cycle(Path(args.manifest), state_dir)
    else:
        result = verify_release_state(state_dir)
    print(
        json.dumps(
            {
                "engineering_state": result["engineering_state"],
                "longitudinal_state": result["longitudinal_state"],
                "receipt_sha256": result["receipt_sha256"],
                "external_effects": result["external_effects"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
