from __future__ import annotations

import argparse
import json

from .core import load_observations, load_profiles, run_certification, write_json_atomic


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CFBE fidelity adapter certification Wave 1")
    parser.add_argument("--profiles")
    parser.add_argument("--observations")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    profiles = load_profiles(args.profiles) if args.profiles else load_profiles()
    observations = load_observations(args.observations) if args.observations else None
    scorecard = run_certification(profiles, observations=observations)
    write_json_atomic(args.output, scorecard)
    print(json.dumps({"certificationState": scorecard["certificationState"], "receiptSha256": scorecard["receiptSha256"]}, sort_keys=True))
    return 0 if scorecard["certificationState"].endswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
