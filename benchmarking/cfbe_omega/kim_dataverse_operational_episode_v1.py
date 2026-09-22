from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json


@dataclass(frozen=True)
class OperationalEpisode:
    episode_id: str
    mission_id: str
    source_sha: str
    started_without_chat_dependency: bool
    resumed_cross_process: bool
    maintenance_self_resolved: bool
    recovery_self_resolved: bool
    owner_interruption_required: bool
    owner_interruption_irreducible: bool
    verified_complete: bool
    proof_refs: tuple[str, ...]


def validate_operational_episode(episode: OperationalEpisode) -> str:
    if not episode.episode_id or not episode.mission_id or len(episode.source_sha) < 7:
        raise ValueError("episode identity is incomplete")
    if episode.verified_complete and not episode.proof_refs:
        raise ValueError("verified completion requires proof_refs")
    if episode.owner_interruption_required and not episode.owner_interruption_irreducible:
        raise ValueError("avoidable owner interruption violates Level 7 operating contract")
    payload = {**episode.__dict__, "proof_refs": sorted(set(episode.proof_refs)), "external_effect": False}
    return "sha256:" + sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
