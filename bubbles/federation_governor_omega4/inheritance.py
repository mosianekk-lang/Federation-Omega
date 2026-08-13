"""Project inheritance capsule helpers."""
from __future__ import annotations
import hashlib, json


def project_capsule(registry, version, project_id):
    project = registry.project(project_id)
    if not project:
        raise KeyError(project_id)
    active = [m for m in registry.missions(project_id)
              if m["current_stage"] not in ("COMPLETE", "ARCHIVED")]
    payload = {
        "governor": "BUBBLES_FEDERATION_GOVERNOR_OMEGA4",
        "version": version,
        "project_id": project_id,
        "matter_wall": project["matter_wall"],
        "active_missions": [m["mission_id"] for m in active],
        "load_pointers": ["project", "evidence", "missions", "capabilities"],
    }
    payload["sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return payload
