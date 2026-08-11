from pathlib import Path
from datetime import datetime, timezone
import json

ROOT = Path("virtual-org")
STATUS = ROOT / "status"
RUNTIME = ROOT / "runtime"
STATUS.mkdir(parents=True, exist_ok=True)
RUNTIME.mkdir(parents=True, exist_ok=True)

now = datetime.now(timezone.utc).isoformat()
registry_path = ROOT / "lane-registry.json"
registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {"lanes": []}

active = [x for x in registry.get("lanes", []) if x.get("state") in {"READY", "RESUMABLE", "ACTIVE", "CHECKPOINTED"}]
blocked = [x for x in registry.get("lanes", []) if x.get("state") == "BLOCKED"]
ranked = sorted(active, key=lambda x: -float(x.get("priority", 0)))
top = ranked[0] if ranked else None

cycle = {
    "timestamp": now,
    "active_count": len(active),
    "blocked_count": len(blocked),
    "top_lane": top.get("lane_id") if top else None,
    "top_next_action": top.get("next_action") if top else None,
    "state": "CYCLE_COMPLETE"
}
payload = json.dumps(cycle, indent=2)
(STATUS / "latest-cycle.json").write_text(payload, encoding="utf-8")
(RUNTIME / f"cycle-{now.replace(':', '-')}.json").write_text(payload, encoding="utf-8")

summary = f"""# EvidenceOps Virtual Organization Status

Updated: {now}

- Active/resumable lanes: {len(active)}
- Blocked lanes: {len(blocked)}
- Highest-value lane: {cycle['top_lane']}
- Next action: {cycle['top_next_action']}
"""
(STATUS / "latest-brief.md").write_text(summary, encoding="utf-8")
