from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import hashlib
import re
from typing import Iterable


class BoundaryClass(StrEnum):
    UNRESOLVED_ENGINEERING_BUILD = "UNRESOLVED_ENGINEERING_BUILD"
    WORKAROUND_ACTIVE_BUILD_OPEN = "WORKAROUND_ACTIVE_BUILD_OPEN"
    BLOCKED_DEPENDENCY_ACTIVE = "BLOCKED_DEPENDENCY_ACTIVE"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"
    CAPABILITY_REDISCOVERY_TRIGGER = "CAPABILITY_REDISCOVERY_TRIGGER"


class LifecycleState(StrEnum):
    DETECTED = "DETECTED"
    SPECIFIED = "SPECIFIED"
    WORKAROUND_ACTIVE = "WORKAROUND_ACTIVE"
    BUILD_READY = "BUILD_READY"
    IMPLEMENTING = "IMPLEMENTING"
    TESTING = "TESTING"
    VERIFIED = "VERIFIED"
    DEPLOYED = "DEPLOYED"
    RETIRED = "RETIRED"
    BLOCKED_DEPENDENCY = "BLOCKED_DEPENDENCY"
    QUARANTINED = "QUARANTINED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED_UNSAFE = "REJECTED_UNSAFE"


BOUNDARY_PATTERNS: tuple[str, ...] = (
    r"\bunsupported\b",
    r"\bunavailable\b",
    r"\bblocked\b",
    r"\bplatform (?:limit|boundary)\b",
    r"\bmissing (?:tool|api|connector|permission|runtime|capability)\b",
    r"\binaccessible (?:surface|resource)\b",
    r"\btimeout\b",
    r"\bquota\b",
    r"\bcontext limit\b",
    r"\bautomation gap\b",
    r"\bruntime gap\b",
    r"\bprovider gate\b",
    r"\bschema mismatch\b",
    r"\bstale credential\b",
    r"\bproof gap\b",
    r"\bmanual handoff\b",
    r"\bfailed invocation\b",
)

ENGINE_IDS: tuple[str, ...] = (
    "FEDERATION_OMEGA_CORE",
    "FORMATION_ENGINE",
    "ALPHA_TO_OMEGA_FOUNDRY",
    "OMEGA_MAX",
    "EVIDENCEOPS",
    "MODISA",
    "SECONDARY_BRAIN",
    "ARCHON_KDL",
    "CLOUDOPS",
    "AIU",
    "NEXUS_CODEX",
    "FEVX",
    "AEGIS_RED_TEAM",
    "HEARTBEAT_MESH",
    "MULTI_PATH_ENGINE",
    "FORMATION_INNOVATION_ENGINE",
    "AUTO_TRIGGER_GRAPH",
    "WORKSTREAM_GOVERNOR",
    "PROOF_AND_LEARNING_FABRIC",
)


@dataclass(frozen=True)
class BoundaryEvent:
    statement: str
    desired_capability: str
    owning_engine: str = "FEDERATION_OMEGA_CORE"
    workaround: str = ""
    dependency: str = ""
    source_trigger: str = "runtime-observation"


@dataclass(frozen=True)
class BuildTrigger:
    build_id: str
    classification: str
    gap_statement: str
    desired_capability: str
    owning_engine: str
    lifecycle_state: str
    dependencies: tuple[str, ...]
    interim_workaround: str
    next_executable_action: str
    acceptance_criteria: tuple[str, ...]
    recheck_triggers: tuple[str, ...]
    authority_ceiling: str = "A1_INTERNAL"
    external_effect: bool = False
    source_trigger: str = "runtime-observation"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _normalise(value: str) -> str:
    return " ".join(value.strip().split())


def is_boundary_statement(statement: str) -> bool:
    normalised = _normalise(statement).lower()
    return any(re.search(pattern, normalised) for pattern in BOUNDARY_PATTERNS)


def stable_build_id(event: BoundaryEvent) -> str:
    canonical = "|".join(
        (
            _normalise(event.statement).lower(),
            _normalise(event.desired_capability).lower(),
            _normalise(event.owning_engine).upper(),
        )
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12].upper()
    return f"BUILD-AO-FED-{digest}"


def classify_boundary(
    event: BoundaryEvent,
    *,
    workaround_active: bool | None = None,
    capability_changed: bool = False,
    completion_claimed: bool = False,
) -> BoundaryClass:
    if capability_changed:
        return BoundaryClass.CAPABILITY_REDISCOVERY_TRIGGER
    if completion_claimed:
        return BoundaryClass.VERIFICATION_REQUIRED
    if event.dependency:
        return BoundaryClass.BLOCKED_DEPENDENCY_ACTIVE
    active = bool(event.workaround) if workaround_active is None else workaround_active
    if active:
        return BoundaryClass.WORKAROUND_ACTIVE_BUILD_OPEN
    return BoundaryClass.UNRESOLVED_ENGINEERING_BUILD


def create_build_trigger(
    event: BoundaryEvent,
    *,
    existing_capabilities: Iterable[str] = (),
    workaround_active: bool | None = None,
    capability_changed: bool = False,
    completion_claimed: bool = False,
) -> BuildTrigger:
    if event.owning_engine not in ENGINE_IDS:
        raise ValueError(f"Unknown Federation engine: {event.owning_engine}")
    if not _normalise(event.desired_capability):
        raise ValueError("desired_capability is required")

    classification = classify_boundary(
        event,
        workaround_active=workaround_active,
        capability_changed=capability_changed,
        completion_claimed=completion_claimed,
    )
    capabilities = tuple(sorted({_normalise(item) for item in existing_capabilities if _normalise(item)}))
    dependencies = tuple(item for item in (_normalise(event.dependency),) if item)

    if classification is BoundaryClass.CAPABILITY_REDISCOVERY_TRIGGER:
        next_action = "Re-discover affected capabilities and run the shortest reversible canary."
        state = LifecycleState.TESTING
    elif classification is BoundaryClass.VERIFICATION_REQUIRED:
        next_action = "Run the acceptance harness and obtain independent target readback."
        state = LifecycleState.TESTING
    elif classification is BoundaryClass.BLOCKED_DEPENDENCY_ACTIVE:
        next_action = "Isolate the dependency, activate the best safe workaround, and build or select a materially different route."
        state = LifecycleState.BLOCKED_DEPENDENCY
    elif classification is BoundaryClass.WORKAROUND_ACTIVE_BUILD_OPEN:
        next_action = "Keep the workaround active while implementing and testing the target capability."
        state = LifecycleState.WORKAROUND_ACTIVE
    else:
        next_action = "Search the Federation capability estate, specify the minimum complete build, and create its first test fixture."
        state = LifecycleState.DETECTED

    reuse_note = (
        f" Reuse candidates: {', '.join(capabilities)}."
        if capabilities
        else " No verified reuse candidate was supplied; capability discovery remains mandatory."
    )

    return BuildTrigger(
        build_id=stable_build_id(event),
        classification=classification.value,
        gap_statement=_normalise(event.statement),
        desired_capability=_normalise(event.desired_capability),
        owning_engine=event.owning_engine,
        lifecycle_state=state.value,
        dependencies=dependencies,
        interim_workaround=_normalise(event.workaround),
        next_executable_action=next_action + reuse_note,
        acceptance_criteria=(
            "Executable implementation exists.",
            "Healthy-path and failure-path tests pass.",
            "Security, privacy, idempotency and rollback controls pass.",
            "Independent or provider-native readback proves the exact target state.",
        ),
        recheck_triggers=(
            "tool or connector discovery",
            "provider capability or schema change",
            "permission or credential state change",
            "failed invocation",
            "checkpoint or substantive cycle",
        ),
        source_trigger=_normalise(event.source_trigger),
    )


def validate_promotion(trigger: BuildTrigger, target_state: LifecycleState, evidence: Iterable[str]) -> None:
    evidence_set = {_normalise(item).lower() for item in evidence if _normalise(item)}
    if target_state is LifecycleState.VERIFIED:
        required = {"implementation", "tests", "acceptance", "readback"}
    elif target_state is LifecycleState.DEPLOYED:
        required = {"implementation", "tests", "acceptance", "readback", "runtime", "health", "persistence", "rollback"}
    else:
        return
    missing = sorted(required - evidence_set)
    if missing:
        raise ValueError(f"Promotion to {target_state.value} blocked; missing evidence: {', '.join(missing)}")
