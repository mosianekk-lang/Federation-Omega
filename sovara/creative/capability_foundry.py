from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class SkillDomain(str, Enum):
    CREATIVE = "CREATIVE"
    SOFTWARE_ENGINEERING = "SOFTWARE_ENGINEERING"
    AUTOMATION = "AUTOMATION"
    CLOUD_RUNTIME = "CLOUD_RUNTIME"
    MEDIA_PIPELINE = "MEDIA_PIPELINE"
    DATA_ENGINEERING = "DATA_ENGINEERING"
    MODEL_SERVING = "MODEL_SERVING"
    OBSERVABILITY = "OBSERVABILITY"
    SECURITY_PRIVACY = "SECURITY_PRIVACY"
    QA_TESTING = "QA_TESTING"


class BuildStrategy(str, Enum):
    REUSE = "REUSE"
    EXTEND = "EXTEND"
    COMPOSE = "COMPOSE"
    INVENT = "INVENT"


class AdmissionState(str, Enum):
    IDEA = "IDEA"
    SOURCE_CANDIDATE = "SOURCE_CANDIDATE"
    TESTED = "TESTED"
    CI_ADMITTED = "CI_ADMITTED"
    DEPLOYMENT_AUTHORIZED = "DEPLOYMENT_AUTHORIZED"
    PROVIDER_PROVEN = "PROVIDER_PROVEN"


@dataclass(frozen=True, slots=True)
class CapabilityCandidate:
    capability_id: str
    outcome: str
    skill_domains: tuple[SkillDomain, ...]
    strategy: BuildStrategy
    reused_capabilities: tuple[str, ...]
    source_changes_required: bool
    provider_effect_required: bool
    authority_ceiling: str = "A1_INTERNAL"
    admission_state: AdmissionState = AdmissionState.IDEA


_FEDERATION_REUSE_ORDER = (
    "SOVARA_PROVIDER_EXECUTION",
    "SOVARA_PROVIDER_RECOVERY",
    "FORMATION_OMEGA",
    "CFBE_OMEGA",
    "FAILURE_WIN_V2",
    "OMEGA_AUTOFIX",
    "EVIDENCEOPS_ALGORITHM_FOUNDRY",
    "PROOFOS_OMEGA",
    "BUBBLES",
    "SENTINEL_OMEGA",
    "LIVING_STATE",
    "UNIVERSAL_EFFECT_PROOF",
)


def plan_capability(
    *,
    capability_id: str,
    outcome: str,
    skill_domains: Iterable[SkillDomain],
    available_capabilities: Iterable[str],
    provider_effect_required: bool = False,
) -> CapabilityCandidate:
    """Compile a missing technical skill into a proof-gated build candidate.

    This function does not write source, deploy infrastructure, expand authority,
    or perform provider effects. It chooses a reuse-first engineering strategy
    and makes the remaining build requirement explicit.
    """

    cid = capability_id.strip()
    goal = outcome.strip()
    if not cid:
        raise ValueError("capability_id is required")
    if not goal:
        raise ValueError("outcome is required")

    domains = tuple(dict.fromkeys(skill_domains))
    if not domains:
        raise ValueError("at least one skill domain is required")

    available = {item.strip() for item in available_capabilities if item.strip()}
    reused = tuple(item for item in _FEDERATION_REUSE_ORDER if item in available)

    if len(reused) >= 3:
        strategy = BuildStrategy.COMPOSE
    elif reused:
        strategy = BuildStrategy.EXTEND
    else:
        strategy = BuildStrategy.INVENT

    return CapabilityCandidate(
        capability_id=cid,
        outcome=goal,
        skill_domains=domains,
        strategy=strategy,
        reused_capabilities=reused,
        source_changes_required=True,
        provider_effect_required=provider_effect_required,
    )


def can_deploy(candidate: CapabilityCandidate) -> bool:
    """Deployment requires explicit admission and an authority transition."""

    return candidate.admission_state in {
        AdmissionState.DEPLOYMENT_AUTHORIZED,
        AdmissionState.PROVIDER_PROVEN,
    }
