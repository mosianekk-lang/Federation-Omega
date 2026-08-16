from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import LexAutonomousStrategyEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Lex Autonomous Strategy Engine")
    parser.add_argument("matter_packet", help="Path to a JSON matter packet")
    parser.add_argument("--workspace", default="./local-artifacts/lex-strategy")
    args = parser.parse_args()

    raw = json.loads(Path(args.matter_packet).read_text(encoding="utf-8"))
    engine = LexAutonomousStrategyEngine(args.workspace)
    run = engine.run(raw)
    print(json.dumps(run.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
