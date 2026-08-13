"""Federation health correlation."""
from __future__ import annotations
import time


class FederationWatchdog:
    def __init__(self, registry):
        self.registry = registry

    def inspect(self, idle_seconds=1080):
        current = time.time()
        findings = []
        missions = self.registry.missions()
        grouped = {}
        for mission in missions:
            key = (mission["project_id"], mission["objective"].strip().lower())
            grouped.setdefault(key, []).append(mission)
            if mission["executable_next"] and current - float(mission["updated_at"]) >= idle_seconds:
                findings.append({"type":"IDLE_EXECUTABLE_MISSION","project_id":mission["project_id"],"mission_id":mission["mission_id"]})
        for (project_id, _), items in grouped.items():
            if len(items) > 1:
                findings.append({"type":"POSSIBLE_DUPLICATE_MISSIONS","project_id":project_id,"mission_ids":sorted(item["mission_id"] for item in items)})
        return {"federation_health":"ATTENTION" if findings else "HEALTHY","findings":findings,"mission_count":len(missions),"scope":"registered governed missions only"}
