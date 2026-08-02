from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import CapabilityHeartbeatEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the EvidenceOps capability heartbeat")
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--registry",
        default="evidenceops/capability_heartbeat/sources.json",
    )
    parser.add_argument(
        "--context",
        default="evidenceops/capability_heartbeat/current_workflow.json",
    )
    parser.add_argument("--output")
    args = parser.parse_args()
    engine = CapabilityHeartbeatEngine(args.root, args.registry)
    report = engine.run(args.context)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
