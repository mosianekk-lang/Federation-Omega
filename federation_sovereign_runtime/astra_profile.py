from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .core import ProcessorProfile, ReasoningEffort


ASTRA_MODEL_ID = "gpt-6-astra"
ASTRA_PUBLIC_SNAPSHOT_DATE = "2026-09-05"
ASTRA_CONTEXT_WINDOW = 1_050_000
ASTRA_MAX_OUTPUT_TOKENS = 128_000
ASTRA_KNOWLEDGE_CUTOFF = "2026-04-30"
ASTRA_REASONING_EFFORTS = (
    ReasoningEffort.LOW.value,
    ReasoningEffort.MEDIUM.value,
    ReasoningEffort.HIGH.value,
    ReasoningEffort.XHIGH.value,
    ReasoningEffort.MAX.value,
)

ASTRA_PUBLIC_CAPABILITIES = frozenset(
    {
        "ASYNC_TOOL_CALLING",
        "MID_TURN_STEERING",
        "DYNAMIC_REASONING_UPDATE",
        "COMPUTER_USE",
        "STRUCTURED_OUTPUTS",
        "STREAMING",
        "PROGRAMMATIC_TOOL_CALLING",
        "MULTI_AGENT_ORCHESTRATION",
        "PROMPT_CACHING",
        "PERSISTED_REASONING",
        "COMPACTION",
        "WEB_SEARCH",
        "FILE_SEARCH",
        "IMAGE_GENERATION",
        "CODE_INTERPRETER",
        "HOSTED_SHELL",
        "APPLY_PATCH",
        "SKILLS",
        "MCP",
        "TOOL_SEARCH",
    }
)

OFFICIAL_PUBLIC_SOURCES = (
    "https://developers.openai.com/api/docs/guides/latest-model",
    "https://developers.openai.com/api/docs/models/gpt-6-astra",
    "https://developers.openai.com/api/docs/models/compare",
)


@dataclass(frozen=True)
class CapabilityGene:
    gene_id: str
    public_astra_mechanism: str
    federation_target: str
    adoption_mode: str
    proof_gate: str


ASTRA_CAPABILITY_GENES = (
    CapabilityGene("ASTRA-G01", "Async tool calling", "NonblockingToolBroker + Bubbles continuity lanes", "CLEAN_ROOM_COMPOSE", "independent-work and call-id regressions"),
    CapabilityGene("ASTRA-G02", "Mid-turn steering", "MissionSteeringController + Human Mission Contract", "CLEAN_ROOM_COMPOSE", "intent-preservation regressions"),
    CapabilityGene("ASTRA-G03", "Dynamic reasoning updates", "AdaptiveReasoningController + Adaptive Intelligence Router", "CLEAN_ROOM_COMPOSE", "configuration transition regressions"),
    CapabilityGene("ASTRA-G04", "Programmatic tool calling", "Deterministic tool micro-runtime", "EXTEND_EXISTING_TOOL_FABRIC", "schema and effect-boundary tests"),
    CapabilityGene("ASTRA-G05", "Multi-agent orchestration", "Bubbles DAG + specialist swarm compiler", "REUSE_AND_EXTEND", "failed-lane isolation + quality tests"),
    CapabilityGene("ASTRA-G06", "Persisted reasoning", "Provider-neutral KDV reasoning capsule", "CLEAN_ROOM_COMPOSE", "restore/replay equivalence"),
    CapabilityGene("ASTRA-G07", "Compaction", "ContextVirtualizer + bounded delta memory", "REUSE_AND_EXTEND", "pinned-proof preservation tests"),
    CapabilityGene("ASTRA-G08", "Computer use", "SOVARA-governed computer/browser execution lanes", "PROVIDER_DEPENDENT", "native effect/readback/rollback"),
    CapabilityGene("ASTRA-G09", "Hosted shell/apply patch/code interpreter", "Sandboxed Tool Fabric", "PROVIDER_DEPENDENT", "sandbox and artifact readback"),
    CapabilityGene("ASTRA-G10", "MCP/tool search/skills", "Capability registry and negotiated tool discovery", "REUSE_AND_EXTEND", "capability contract conformance"),
    CapabilityGene("ASTRA-G11", "Web/file search", "EvidenceOps/TruthGrid research plane", "REUSE_AND_EXTEND", "source/provenance coverage"),
    CapabilityGene("ASTRA-G12", "Image/document creation", "Artifact Foundry and quality courts", "REUSE_AND_EXTEND", "artifact verification"),
    CapabilityGene("ASTRA-G13", "Large context", "Context virtualization instead of single-window dependence", "CLEAN_ROOM_COMPOSE", "context loss and overflow tests"),
    CapabilityGene("ASTRA-G14", "Intent retention through steering", "Human Mission Contract intent lock", "REUSE_AND_EXTEND", "objective-drift tests"),
    CapabilityGene("ASTRA-G15", "Misalignment monitoring", "AlignmentSentinel + RealityGuard", "CLEAN_ROOM_COMPOSE", "scope/authority/claim drift tests"),
    CapabilityGene("ASTRA-G16", "Scheduled/event-triggered work", "Bubbles/ChatBridge durable event fabric", "REUSE_AND_EXTEND", "resume/trigger receipts"),
    CapabilityGene("ASTRA-G17", "Long-running computer work", "Durable continuity + HOLD_READBACK semantics", "REUSE_AND_EXTEND", "restart and uncertain-effect tests"),
    CapabilityGene("ASTRA-G18", "Initiative/follow-through", "Outcome-First + PRE_FINAL_RESPONSE completion gate", "REUSE_EXISTING", "premature-termination regression"),
    CapabilityGene("ASTRA-G19", "Professional artifact work", "Artifact quality + visual/document courts", "REUSE_AND_EXTEND", "domain quality evals"),
    CapabilityGene("ASTRA-G20", "Efficiency under stronger intelligence", "Processor Market + Cost Governor", "CLEAN_ROOM_COMPOSE", "quality/cost Pareto cohort"),
)


def public_astra_profile(
    *,
    available: bool,
    authorized: bool,
    measured_quality: float | None = None,
    measured_latency_score: float | None = None,
    measured_cost_score: float | None = None,
    measured_privacy_score: float | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ProcessorProfile:
    """Build an Astra processor profile without inventing empirical scores.

    Availability and authorization are caller-supplied live facts. Quality,
    latency, cost and privacy scores remain optional until measured by the
    Federation's own evaluation courts.
    """
    merged_metadata = {
        "public_snapshot_date": ASTRA_PUBLIC_SNAPSHOT_DATE,
        "knowledge_cutoff": ASTRA_KNOWLEDGE_CUTOFF,
        "max_output_tokens": ASTRA_MAX_OUTPUT_TOKENS,
        "reasoning_efforts": ASTRA_REASONING_EFFORTS,
        "official_public_sources": OFFICIAL_PUBLIC_SOURCES,
        "provider_is_cognitive_processor_not_mission_authority": True,
        "weights_or_private_reasoning_copied": False,
    }
    if metadata:
        merged_metadata.update(dict(metadata))
    return ProcessorProfile(
        processor_id="OPENAI::GPT-6-ASTRA",
        provider="OPENAI",
        model=ASTRA_MODEL_ID,
        capabilities=ASTRA_PUBLIC_CAPABILITIES,
        available=bool(available),
        authorized=bool(authorized),
        max_context_tokens=ASTRA_CONTEXT_WINDOW,
        measured_quality=measured_quality,
        measured_latency_score=measured_latency_score,
        measured_cost_score=measured_cost_score,
        measured_privacy_score=measured_privacy_score,
        metadata=merged_metadata,
    )


def with_async_tool(tool: Mapping[str, Any]) -> dict[str, Any]:
    """Return an Astra-compatible async function/custom-tool descriptor.

    Public Astra guidance states that function or custom tools can opt into
    async execution with ``async: true``. This helper only applies that public
    modifier; it does not execute the tool or manage its result.
    """
    descriptor = dict(tool)
    if descriptor.get("type") not in {"function", "custom"}:
        raise ValueError("ASTRA_ASYNC_REQUIRES_FUNCTION_OR_CUSTOM_TOOL")
    descriptor["async"] = True
    return descriptor


def configuration_update_item(effort: ReasoningEffort | str) -> dict[str, Any]:
    """Create the public Responses API configuration-update input item."""
    value = effort.value if isinstance(effort, ReasoningEffort) else str(effort)
    if value not in ASTRA_REASONING_EFFORTS:
        raise ValueError("UNSUPPORTED_ASTRA_REASONING_EFFORT")
    return {
        "type": "configuration_update",
        "reasoning": {"effort": value},
    }


__all__ = [
    "ASTRA_CAPABILITY_GENES",
    "ASTRA_CONTEXT_WINDOW",
    "ASTRA_KNOWLEDGE_CUTOFF",
    "ASTRA_MAX_OUTPUT_TOKENS",
    "ASTRA_MODEL_ID",
    "ASTRA_PUBLIC_CAPABILITIES",
    "ASTRA_PUBLIC_SNAPSHOT_DATE",
    "ASTRA_REASONING_EFFORTS",
    "CapabilityGene",
    "OFFICIAL_PUBLIC_SOURCES",
    "configuration_update_item",
    "public_astra_profile",
    "with_async_tool",
]
