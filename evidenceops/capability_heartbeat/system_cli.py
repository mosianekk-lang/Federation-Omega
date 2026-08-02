from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .system import EvidenceOpsHeartbeatSystem


def main() -> int:
    parser = argparse.ArgumentParser(description="Operate the EvidenceOps Heartbeat System")
    parser.add_argument("command", choices=["index", "turn", "reconcile", "surfaces", "seeds"])
    parser.add_argument("--db", default="scheduler/runtime/evidenceops-heartbeat.db")
    parser.add_argument("--surfaces", default="evidenceops/capability_heartbeat/surface_registry.json")
    parser.add_argument("--event")
    parser.add_argument("--chat-id")
    parser.add_argument("--output")
    args = parser.parse_args()

    system = EvidenceOpsHeartbeatSystem(args.db, repository_root=".")
    now = datetime.now(timezone.utc).isoformat()
    if args.command == "index":
        result = system.index_surfaces(system.load_surface_registry(args.surfaces), observed_at=now)
    elif args.command == "turn":
        if not args.event:
            parser.error("--event is required for turn")
        result = system.ingest_turn(json.loads(Path(args.event).read_text(encoding="utf-8")))
    elif args.command == "reconcile":
        result = system.reconcile(observed_at=now)
    elif args.command == "surfaces":
        result = system.surface_status()
    else:
        result = system.connector_seed_status(args.chat_id)
    system.close()
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
