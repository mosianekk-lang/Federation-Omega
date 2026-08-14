from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Tuple


CREATOR_MODE_CONTRACT_VERSION = "1.0.1"


class WorkClass(str, Enum):
    CREATIVE = "CREATIVE"
    JUDGMENT = "JUDGMENT"
    CONSEQUENTIAL_APPROVAL = "CONSEQUENTIAL_APPROVAL"
    FACT_ONLY_USER_KNOWS = "FACT_ONLY_USER_KNOWS"
    SYSTEM_DEBUG = "SYSTEM_DEBUG"
    TOOL_ROUTING = "TOOL_ROUTING"
    RETRY_RECOVERY = "RETRY_RECOVERY"
    QA_VALIDATION = "QA_VALIDATION"
    CONTINUITY = "CONTINUITY"
    RESEARCH_RETRIEVAL = "RESEARCH_RETRIEVAL"
    ORGANISATION = "ORGANISATION"
    REPETITIVE_TRANSFORMATION = "REPETITIVE_TRANSFORMATION"


class BurdenOwner(str, Enum):
    KIM = "KIM"
    SYSTEM = "SYSTEM"
    SHARED = "SHARED"


@dataclass(frozen=True)
class WorkItem:
    description: str
    work_class: WorkClass
    consequential: bool = False
    system_can_execute: bool = True
    user_has_unique_information: bool = False


@dataclass(frozen=True)
class RoutedWorkItem:
    description: str
    work_class: WorkClass
    owner: BurdenOwner
    reason: str


@dataclass(frozen=True)
class CreatorModeReport:
    routed_items: Tuple[RoutedWorkItem, ...]
    system_absorbed_count: int
    user_required_count: int
    shared_count: int
    avoidable_user_debugging_count: int
    creator_focus_protected: bool


SYSTEM_FIRST_CLASSES = {
    WorkClass.SYSTEM_DEBUG,
    WorkClass.TOOL_ROUTING,
    WorkClass.RETRY_RECOVERY,
    WorkClass.QA_VALIDATION,
    WorkClass.CONTINUITY,
    WorkClass.RESEARCH_RETRIEVAL,
    WorkClass.ORGANISATION,
    WorkClass.REPETITIVE_TRANSFORMATION,
}

USER_FIRST_CLASSES = {
    WorkClass.CREATIVE,
    WorkClass.JUDGMENT,
    WorkClass.CONSEQUENTIAL_APPROVAL,
    WorkClass.FACT_ONLY_USER_KNOWS,
}


class ForestFirstCreatorMode:
    """Route operational burden away from the user by default.

    Creator Mode treats Kim as mission owner/creator rather than systems operator.
    Safe, authorised, repeatable technical work belongs to the system. Kim is
    interrupted mainly for creative direction, personal facts only he can supply,
    teach-back/judgment, and consequential approvals.

    This module routes burden only. It does not expand tool authority, provider
    permissions, filing rights, or the system's ability to obtain facts that only
    the user knows.
    """

    def route(self, items: Iterable[WorkItem]) -> CreatorModeReport:
        routed: list[RoutedWorkItem] = []
        avoidable_debug = 0

        for item in items:
            if item.consequential or item.work_class is WorkClass.CONSEQUENTIAL_APPROVAL:
                routed.append(RoutedWorkItem(
                    description=item.description,
                    work_class=item.work_class,
                    owner=BurdenOwner.KIM,
                    reason="Consequential action remains owner-reserved.",
                ))
                continue

            if item.user_has_unique_information or item.work_class is WorkClass.FACT_ONLY_USER_KNOWS:
                routed.append(RoutedWorkItem(
                    description=item.description,
                    work_class=item.work_class,
                    owner=BurdenOwner.KIM,
                    reason="The required fact or lived judgment is uniquely held by the user.",
                ))
                continue

            if item.work_class in SYSTEM_FIRST_CLASSES and item.system_can_execute:
                routed.append(RoutedWorkItem(
                    description=item.description,
                    work_class=item.work_class,
                    owner=BurdenOwner.SYSTEM,
                    reason="Safe repeatable operational work should be absorbed by the system.",
                ))
                if item.work_class in {
                    WorkClass.SYSTEM_DEBUG,
                    WorkClass.TOOL_ROUTING,
                    WorkClass.RETRY_RECOVERY,
                    WorkClass.QA_VALIDATION,
                    WorkClass.CONTINUITY,
                }:
                    avoidable_debug += 1
                continue

            if item.work_class in USER_FIRST_CLASSES:
                routed.append(RoutedWorkItem(
                    description=item.description,
                    work_class=item.work_class,
                    owner=BurdenOwner.KIM,
                    reason="This is creative direction or human judgment, not a systems burden.",
                ))
                continue

            if item.system_can_execute:
                routed.append(RoutedWorkItem(
                    description=item.description,
                    work_class=item.work_class,
                    owner=BurdenOwner.SYSTEM,
                    reason="No owner-only dependency is present and the system can execute safely.",
                ))
            else:
                routed.append(RoutedWorkItem(
                    description=item.description,
                    work_class=item.work_class,
                    owner=BurdenOwner.SHARED,
                    reason="System execution is unavailable; minimise the user's required contribution.",
                ))

        system_count = sum(r.owner is BurdenOwner.SYSTEM for r in routed)
        user_count = sum(r.owner is BurdenOwner.KIM for r in routed)
        shared_count = sum(r.owner is BurdenOwner.SHARED for r in routed)
        creator_focus_protected = not any(
            r.owner is BurdenOwner.KIM and r.work_class in SYSTEM_FIRST_CLASSES
            for r in routed
        )

        return CreatorModeReport(
            routed_items=tuple(routed),
            system_absorbed_count=system_count,
            user_required_count=user_count,
            shared_count=shared_count,
            avoidable_user_debugging_count=avoidable_debug,
            creator_focus_protected=creator_focus_protected,
        )


__all__ = [
    "BurdenOwner",
    "CREATOR_MODE_CONTRACT_VERSION",
    "CreatorModeReport",
    "ForestFirstCreatorMode",
    "RoutedWorkItem",
    "WorkClass",
    "WorkItem",
]
