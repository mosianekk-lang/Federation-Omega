"""Thin bootstrap helpers for Federation Governor Ω4."""
from __future__ import annotations
from .shim import ChatGovernorShim


def build_chat_shim(registry, version, chat_key, project_id, mission_id,
                    needed_tags, connectors, source_pointers=(), capsule_pointer=""):
    project = registry.project(project_id)
    mission = registry.mission(mission_id)
    if not project or not mission:
        raise KeyError("Project and mission must be registered first")
    specialists = registry.resolve_capabilities(needed_tags, max_results=4)
    shim = ChatGovernorShim(
        "BUBBLES_FEDERATION_GOVERNOR_OMEGA4", version, project_id, mission_id,
        mission["objective"], capsule_pointer, list(source_pointers), specialists,
        list(dict.fromkeys(connectors)), mission["next_gate"], project["matter_wall"])
    payload = shim.payload()
    registry.save_shim(chat_key, project_id, mission_id, payload, version)
    return payload
