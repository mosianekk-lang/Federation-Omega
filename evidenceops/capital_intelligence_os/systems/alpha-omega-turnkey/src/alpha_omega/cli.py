from __future__ import annotations
import argparse, json
from pathlib import Path
from .engine import AlphaOmegaEngine

def main():
    parser = argparse.ArgumentParser(prog="alpha-omega")
    parser.add_argument("concept_json")
    parser.add_argument("--workspace", default="./alpha_omega_workspace")
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()

    raw = json.loads(Path(args.concept_json).read_text(encoding="utf-8"))
    engine = AlphaOmegaEngine(args.workspace)
    plan = engine.build_plan(raw)
    print(json.dumps(plan.to_dict(), indent=2, default=str))
    if args.build:
        receipt = engine.execute_local_build(plan)
        print(json.dumps(receipt, indent=2))

if __name__ == "__main__":
    main()
