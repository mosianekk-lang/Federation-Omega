from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FailurePreventionRule:
    failure_class: str
    trigger: str
    prevention: str
    regression_required: bool


RULES = (
    FailurePreventionRule(
        "WORKFLOW_ONLY_TEST_IN_WORKFLOW_FREE_EXPORT",
        "test references .github/workflows while executing inside Phoenix Core export",
        "workflow-dependent tests must skip or use a source-repository guard when workflow controls are intentionally absent",
        True,
    ),
    FailurePreventionRule(
        "OWNER_AS_MAINTENANCE_SCHEDULER",
        "owner is asked to continue/retry/repair a reversible self-resolvable internal fault",
        "route fault to Maintenance event and continue independent lanes",
        True,
    ),
    FailurePreventionRule(
        "LOCAL_GATE_GLOBAL_STALL",
        "provider or authority hold blocks unrelated internal work",
        "isolate affected lane and continue other ready lanes",
        True,
    ),
)


def failure_prevention_rules() -> tuple[FailurePreventionRule, ...]:
    return RULES
