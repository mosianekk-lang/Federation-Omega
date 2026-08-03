import argparse
import json
from pathlib import Path

from .foundry import SolutionFoundry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("concept_json")
    parser.add_argument("--workspace", default="./ao_foundry_workspace")
    parser.add_argument("--portfolio", action="store_true")
    parser.add_argument("--maintenance-cycle", action="store_true")
    args = parser.parse_args()
    raw = json.loads(Path(args.concept_json).read_text(encoding="utf-8"))
    foundry = SolutionFoundry(args.workspace)

    if args.portfolio:
        result = foundry.score_portfolio(raw)
    elif args.maintenance_cycle:
        spec = foundry.compile_product_spec(raw)
        genome = foundry.compile_solution_genome(spec, foundry.capability_marketplace())
        expected = raw.get(
            "maintenance_expected",
            {"version": "2.2.0", "provider": "github_actions"},
        )
        actual = raw.get("maintenance_actual", expected)
        result = foundry.operations.maintenance_cycle(
            genome["system_id"],
            expected=expected,
            actual=actual,
            error=str(raw.get("maintenance_error", "")),
            metrics=raw.get("maintenance_metrics"),
        )
    else:
        result = foundry.operational_release(raw)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
