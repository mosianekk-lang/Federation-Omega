from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import AlphaOmegaEngine
from .progressive import ProgressiveAlphaOmega


def main() -> None:
    parser = argparse.ArgumentParser(prog="alpha-omega")
    parser.add_argument("concept_json")
    parser.add_argument("--workspace", default="./alpha_omega_workspace")
    parser.add_argument("--build", action="store_true", help="Run the legacy local package build")
    parser.add_argument("--progressive", action="store_true", help="Compile the Formation-driven multi-path/multi-stream plan")
    parser.add_argument("--simulate-safe", action="store_true", help="Run the complete local A1 safe-scope canary; no provider effects")
    parser.add_argument("--max-parallel", type=int, default=8)
    parser.add_argument("--max-waves", type=int, default=100)
    args = parser.parse_args()

    raw = json.loads(Path(args.concept_json).read_text(encoding="utf-8"))
    if args.simulate_safe and not args.progressive:
        parser.error("--simulate-safe requires --progressive")

    if args.progressive:
        engine = ProgressiveAlphaOmega(args.workspace, max_parallel_safe=args.max_parallel)
        plan = engine.compile_plan(raw)
        print(json.dumps(plan.to_dict(), indent=2, default=str))
        if args.simulate_safe:
            receipt = engine.run_local_canary(plan, max_waves=args.max_waves)
            print(json.dumps(receipt, indent=2, default=str))
        return

    engine = AlphaOmegaEngine(args.workspace)
    plan = engine.build_plan(raw)
    print(json.dumps(plan.to_dict(), indent=2, default=str))
    if args.build:
        receipt = engine.execute_local_build(plan)
        print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
