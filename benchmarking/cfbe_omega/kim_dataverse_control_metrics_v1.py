from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class MissionEpisode:
    episode_id: str
    verified_complete: bool
    owner_interventions: int
    avoidable_owner_interventions: int
    maintenance_events: int
    maintenance_self_resolved: int
    recovery_events: int
    recovery_self_resolved: int
    chat_turn_required_for_continuation: bool
    provider_failure_caused_global_stall: bool


@dataclass(frozen=True)
class InstitutionalMetrics:
    episode_count: int
    verified_completion_rate: float
    owner_intervention_rate: float
    avoidable_owner_intervention_rate: float
    maintenance_self_resolution_rate: float
    recovery_self_resolution_rate: float
    chat_dependency_rate: float
    global_stall_rate: float


def aggregate_institutional_metrics(episodes: Sequence[MissionEpisode]) -> InstitutionalMetrics:
    ids = [episode.episode_id for episode in episodes]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate episode_id")
    for episode in episodes:
        for value in (
            episode.owner_interventions,
            episode.avoidable_owner_interventions,
            episode.maintenance_events,
            episode.maintenance_self_resolved,
            episode.recovery_events,
            episode.recovery_self_resolved,
        ):
            if value < 0:
                raise ValueError("episode counts must be non-negative")
        if episode.avoidable_owner_interventions > episode.owner_interventions:
            raise ValueError("avoidable interventions cannot exceed total interventions")
        if episode.maintenance_self_resolved > episode.maintenance_events:
            raise ValueError("maintenance self-resolved cannot exceed maintenance events")
        if episode.recovery_self_resolved > episode.recovery_events:
            raise ValueError("recovery self-resolved cannot exceed recovery events")

    count = len(episodes)
    total_owner = sum(item.owner_interventions for item in episodes)
    total_avoidable = sum(item.avoidable_owner_interventions for item in episodes)
    total_maintenance = sum(item.maintenance_events for item in episodes)
    total_maintenance_resolved = sum(item.maintenance_self_resolved for item in episodes)
    total_recovery = sum(item.recovery_events for item in episodes)
    total_recovery_resolved = sum(item.recovery_self_resolved for item in episodes)
    return InstitutionalMetrics(
        episode_count=count,
        verified_completion_rate=round(sum(item.verified_complete for item in episodes) / max(count, 1), 6),
        owner_intervention_rate=round(total_owner / max(count, 1), 6),
        avoidable_owner_intervention_rate=round(total_avoidable / max(total_owner, 1), 6),
        maintenance_self_resolution_rate=round(total_maintenance_resolved / max(total_maintenance, 1), 6),
        recovery_self_resolution_rate=round(total_recovery_resolved / max(total_recovery, 1), 6),
        chat_dependency_rate=round(sum(item.chat_turn_required_for_continuation for item in episodes) / max(count, 1), 6),
        global_stall_rate=round(sum(item.provider_failure_caused_global_stall for item in episodes) / max(count, 1), 6),
    )
