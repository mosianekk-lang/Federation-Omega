from __future__ import annotations

"""CFBE/FUSE AutoPilot Omega4 resident execution cycle.

This module turns a bounded subset of the existing scheduler registry into
actual unattended, proof-bearing work. It reuses existing EvidenceOps/CFBE
owners instead of introducing a second intelligence stack.

The runtime is safe by construction:
- only explicitly allow-listed NO_EFFECT/read-only handlers can execute;
- unknown, external, effectful, implementation or owner-choice work is held;
- each cycle emits a deterministic receipt and resumable state document;
- restoring state never authorizes an external effect;
- completion is never inferred from dispatch alone.

A hosting workflow may invoke this module on a timer or event. That proves an
unattended host cycle only after provider-native workflow readback; it does not
by itself prove a continuously resident daemon, zero-compute wait, or full
provider-effect autonomy.
"""

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from evidenceops.build_system.objective_completion_guard import evaluate as evaluate_completion
from evidenceops.capability_heartbeat import CapabilityHeartbeatEngine
from evidenceops.capability_heartbeat.system import EvidenceOpsHeartbeatSystem
from evidenceops.cloud_capability.inheritance import audit_inheritance


SCHEMA = "CFBE_AUTOPILOT_OMEGA4_RESIDENT_RUNTIME_V1"
STATE_SCHEMA = "CFBE_AUTOPILOT_OMEGA4_RESIDENT_STATE_V1"
SAST = ZoneInfo("Africa/Johannesburg")


@dataclass(frozen=True, slots=True)
class TaskHandler:
    task_id: str
    handler: Callable[[Path, Path, dict[str, object]], dict[str, object]]
    effect_class: str = "NO_EFFECT"


def canonical_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _lane_watch(root: Path, output_dir: Path, task: dict[str, object]) -> dict[str, object]:
    registry = _read_json(root / "scheduler/tasks.json")
    tasks = list(registry.get("tasks", []))
    states: dict[str, int] = {}
    blocked: list[dict[str, object]] = []
    for row in tasks:
        state = str(row.get("state", "UNKNOWN"))
        states[state] = states.get(state, 0) + 1
        if state == "BLOCKED":
            blocked.append(
                {
                    "task_id": row.get("task_id"),
                    "title": row.get("title"),
                    "blocker": row.get("blocker"),
                }
            )
    result = {
        "task_count": len(tasks),
        "state_counts": states,
        "blocked": blocked,
        "registry_sha256": _file_sha256(root / "scheduler/tasks.json"),
    }
    (output_dir / "lane-watch.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def _continuity_checkpoint(root: Path, output_dir: Path, task: dict[str, object]) -> dict[str, object]:
    critical = (
        "scheduler/tasks.json",
        "scheduler/run_scheduler.py",
        "federation/bubbles_autopilot_policy.py",
        "federation/bubbles_autopilot_orchestrator.py",
        "bubbles/chat_governor_omega3/continuity.py",
    )
    hashes: dict[str, str] = {}
    missing: list[str] = []
    for rel in critical:
        path = root / rel
        if path.is_file():
            hashes[rel] = _file_sha256(path)
        else:
            missing.append(rel)
    result = {
        "critical_file_hashes": hashes,
        "missing": missing,
        "checkpoint_sha256": canonical_hash({"hashes": hashes, "missing": missing}),
    }
    (output_dir / "continuity-checkpoint.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def _capability_heartbeat(root: Path, output_dir: Path, task: dict[str, object]) -> dict[str, object]:
    heartbeat = CapabilityHeartbeatEngine(
        str(root), str(root / "evidenceops/capability_heartbeat/sources.json")
    ).run(str(root / "evidenceops/capability_heartbeat/current_workflow.json"))
    (output_dir / "capability-heartbeat.json").write_text(
        json.dumps(heartbeat, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    observed_at = datetime.now(timezone.utc).isoformat()
    system_db = output_dir / "evidenceops-heartbeat.db"
    system = EvidenceOpsHeartbeatSystem(str(system_db), repository_root=str(root))
    try:
        surface_index = system.index_surfaces(
            system.load_surface_registry(
                str(root / "evidenceops/capability_heartbeat/surface_registry.json")
            ),
            observed_at=observed_at,
        )
        reconciliation = system.reconcile(observed_at=observed_at)
    finally:
        system.close()
    system_report = {
        "surface_index": surface_index,
        "reconciliation": reconciliation,
    }
    (output_dir / "heartbeat-system.json").write_text(
        json.dumps(system_report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "heartbeat_report_sha256": heartbeat.get("report_sha256"),
        "source_count": heartbeat.get("source_count"),
        "surface_count": surface_index.get("surface_count"),
        "open_adapter_cases": reconciliation.get("adapter_remediation", {}).get(
            "open_case_count"
        ),
        "system_report_sha256": canonical_hash(system_report),
    }


def _objective_completion(root: Path, output_dir: Path, task: dict[str, object]) -> dict[str, object]:
    source = root / "evidenceops/secure_capability_box/objective_completion_state.json"
    result = evaluate_completion(_read_json(source))
    result["source_sha256"] = _file_sha256(source)
    result["report_sha256"] = canonical_hash(result)
    (output_dir / "objective-completion.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def _cloud_inheritance(root: Path, output_dir: Path, task: dict[str, object]) -> dict[str, object]:
    result = audit_inheritance(str(root))
    result["report_sha256"] = canonical_hash(result)
    (output_dir / "cloud-capability-inheritance.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


HANDLERS: dict[str, TaskHandler] = {
    "EXT-001": TaskHandler("EXT-001", _lane_watch),
    "EXT-004": TaskHandler("EXT-004", _continuity_checkpoint),
    "EXT-011": TaskHandler("EXT-011", _capability_heartbeat),
    "EXT-012": TaskHandler("EXT-012", _objective_completion),
    "EXT-013": TaskHandler("EXT-013", _cloud_inheritance),
}


def _cadence_bucket(cadence: str, now_sast: datetime, *, force: bool) -> str | None:
    if force:
        return "force:" + now_sast.strftime("%Y%m%d%H%M")
    if cadence == "hourly":
        return "hour:" + now_sast.strftime("%Y%m%d%H")
    if cadence == "every_6_hours" and now_sast.hour % 6 == 0:
        return "6h:" + now_sast.strftime("%Y%m%d%H")
    if cadence == "daily_0800_sast" and now_sast.hour == 8:
        return "day08:" + now_sast.strftime("%Y%m%d")
    if cadence == "daily_2200_sast" and now_sast.hour == 22:
        return "day22:" + now_sast.strftime("%Y%m%d")
    if cadence == "weekly_monday_0700_sast" and now_sast.weekday() == 0 and now_sast.hour == 7:
        return "week:" + now_sast.strftime("%G-W%V")
    return None


def load_previous_state(path: Path | None) -> dict[str, object]:
    if path is None or not path.is_file():
        return {
            "schema": STATE_SCHEMA,
            "generation": 0,
            "task_cursors": {},
            "last_cycle_id": "",
        }
    state = _read_json(path)
    if state.get("schema") != STATE_SCHEMA:
        raise ValueError("AUTOPILOT_OMEGA4_STATE_SCHEMA_MISMATCH")
    if not isinstance(state.get("task_cursors"), dict):
        raise ValueError("AUTOPILOT_OMEGA4_TASK_CURSORS_REQUIRED")
    return state


def run_cycle(
    *,
    root: Path,
    output_dir: Path,
    previous_state_path: Path | None = None,
    now_utc: datetime | None = None,
    host_provider: str = "unknown",
    host_run_id: str = "",
    source_sha: str = "",
    trigger: str = "manual",
    force: bool = False,
) -> tuple[dict[str, object], dict[str, object]]:
    root = root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    now_utc = now_utc or datetime.now(timezone.utc)
    now_sast = now_utc.astimezone(SAST)
    previous = load_previous_state(previous_state_path)
    previous_cursors = dict(previous.get("task_cursors", {}))
    next_cursors = dict(previous_cursors)

    registry_path = root / "scheduler/tasks.json"
    registry = _read_json(registry_path)
    tasks = list(registry.get("tasks", []))
    registry_by_id = {str(row.get("task_id")): row for row in tasks}

    cycle_identity = {
        "host_provider": host_provider,
        "host_run_id": host_run_id,
        "source_sha": source_sha,
        "trigger": trigger,
        "observed_at_utc": now_utc.isoformat(),
    }
    cycle_id = canonical_hash(cycle_identity)[:24]

    executed: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    held: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    for task_id, handler_spec in HANDLERS.items():
        task = registry_by_id.get(task_id)
        if task is None:
            failures.append({"task_id": task_id, "reason": "REGISTERED_TASK_MISSING"})
            continue
        if str(task.get("state")) != "READY":
            held.append(
                {
                    "task_id": task_id,
                    "state": task.get("state"),
                    "reason": "TASK_NOT_READY",
                }
            )
            continue
        bucket = _cadence_bucket(str(task.get("cadence", "")), now_sast, force=force)
        if bucket is None:
            skipped.append({"task_id": task_id, "reason": "CADENCE_NOT_DUE"})
            continue
        prior = previous_cursors.get(task_id, {})
        if isinstance(prior, dict) and prior.get("bucket") == bucket:
            skipped.append(
                {
                    "task_id": task_id,
                    "reason": "IDEMPOTENT_BUCKET_ALREADY_EXECUTED",
                    "bucket": bucket,
                }
            )
            continue
        if handler_spec.effect_class != "NO_EFFECT":
            held.append({"task_id": task_id, "reason": "RESIDENT_EFFECT_CLASS_NOT_ALLOWED"})
            continue
        try:
            result = handler_spec.handler(root, output_dir, task)
            result_hash = canonical_hash(result)
            row = {
                "task_id": task_id,
                "title": task.get("title"),
                "effect_class": handler_spec.effect_class,
                "bucket": bucket,
                "status": "EXECUTED_VERIFIED_LOCAL_RESULT",
                "result_sha256": result_hash,
            }
            executed.append(row)
            next_cursors[task_id] = {
                "bucket": bucket,
                "last_status": row["status"],
                "last_result_sha256": result_hash,
                "last_cycle_id": cycle_id,
            }
        except Exception as exc:
            failures.append(
                {
                    "task_id": task_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:500],
                }
            )

    known = set(HANDLERS)
    for task in tasks:
        task_id = str(task.get("task_id", ""))
        if task_id and task_id not in known and str(task.get("state")) == "READY":
            held.append(
                {
                    "task_id": task_id,
                    "title": task.get("title"),
                    "reason": "NO_RESIDENT_SAFE_HANDLER_ADMITTED",
                }
            )

    generation = int(previous.get("generation", 0)) + 1
    state = {
        "schema": STATE_SCHEMA,
        "generation": generation,
        "last_cycle_id": cycle_id,
        "last_observed_at_utc": now_utc.isoformat(),
        "task_cursors": next_cursors,
        "external_effect_authority": False,
    }
    state["state_sha256"] = canonical_hash(state)

    receipt = {
        "schema": SCHEMA,
        "cycle_id": cycle_id,
        "generation": generation,
        "observed_at_utc": now_utc.isoformat(),
        "observed_at_sast": now_sast.isoformat(),
        "host_provider": host_provider,
        "host_run_id": host_run_id,
        "source_sha": source_sha,
        "trigger": trigger,
        "previous_state_restored": previous_state_path is not None and previous_state_path.is_file(),
        "registry_sha256": _file_sha256(registry_path),
        "executed": executed,
        "skipped": skipped,
        "held": held,
        "failures": failures,
        "executed_count": len(executed),
        "failure_count": len(failures),
        "provider_mutation_attempted": False,
        "external_effect_attempted": False,
        "stable_promotion_authorized": False,
        "continuous_daemon_proven": False,
        "zero_compute_wait_proven": False,
        "full_autopilot_runtime_proven": False,
        "truth_boundary": (
            "This receipt proves only the NO_EFFECT/read-only handlers executed in this host cycle. "
            "Provider-host execution requires workflow readback; continuous residence, provider effects, "
            "zero-compute wait and full-autopilot status are not inferred."
        ),
        "next_state_sha256": state["state_sha256"],
    }
    receipt["receipt_sha256"] = canonical_hash(receipt)
    return receipt, state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output-dir", default="autopilot-omega4-output")
    parser.add_argument("--previous-state")
    parser.add_argument("--host-provider", default="unknown")
    parser.add_argument("--host-run-id", default="")
    parser.add_argument("--source-sha", default="")
    parser.add_argument("--trigger", default="manual")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    previous = Path(args.previous_state) if args.previous_state else None
    receipt, state = run_cycle(
        root=Path(args.root),
        output_dir=output_dir,
        previous_state_path=previous,
        host_provider=args.host_provider,
        host_run_id=args.host_run_id,
        source_sha=args.source_sha,
        trigger=args.trigger,
        force=args.force,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "resident-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "resident-state.json").write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "cycle_id": receipt["cycle_id"],
                "executed_count": receipt["executed_count"],
                "failure_count": receipt["failure_count"],
                "receipt_sha256": receipt["receipt_sha256"],
                "state_sha256": state["state_sha256"],
            },
            sort_keys=True,
        )
    )
    return 1 if receipt["failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
