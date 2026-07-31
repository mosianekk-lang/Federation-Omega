from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import json
from typing import Any

ROOT = Path("virtual-org")
STATUS = ROOT / "status"
RUNTIME = ROOT / "runtime"

EXECUTABLE_STATES = {"READY", "RESUMABLE", "ACTIVE", "TEST_PASSED"}
VISIBLE_STATES = EXECUTABLE_STATES | {"CHECKPOINTED"}


def _has_approval_gate(lane: dict[str, Any]) -> bool:
    value = lane.get("approval_gate")
    return isinstance(value, str) and bool(value.strip())


def _is_safe_executable(lane: dict[str, Any]) -> bool:
    state = lane.get("state")
    if state == "BLOCKED" or _has_approval_gate(lane):
        return False
    if state in EXECUTABLE_STATES:
        return bool(lane.get("next_action"))
    return state == "CHECKPOINTED" and bool(lane.get("next_action"))


def select_cycle(registry: dict[str, Any], now: str) -> dict[str, Any]:
    lanes = registry.get("lanes", [])
    visible = [lane for lane in lanes if lane.get("state") in VISIBLE_STATES]
    blocked = [lane for lane in lanes if lane.get("state") == "BLOCKED"]
    approval_checkpointed = [lane for lane in visible if _has_approval_gate(lane)]
    executable = [lane for lane in visible if _is_safe_executable(lane)]
    ranked = sorted(
        executable,
        key=lambda lane: (-float(lane.get("priority", 0)), str(lane.get("lane_id", ""))),
    )
    top = ranked[0] if ranked else None
    return {
        "timestamp": now,
        "visible_lane_count": len(visible),
        "safe_executable_count": len(executable),
        "approval_checkpoint_count": len(approval_checkpointed),
        "blocked_count": len(blocked),
        "top_safe_lane": top.get("lane_id") if top else None,
        "top_next_action": top.get("next_action") if top else None,
        "selection_rule": "highest priority among safe executable lanes; approval-gated and blocked lanes remain visible but cannot displace executable work",
        "state": "CYCLE_COMPLETE",
    }


def main() -> int:
    STATUS.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    registry_path = ROOT / "lane-registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {"lanes": []}
    cycle = select_cycle(registry, now)
    payload = json.dumps(cycle, indent=2)
    (STATUS / "latest-cycle.json").write_text(payload, encoding="utf-8")
    (RUNTIME / f"cycle-{now.replace(':', '-')}.json").write_text(payload, encoding="utf-8")

    summary = f"""# EvidenceOps Virtual Organization Status

Updated: {now}

- Visible active/resumable/checkpointed lanes: {cycle['visible_lane_count']}
- Safe executable lanes: {cycle['safe_executable_count']}
- Approval-checkpointed lanes: {cycle['approval_checkpoint_count']}
- Blocked lanes: {cycle['blocked_count']}
- Highest-value safe executable lane: {cycle['top_safe_lane']}
- Next action: {cycle['top_next_action']}
"""
    (STATUS / "latest-brief.md").write_text(summary, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
