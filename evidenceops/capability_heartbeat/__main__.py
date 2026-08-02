from __future__ import annotations

import argparse
import hashlib
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
    sources, candidates = engine.collect()
    report = {
        "schema": "EVIDENCEOPS-CAPABILITY-CATALOGUE-INVENTORY-2",
        "source_count": len(sources),
        "candidate_count": len(candidates),
        "heartbeats": sources,
        "candidates": [item.to_dict() for item in candidates],
        "decisions": [],
        "recommendation_authority": False,
        "ingress_authority": False,
        "scheduler_authority": False,
        "truth_boundary": "The standalone CLI is inventory-only. Recommendations require an injected verified-v4 authority session.",
    }
    report["report_sha256"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
