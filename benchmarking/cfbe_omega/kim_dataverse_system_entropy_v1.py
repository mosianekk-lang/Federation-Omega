from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence


class EntropyAction(str, Enum):
    RETAIN = "RETAIN"
    MERGE_REVIEW = "MERGE_REVIEW"
    CONVERT_TO_POLICY_REVIEW = "CONVERT_TO_POLICY_REVIEW"
    CONVERT_TO_DYNAMIC_ROLE_REVIEW = "CONVERT_TO_DYNAMIC_ROLE_REVIEW"
    RETIRE_REVIEW = "RETIRE_REVIEW"


@dataclass(frozen=True)
class SystemShape:
    system_id: str
    responsibilities: tuple[str, ...]
    has_scheduler: bool
    has_memory_root: bool
    has_provider_executor: bool
    has_authority_plane: bool
    reuse_count: int
    observed_value: bool
    permanent_agent: bool = False


@dataclass(frozen=True)
class EntropyDecision:
    system_id: str
    action: EntropyAction
    rationale: str
    destructive_action_authorized: bool = False


def evaluate_system_entropy(systems: Sequence[SystemShape]) -> tuple[EntropyDecision, ...]:
    ids = [item.system_id for item in systems]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate system_id")
    responsibility_sets = {item.system_id: set(item.responsibilities) for item in systems}
    decisions = []
    for system in systems:
        overlaps = []
        for other in systems:
            if other.system_id == system.system_id:
                continue
            union = responsibility_sets[system.system_id] | responsibility_sets[other.system_id]
            if union:
                overlaps.append(len(responsibility_sets[system.system_id] & responsibility_sets[other.system_id]) / len(union))
        max_overlap = max(overlaps, default=0.0)
        duplicated_control_plane = sum(
            (system.has_scheduler, system.has_memory_root, system.has_provider_executor, system.has_authority_plane)
        ) >= 2
        if max_overlap >= 0.9:
            action = EntropyAction.MERGE_REVIEW
            rationale = "high responsibility overlap"
        elif system.permanent_agent and system.reuse_count <= 1 and not system.observed_value:
            action = EntropyAction.CONVERT_TO_DYNAMIC_ROLE_REVIEW
            rationale = "permanent agent has low reuse and no observed value"
        elif not system.observed_value and system.reuse_count == 0:
            action = EntropyAction.RETIRE_REVIEW
            rationale = "unused system lacks observed value"
        elif duplicated_control_plane:
            action = EntropyAction.CONVERT_TO_POLICY_REVIEW
            rationale = "system shape risks duplicate control-plane ownership"
        else:
            action = EntropyAction.RETAIN
            rationale = "distinct responsibility with retained value/reuse"
        decisions.append(EntropyDecision(system.system_id, action, rationale, False))
    return tuple(sorted(decisions, key=lambda item: item.system_id))


def entropy_summary(decisions: Sequence[EntropyDecision]) -> Mapping[str, int]:
    return {action.value: sum(item.action == action for item in decisions) for action in EntropyAction}
