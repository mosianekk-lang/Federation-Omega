from __future__ import annotations

import argparse
import json
from pathlib import Path

from .foundry import SolutionFoundry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("concept_json")
    parser.add_argument("--workspace", default="./ao_foundry_workspace")
    parser.add_argument("--portfolio", action="store_true")
    parser.add_argument("--github-artifact", action="store_true")
    args = parser.parse_args()

    raw = json.loads(Path(args.concept_json).read_text(encoding="utf-8"))
    foundry = SolutionFoundry(args.workspace)
    if args.portfolio:
        result = foundry.score_portfolio(raw)
    elif args.github_artifact:
        result = foundry.github_release_artifact(raw)
    else:
        result = foundry.operational_release(raw)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
