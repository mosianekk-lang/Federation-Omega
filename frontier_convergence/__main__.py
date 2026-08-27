from __future__ import annotations
import json
import sys

from .canary import run_canary


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "canary"
    if command == "canary":
        print(json.dumps(run_canary(), sort_keys=True))
        return
    if command == "serve":
        from .service import run
        run()
        return
    raise SystemExit("usage: python -m frontier_convergence [canary|serve]")


if __name__ == "__main__":
    main()
