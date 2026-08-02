#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from evidenceops.capability_heartbeat import CapabilityHeartbeatEngine
from evidenceops.capability_heartbeat.system import EvidenceOpsHeartbeatSystem
from evidenceops.build_system.objective_completion_guard import evaluate as evaluate_completion
from evidenceops.cloud_capability.inheritance import audit_inheritance

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
    parser.add_argument(
        "--heartbeat-registry",
        default="evidenceops/capability_heartbeat/sources.json",
    )
    parser.add_argument(
        "--heartbeat-context",
        default="evidenceops/capability_heartbeat/current_workflow.json",
    )
    parser.add_argument(
        "--heartbeat-output",
        default="scheduler/runtime/capability-heartbeat.json",
    )
    parser.add_argument(
        "--heartbeat-system-db",
        default="scheduler/runtime/evidenceops-heartbeat.db",
    )
    parser.add_argument(
        "--heartbeat-system-output",
        default="scheduler/runtime/heartbeat-system.json",
    )
    parser.add_argument(
        "--completion-state",
        default="evidenceops/secure_capability_box/objective_completion_state.json",
    )
    parser.add_argument(
        "--completion-output",
        default="scheduler/runtime/objective-completion.json",
    )
    parser.add_argument(
        "--cloud-capability-output",
        default="scheduler/runtime/cloud-capability-inheritance.json",
    )
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

    heartbeat_engine = CapabilityHeartbeatEngine(".", args.heartbeat_registry)
    heartbeat_sources, heartbeat_candidates = heartbeat_engine.collect()
    heartbeat = {
        "schema": "EVIDENCEOPS-SCHEDULED-CAPABILITY-INVENTORY-2",
        "generated_at": now,
        "source_count": len(heartbeat_sources),
        "candidate_count": len(heartbeat_candidates),
        "heartbeats": heartbeat_sources,
        "candidates": [item.to_dict() for item in heartbeat_candidates],
        "decisions": [],
        "scheduler_authority": False,
        "recommendation_authority": False,
        "ingress_authority": False,
        "live_awareness_flags": {
            "live_master_bible_attachment": False,
            "active_chat_inventory": False,
            "per_chat_emitters": False,
            "unsolicited_injection": False,
            "system_wide_awareness": False,
        },
        "truth_boundary": "Scheduled execution inventories local catalogue evidence only; verified-v4 recommendations require an explicit on-input authority session.",
    }
    heartbeat["report_sha256"] = canonical_hash(heartbeat)
    heartbeat_output = Path(args.heartbeat_output)
    heartbeat_output.parent.mkdir(parents=True, exist_ok=True)
    heartbeat_output.write_text(
        json.dumps(heartbeat, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    heartbeat_system = EvidenceOpsHeartbeatSystem(
        args.heartbeat_system_db, repository_root="."
    )
    surface_index = heartbeat_system.index_surfaces(
        heartbeat_system.load_surface_registry(
            "evidenceops/capability_heartbeat/surface_registry.json"
        ),
        observed_at=now,
    )
    reconciliation = heartbeat_system.reconcile(observed_at=now)
    heartbeat_system.close()
    heartbeat_system_report = {
        "schema": "EVIDENCEOPS-HEARTBEAT-SYSTEM-SCHEDULER-2",
        "surface_index": surface_index,
        "reconciliation": reconciliation,
        "runtime_state": "SCHEDULED_INVENTORY_ONLY",
        "scheduler_authority": False,
        "recommendation_authority": False,
        "truth_boundary": "This scheduled report inventories static surfaces and local expiry state only; it cannot recommend, authorize ingress, advance remediation, dispatch, or prove live attachment.",
    }
    heartbeat_system_report["report_sha256"] = canonical_hash(
        heartbeat_system_report
    )
    heartbeat_system_output = Path(args.heartbeat_system_output)
    heartbeat_system_output.parent.mkdir(parents=True, exist_ok=True)
    heartbeat_system_output.write_text(
        json.dumps(heartbeat_system_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    completion_packet = json.loads(
        Path(args.completion_state).read_text(encoding="utf-8")
    )
    completion = evaluate_completion(completion_packet)
    completion["evaluatedAt"] = now
    completion["source"] = args.completion_state
    completion["report_sha256"] = canonical_hash(completion)
    completion_output = Path(args.completion_output)
    completion_output.parent.mkdir(parents=True, exist_ok=True)
    completion_output.write_text(
        json.dumps(completion, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    cloud_capability = audit_inheritance(".")
    cloud_capability["evaluatedAt"] = now
    cloud_capability["report_sha256"] = canonical_hash(cloud_capability)
    cloud_output = Path(args.cloud_capability_output)
    cloud_output.parent.mkdir(parents=True, exist_ok=True)
    cloud_output.write_text(
        json.dumps(cloud_capability, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("# EvidenceOps External Scheduler")
    print(f"Mode: {mode}")
    print(f"Tasks selected: {len(assessments)}")
    print(f"Report SHA-256: {report['report_sha256']}")
    for item in assessments:
        print(f"- {item['task_id']} | {item['decision']} | {item['title']}")
    print(
        f"Capability heartbeat: {heartbeat['source_count']} sources, "
        f"{len(heartbeat['decisions'])} scheduler decisions, "
        f"SHA-256 {heartbeat['report_sha256']}"
    )
    print(
        f"Heartbeat System: {surface_index['surface_count']} surfaces, "
        f"{reconciliation['adapter_remediation']['open_case_count']} adapter cases, "
        f"SHA-256 {heartbeat_system_report['report_sha256']}"
    )
    print(
        f"Objective completion: {completion['decision']} | "
        f"continue={completion['mustContinue']} | "
        f"final-response={completion['finalResponsePermitted']}"
    )
    print(
        f"Cloud capability inheritance: all-bound={cloud_capability['all_bound']} | "
        f"contracts={len(cloud_capability['build_contracts_checked'])} | "
        f"missing={len(cloud_capability['missing_bindings'])}"
    )
    return 0


def cadence_is_dispatchable(cadence: str, mode: str) -> bool:
    return cadence == mode or mode == "manual"


if __name__ == "__main__":
    raise SystemExit(main())
