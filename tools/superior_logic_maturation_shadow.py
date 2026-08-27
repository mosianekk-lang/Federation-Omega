#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from evidenceops.caseforge.maturation_shadow_runtime import (
    ShadowRuntimeInput,
    SuperiorLogicMaturationShadowRuntime,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the provider-disabled Superior Logic maturation shadow cycle."
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--event", required=True, choices=("schedule", "push", "workflow_dispatch"))
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--previous-successful-cycles", type=int, default=0)
    parser.add_argument("--previous-manual-cycles", type=int, default=0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runtime = SuperiorLogicMaturationShadowRuntime()
    receipt = runtime.run(
        ShadowRuntimeInput(
            run_id=args.run_id,
            head_sha=args.head_sha,
            event=args.event,
            observed_at=args.observed_at,
            previous_successful_cycles=args.previous_successful_cycles,
            previous_manual_cycles=args.previous_manual_cycles,
        )
    )
    output_dir = Path(args.output_dir)
    paths = runtime.write_receipts(receipt, output_dir)
    payload = receipt.to_dict()
    payload["written_paths"] = [str(path) for path in paths]
    print(json.dumps(payload, indent=2, sort_keys=True))
    if receipt.status != "SHADOW_MATURATION_CYCLE_VERIFIED":
        return 2
    if receipt.external_effect:
        return 3
    if not receipt.transaction_id or not receipt.idempotency_key:
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
