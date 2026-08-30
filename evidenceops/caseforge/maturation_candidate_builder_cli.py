from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .maturation_candidate_builder import (
    CandidateBuildRequest,
    SuperiorLogicCandidateBuilder,
    standard_challenger_missions,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the provider-disabled Stage-20 PR candidate-builder canary.")
    parser.add_argument("--input-work-package", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mission-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--base-ref", default="main")
    parser.add_argument("--target-branch", required=True)
    parser.add_argument("--observed-at", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    work_package = json.loads(Path(args.input_work_package).read_text(encoding="utf-8"))
    builder = SuperiorLogicCandidateBuilder()
    receipt = builder.build(
        CandidateBuildRequest(
            mission_id=args.mission_id,
            run_id=args.run_id,
            head_sha=args.head_sha,
            base_ref=args.base_ref,
            target_branch=args.target_branch,
            observed_at=args.observed_at,
            work_package=work_package,
            challenger_missions=standard_challenger_missions(),
        )
    )
    paths = builder.write_receipts(receipt, Path(args.output_dir))
    payload = receipt.to_dict()
    payload["written_paths"] = [str(path) for path in paths]
    print(json.dumps(payload, indent=2, sort_keys=True))
    if receipt.status != "CANDIDATE_CANARY_ASSURED":
        return 2
    if not receipt.provider_disabled or receipt.external_effect:
        return 3
    if len(receipt.observations) != 5:
        return 4
    if receipt.assurance.stable_promotion_authorized:
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
