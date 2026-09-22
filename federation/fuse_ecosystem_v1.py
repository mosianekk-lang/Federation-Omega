from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping

from federation.capability_truth_v1 import (
    AdapterRouteDecision,
    CapabilityCurrentnessFabric,
    CapabilityRouteRequirement,
    Maturity,
    PrivacyClass,
)


class EcosystemPlane(str, Enum):
    EXPERIENCE = "EXPERIENCE"
    INTELLIGENCE = "INTELLIGENCE"
    RESEARCH = "RESEARCH"
    EXECUTION = "EXECUTION"
    CODE = "CODE"
    CREATIVE = "CREATIVE"
    DATA = "DATA"
    KNOWLEDGE = "KNOWLEDGE"
    WORKFLOW = "WORKFLOW"
    COMMUNICATION = "COMMUNICATION"
    DEVICE = "DEVICE"
    MEMORY = "MEMORY"
    SECURITY = "SECURITY"
    OBSERVABILITY = "OBSERVABILITY"
    MARKETPLACE = "MARKETPLACE"


@dataclass(frozen=True, slots=True)
class EcosystemServiceSpec:
    service_id: str
    plane: EcosystemPlane
    required_capabilities: tuple[str, ...]
    optional_capabilities: tuple[str, ...] = ()
    required_maturity: Maturity = Maturity.BOUND
    min_failure_domains: int = 1
    proof_required: bool = True
    description: str = ""

    def validate(self) -> "EcosystemServiceSpec":
        if not self.service_id.strip():
            raise ValueError("ECOSYSTEM_SERVICE_ID_REQUIRED")
        if not self.required_capabilities:
            raise ValueError("ECOSYSTEM_REQUIRED_CAPABILITY_REQUIRED")
        if self.min_failure_domains < 1:
            raise ValueError("ECOSYSTEM_FAILURE_DOMAIN_COUNT_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class EcosystemMissionSpec:
    mission_id: str
    service_ids: tuple[str, ...]
    authority_class: str = "A1_INTERNAL"
    effect_class: str = "NO_EFFECT"
    privacy_class: PrivacyClass = PrivacyClass.INTERNAL
    independent_backup_required: bool = False
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> "EcosystemMissionSpec":
        if not self.mission_id.strip():
            raise ValueError("ECOSYSTEM_MISSION_ID_REQUIRED")
        if not self.service_ids:
            raise ValueError("ECOSYSTEM_MISSION_SERVICE_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class CapabilitySelection:
    capability_id: str
    primary_adapter: str
    provider: str
    backup_adapters: tuple[str, ...]
    failure_domains: tuple[str, ...]
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EcosystemPlan:
    mission_id: str
    service_ids: tuple[str, ...]
    selections: tuple[CapabilitySelection, ...]
    missing_capabilities: tuple[str, ...]
    proof_required: bool
    authority_class: str
    effect_class: str
    privacy_class: PrivacyClass

    @property
    def executable(self) -> bool:
        return not self.missing_capabilities


def _eligible_unique_failure_domains(
    ranked: Iterable[AdapterRouteDecision],
    observations_by_adapter: Mapping[str, object],
) -> tuple[AdapterRouteDecision, ...]:
    selected: list[AdapterRouteDecision] = []
    seen_domains: set[str] = set()
    for decision in ranked:
        if not decision.eligible:
            continue
        obs = observations_by_adapter.get(decision.adapter_id)
        domain = getattr(obs, "failure_domain", "") or f"adapter:{decision.adapter_id}"
        if domain in seen_domains:
            continue
        seen_domains.add(domain)
        selected.append(decision)
    return tuple(selected)


class FuseEcosystemKernel:
    """Mission facade over existing FUSE routing, currentness and execution controls.

    This class does not execute provider actions and does not grant authority.
    It compiles provider-neutral ecosystem services into qualified capability
    selections. Alpha-Omega/FCOA remain the execution controllers.
    """

    def __init__(
        self,
        fabric: CapabilityCurrentnessFabric,
        services: Mapping[str, EcosystemServiceSpec] | None = None,
    ):
        self.fabric = fabric
        self.services = dict(services or FUSE_ECOSYSTEM_SERVICES)
        for spec in self.services.values():
            spec.validate()

    def compile(self, mission: EcosystemMissionSpec, *, now: str) -> EcosystemPlan:
        mission.validate()
        required_specs: list[EcosystemServiceSpec] = []
        for service_id in mission.service_ids:
            spec = self.services.get(service_id)
            if spec is None:
                raise ValueError(f"ECOSYSTEM_SERVICE_UNKNOWN:{service_id}")
            required_specs.append(spec)

        selections: list[CapabilitySelection] = []
        missing: list[str] = []
        proof_required = False

        for spec in required_specs:
            proof_required = proof_required or spec.proof_required
            required_domains = max(
                spec.min_failure_domains,
                2 if mission.independent_backup_required else 1,
            )
            for capability_id in spec.required_capabilities:
                req = CapabilityRouteRequirement(
                    capability_id=capability_id,
                    required_maturity=spec.required_maturity,
                    authority_class=mission.authority_class,
                    effect_class=mission.effect_class,
                    privacy_class=mission.privacy_class,
                    require_callable=True,
                )
                ranked = self.fabric.rank(req, now=now)
                observations = {
                    item.adapter_id: item
                    for item in self.fabric.observations_for(capability_id)
                }
                diverse = _eligible_unique_failure_domains(ranked, observations)
                if len(diverse) < required_domains:
                    missing.append(capability_id)
                    continue

                primary = diverse[0]
                primary_obs = observations[primary.adapter_id]
                backups = tuple(x.adapter_id for x in diverse[1:])
                domains = tuple(
                    (observations[x.adapter_id].failure_domain or f"adapter:{x.adapter_id}")
                    for x in diverse
                )
                selections.append(
                    CapabilitySelection(
                        capability_id=capability_id,
                        primary_adapter=primary.adapter_id,
                        provider=primary.provider,
                        backup_adapters=backups,
                        failure_domains=domains,
                        reasons=("CAPABILITY_TRUTH_CURRENTNESS_QUALIFIED",),
                    )
                )

        return EcosystemPlan(
            mission_id=mission.mission_id,
            service_ids=mission.service_ids,
            selections=tuple(selections),
            missing_capabilities=tuple(sorted(set(missing))),
            proof_required=proof_required,
            authority_class=mission.authority_class,
            effect_class=mission.effect_class,
            privacy_class=mission.privacy_class,
        )


FUSE_ECOSYSTEM_SERVICES: dict[str, EcosystemServiceSpec] = {
    "research.deep": EcosystemServiceSpec(
        "research.deep",
        EcosystemPlane.RESEARCH,
        ("research.web", "research.enterprise_knowledge", "citation.provenance"),
        optional_capabilities=("research.browser_visual", "research.pdf"),
        required_maturity=Maturity.PROVIDER_READBACK,
        min_failure_domains=1,
        description="Multi-step web and enterprise research with source-grounded outputs.",
    ),
    "agent.action": EcosystemServiceSpec(
        "agent.action",
        EcosystemPlane.EXECUTION,
        ("tool.api", "browser.action", "terminal.exec"),
        optional_capabilities=("computer.gui", "workflow.event"),
        required_maturity=Maturity.BOUND,
        min_failure_domains=1,
        description="Choose the strongest structured API, browser, terminal or GUI route.",
    ),
    "agent.multi": EcosystemServiceSpec(
        "agent.multi",
        EcosystemPlane.INTELLIGENCE,
        ("agent.delegate", "agent.message", "agent.checkpoint"),
        optional_capabilities=("agent.a2a", "agent.subagent", "agent.hooks"),
        required_maturity=Maturity.BOUND,
        min_failure_domains=1,
        description="Parallel bounded specialist agents with durable handoff and checkpoints.",
    ),
    "model.council": EcosystemServiceSpec(
        "model.council",
        EcosystemPlane.INTELLIGENCE,
        ("model.route", "model.evaluate", "model.disagreement"),
        optional_capabilities=("model.ensemble", "model.local"),
        required_maturity=Maturity.BOUND,
        min_failure_domains=2,
        description="Provider/model diversity with evidence-preserving disagreement.",
    ),
    "code.agentic": EcosystemServiceSpec(
        "code.agentic",
        EcosystemPlane.CODE,
        ("code.read", "code.edit", "code.test", "code.checkpoint"),
        optional_capabilities=("code.subagent", "code.hook", "code.review"),
        required_maturity=Maturity.BOUND,
        min_failure_domains=1,
        description="Plan, edit, test, checkpoint, review and recover code changes.",
    ),
    "creative.studio": EcosystemServiceSpec(
        "creative.studio",
        EcosystemPlane.CREATIVE,
        ("creative.design", "creative.image", "artifact.export"),
        optional_capabilities=("creative.video", "creative.audio", "creative.vector", "creative.layout"),
        required_maturity=Maturity.BOUND,
        min_failure_domains=1,
        description="Conversational multi-tool creative production with existing-asset reuse.",
    ),
    "data.analytics": EcosystemServiceSpec(
        "data.analytics",
        EcosystemPlane.DATA,
        ("data.query", "data.transform", "data.visualize"),
        optional_capabilities=("data.predict", "data.semantic_model"),
        required_maturity=Maturity.BOUND,
        min_failure_domains=1,
        description="Structured analysis, transformation and visual insight generation.",
    ),
    "enterprise.workflow": EcosystemServiceSpec(
        "enterprise.workflow",
        EcosystemPlane.WORKFLOW,
        ("workflow.compose", "workflow.trigger", "workflow.connector"),
        optional_capabilities=("workflow.lowcode", "workflow.rollback", "workflow.run_history"),
        required_maturity=Maturity.BOUND,
        min_failure_domains=1,
        description="Reusable event-driven and low-code workflow automation.",
    ),
    "knowledge.enterprise": EcosystemServiceSpec(
        "knowledge.enterprise",
        EcosystemPlane.KNOWLEDGE,
        ("knowledge.search", "knowledge.retrieve", "knowledge.provenance"),
        optional_capabilities=("knowledge.graph", "knowledge.permissions"),
        required_maturity=Maturity.BOUND,
        min_failure_domains=1,
        description="Search and reason across governed internal knowledge with provenance.",
    ),
    "memory.continuum": EcosystemServiceSpec(
        "memory.continuum",
        EcosystemPlane.MEMORY,
        ("memory.event", "memory.projection", "memory.checkpoint"),
        optional_capabilities=("memory.semantic", "memory.global_fanout"),
        required_maturity=Maturity.BOUND,
        min_failure_domains=1,
        description="Durable event truth, verified projections, checkpoints and governed recall.",
    ),
    "device.computer": EcosystemServiceSpec(
        "device.computer",
        EcosystemPlane.DEVICE,
        ("device.screen.read", "device.input"),
        optional_capabilities=("device.terminal", "device.browser", "device.mobile"),
        required_maturity=Maturity.PROVIDER_READBACK,
        min_failure_domains=1,
        description="Authorized computer/desktop/browser/device control with readback.",
    ),
    "security.agent": EcosystemServiceSpec(
        "security.agent",
        EcosystemPlane.SECURITY,
        ("security.identity", "security.policy", "security.audit"),
        optional_capabilities=("security.prompt_injection", "security.model_armor", "security.secret_vault"),
        required_maturity=Maturity.BOUND,
        min_failure_domains=1,
        description="Identity, policy, audit, secret handling and runtime protection.",
    ),
    "observability.agent": EcosystemServiceSpec(
        "observability.agent",
        EcosystemPlane.OBSERVABILITY,
        ("observe.trace", "observe.quality", "observe.cost"),
        optional_capabilities=("observe.latency", "observe.drift", "observe.roi"),
        required_maturity=Maturity.BOUND,
        min_failure_domains=1,
        description="Trace, quality, cost, drift and owner-value measurement.",
    ),
    "marketplace.capability": EcosystemServiceSpec(
        "marketplace.capability",
        EcosystemPlane.MARKETPLACE,
        ("capability.discover", "capability.currentness", "capability.install"),
        optional_capabilities=("capability.marketplace", "capability.a2a", "capability.mcp"),
        required_maturity=Maturity.BOUND,
        min_failure_domains=1,
        description="Discover, qualify, install and route ecosystem capabilities.",
    ),
    "artifact.workspace": EcosystemServiceSpec(
        "artifact.workspace",
        EcosystemPlane.EXPERIENCE,
        ("artifact.document", "artifact.spreadsheet", "artifact.presentation"),
        optional_capabilities=("artifact.pdf", "artifact.design", "artifact.code"),
        required_maturity=Maturity.BOUND,
        min_failure_domains=1,
        description="Persistent workbench for documents, sheets, presentations, PDFs and code.",
    ),
    "communications.enterprise": EcosystemServiceSpec(
        "communications.enterprise",
        EcosystemPlane.COMMUNICATION,
        ("identity.resolve", "mail.telemetry", "calendar.read"),
        optional_capabilities=("mail.send", "calendar.write", "chat.team"),
        required_maturity=Maturity.PROVIDER_READBACK,
        min_failure_domains=2,
        description="Cross-provider identity, mail and calendar communication plane.",
    ),
}


__all__ = [
    "CapabilitySelection",
    "EcosystemMissionSpec",
    "EcosystemPlane",
    "EcosystemPlan",
    "EcosystemServiceSpec",
    "FUSE_ECOSYSTEM_SERVICES",
    "FuseEcosystemKernel",
]
