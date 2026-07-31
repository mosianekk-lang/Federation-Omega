#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

CRON_TO_MODE = {
    "17 * * * *": "hourly",
    "43 */6 * * *": "every_6_hours",
    "0 6 * * *": "daily_0800_sast",
    "0 20 * * *": "daily_2200_sast",
    "0 5 * * 1": "weekly_monday_0700_sast",
}


def canonical_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="auto")
    parser.add_argument("--cron", default="")
    parser.add_argument("--registry", default="scheduler/tasks.json")
    parser.add_argument("--output", default="scheduler/runtime/latest-report.json")
    args = parser.parse_args()

    registry = json.loads(Path(args.registry).read_text(encoding="utf-8"))
    mode = args.mode
    if mode == "auto":
        mode = CRON_TO_MODE.get(args.cron, "manual")

    selected = []
    for task in registry["tasks"]:
        cadence = task["cadence"]
        if cadence == mode:
            selected.append(task)
        elif mode == "hourly" and cadence == "dependency_driven":
            selected.append(task)
        elif mode == "manual":
            selected.append(task)

    now = datetime.now(timezone.utc).isoformat()
    assessments = []
    for task in selected:
        state = task["state"]
        if state == "BLOCKED":
            decision = "WATCHING_BLOCKER"
        elif cadence_is_dispatchable(task["cadence"], mode):
            decision = "READY_FOR_AUTHORISED_DISPATCH"
        else:
            decision = "REVIEW_REQUIRED"
        assessments.append({
            "task_id": task["task_id"],
            "title": task["title"],
            "registry_state": state,
            "decision": decision,
            "action": task["action"],
            "proof_gate": task["proof_gate"],
            "blocker": task.get("blocker"),
        })

    report = {
        "generated_at": now,
        "mode": mode,
        "cron": args.cron,
        "selected_task_count": len(assessments),
        "assessments": assessments,
        "truth_boundary": "This scheduler selects and watches work. It does not claim external execution without a readback or proof receipt.",
    }
    report["report_sha256"] = canonical_hash(report)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("# EvidenceOps External Scheduler")
    print(f"Mode: {mode}")
    print(f"Tasks selected: {len(assessments)}")
    print(f"Report SHA-256: {report['report_sha256']}")
    for item in assessments:
        print(f"- {item['task_id']} | {item['decision']} | {item['title']}")
    return 0


def cadence_is_dispatchable(cadence: str, mode: str) -> bool:
    return cadence == mode or mode == "manual"


if __name__ == "__main__":
    raise SystemExit(main())
