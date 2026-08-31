from __future__ import annotations

"""CFBE Omega frontier refresh v2.

Strengthens the existing Hyperleverage 100 genome against fresh September-2026
public leader evidence without creating another sovereign scheduler, memory
service, provider executor, or authority plane.

All functions are deterministic source/control logic. Provider/runtime/value
promotion remains separately evidence-gated.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable, Mapping, Sequence

from benchmarking.cfbe_omega.federation_competitive_upgrade_fabric_v1 import (
    CapabilityGene,
    ImplementationMode,
    load_genome,
)

SCHEMA = "CFBE-FEDERATION-FRONTIER-REFRESH-V2"
OTEL_SEMCONV_VERSION = "1.44.0"


class FrontierState(str, Enum):
    REUSE_VERIFIED = "REUSE_VERIFIED"
    SOURCE_COMPOSITION_V1 = "SOURCE_COMPOSITION_V1"
    STRENGTHENED_SOURCE_V2 = "STRENGTHENED_SOURCE_V2"
    PROVIDER_GATED = "PROVIDER_GATED"


class WorkLane(str, Enum):
    INTERACTIVE = "INTERACTIVE"
    DURABLE_WORKFLOW = "DURABLE_WORKFLOW"
    HOLD = "HOLD"


class SandboxState(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    SOURCE_READY_PROVIDER_OPEN = "SOURCE_READY_PROVIDER_OPEN"
    RESUMABLE_SANDBOX_READY = "RESUMABLE_SANDBOX_READY"
    HOLD_EFFECT_AUTHORITY = "HOLD_EFFECT_AUTHORITY"


@dataclass(frozen=True, slots=True)
class FrontierEvidence:
    source_id: str
    provider: str
    capability: str
    reference: str
    evidence_class: str = "PUBLIC_OFFICIAL"
    grants_authority: bool = False


@dataclass(frozen=True, slots=True)
class GeneFrontierAudit:
    gene_id: str
    domain: str
    improvement: str
    state: FrontierState
    implementation_target: str
    acceptance_gate: str
    frontier_sources: tuple[str, ...]
    provider_runtime_proven: bool = False
    stable_promotion_allowed: bool = False


@dataclass(frozen=True, slots=True)
class FrontierGenomeReceipt:
    schema: str
    gene_count: int
    routed_count: int
    strengthened_v2_count: int
    provider_gated_count: int
    unrouted_gene_ids: tuple[str, ...]
    audits: tuple[GeneFrontierAudit, ...]
    provider_effect_authorized: bool = False
    stable_promotion_allowed: bool = False

    def canonical_mapping(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DurableLanePlan:
    lane: WorkLane
    resumable_required: bool
    external_wait_required: bool
    human_approval_required: bool
    reasons: tuple[str, ...]
    provider_runtime_proven: bool = False


@dataclass(frozen=True, slots=True)
class SandboxExecutionPlan:
    state: SandboxState
    isolated_workspace_required: bool
    resumable_session_required: bool
    exact_effect_permit_required: bool
    reasons: tuple[str, ...]
    provider_effect_authorized: bool = False


@dataclass(frozen=True, slots=True)
class ToolboxGovernancePlan:
    state: str
    tools: tuple[tuple[str, str], ...]
    centralized_registry: bool
    centralized_auth: bool
    version_pinned: bool
    missing: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvaluationCampaignPlan:
    state: str
    golden_cases: int
    production_failure_cases: int
    synthetic_cases: int
    total_cases: int
    required_next_actions: tuple[str, ...]
    stable_promotion_allowed: bool = False


@dataclass(frozen=True, slots=True)
class AgentOptimizerDecision:
    state: str
    baseline_score: float
    candidate_score: float
    delta: float
    paired_cases: int
    hard_regressions: int
    owner_value_observed: bool
    provider_runtime_proven: bool
    stable_promotion_allowed: bool = False


@dataclass(frozen=True, slots=True)
class AIAssetInventoryReceipt:
    state: str
    asset_count: int
    complete_asset_ids: tuple[str, ...]
    incomplete_asset_ids: tuple[str, ...]
    required_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AgentTelemetryReceipt:
    state: str
    observed_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    semantic_convention_version: str
    sensitive_payloads_enabled: bool


@dataclass(frozen=True, slots=True)
class SupplyChainV12Receipt:
    state: str
    release_class: str
    missing: tuple[str, ...]
    source_track_ready: bool
    build_track_ready: bool
    artifact_attestation_required: bool
    provider_effect_authorized: bool = False


@dataclass(frozen=True, slots=True)
class IdempotencyV2Receipt:
    state: str
    method: str
    key_required: bool
    replay_eligible: bool
    scope_bound: bool
    age_days: int
    reason: str
    provider_effect_authorized: bool = False


@dataclass(frozen=True, slots=True)
class HookExecutionReceipt:
    state: str
    trusted_source: bool
    reviewed: bool
    sandboxed: bool
    effectful: bool
    exact_effect_permit: bool
    provider_effect_authorized: bool = False


FRONTIER_EVIDENCE: tuple[FrontierEvidence, ...] = (
    FrontierEvidence("SRC-OAI-AGENTS-202609", "OpenAI", "Agents, handoffs, guardrails, sandbox agents, sessions and tracing", "https://openai.github.io/openai-agents-python/"),
    FrontierEvidence("SRC-OAI-TRACE-202609", "OpenAI", "Task/turn/agent/tool/handoff trace spans and sensitive-data controls", "https://openai.github.io/openai-agents-python/tracing/"),
    FrontierEvidence("SRC-MS-FOUNDRY-202609", "Microsoft", "Managed agent runtime, versioned toolboxes, observability, optimizer and registry", "https://learn.microsoft.com/en-us/azure/ai-foundry/agents/overview"),
    FrontierEvidence("SRC-MS-EVAL-202609", "Microsoft", "Agent rubric evaluation, CI quality gates and continuous evaluation", "https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/evaluate-agent"),
    FrontierEvidence("SRC-GOOGLE-AGENTS-CLI-202609", "Google", "Scaffold/eval/deploy/publish/observe lifecycle and agent coding skills", "https://google.github.io/agents-cli/guide/getting-started/"),
    FrontierEvidence("SRC-GOOGLE-EVAL-202609", "Google", "Eval generation, grading, comparison, synthesis, failure analysis and optimization", "https://google.github.io/agents-cli/guide/evaluation/"),
    FrontierEvidence("SRC-GOOGLE-CODEEXEC-202609", "Google", "Sandboxed persistent multi-request Agent Runtime code execution", "https://google.github.io/adk-docs/tools/google-cloud/code-exec-agent-engine/"),
    FrontierEvidence("SRC-GOOGLE-RESTATE-202609", "Google ADK / Restate", "Durable LLM/tool journaling, pause/resume, safe versioning and persistent sessions", "https://google.github.io/adk-docs/integrations/restate/"),
    FrontierEvidence("SRC-AWS-AGENTCORE-202609", "AWS", "Agent, memory and gateway observability with OTEL-compatible telemetry", "https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html"),
    FrontierEvidence("SRC-CF-WORKFLOWS-202609", "Cloudflare", "Durable multi-step workflows, retries, external waits and resumable agent steps", "https://developers.cloudflare.com/workflows/"),
    FrontierEvidence("SRC-DD-AGENTOBS-202609", "Datadog", "Agent traces, performance, cost, error, quality, privacy and safety observability", "https://docs.datadoghq.com/llm_observability/"),
    FrontierEvidence("SRC-SN-AICT-202609", "ServiceNow", "Cross-vendor AI asset discovery, governance, observability, identity and value measurement", "https://www.servicenow.com/products/ai-control-tower.html"),
    FrontierEvidence("SRC-SN-ACTION-202609", "ServiceNow", "MCP/A2A action fabric and centrally governed cross-agent tool access", "https://www.servicenow.com/platform/action-fabric.html"),
    FrontierEvidence("SRC-SLSA-12-202609", "SLSA", "Version 1.2 source/build tracks and provenance", "https://slsa.dev/spec/v1.2/"),
    FrontierEvidence("SRC-GH-ATTEST-202609", "GitHub", "Artifact attestations and SLSA Build Level 3 patterns", "https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations"),
    FrontierEvidence("SRC-OTEL-144-202609", "OpenTelemetry", "Semantic Conventions 1.44.0 across traces, metrics, logs and events", "https://opentelemetry.io/docs/specs/semconv/"),
    FrontierEvidence("SRC-STRIPE-V2-IDEMP-202609", "Stripe", "API v2 scoped idempotency for POST/DELETE and failed replay without duplicate side effects", "https://docs.stripe.com/api-v2-overview"),
    FrontierEvidence("SRC-K8S-RECONCILE-202609", "Kubernetes", "Desired/current-state reconciliation controller pattern", "https://kubernetes.io/docs/concepts/architecture/controller/"),
    FrontierEvidence("SRC-ANTHROPIC-CODE-202609", "Anthropic", "Subagents, hooks, MCP and large-codebase context strategies", "https://www.anthropic.com/webinars/claude-code-advanced-patterns"),
)


STRENGTHENED_GENE_SOURCES: Mapping[str, tuple[str, ...]] = {
    "FHU-004": ("SRC-CF-WORKFLOWS-202609", "SRC-GOOGLE-RESTATE-202609"),
    "FHU-010": ("SRC-CF-WORKFLOWS-202609",),
    "FHU-018": ("SRC-GOOGLE-RESTATE-202609",),
    "FHU-020": ("SRC-OAI-AGENTS-202609", "SRC-GOOGLE-RESTATE-202609"),
    "FHU-031": ("SRC-OTEL-144-202609", "SRC-AWS-AGENTCORE-202609"),
    "FHU-032": ("SRC-OAI-TRACE-202609", "SRC-DD-AGENTOBS-202609"),
    "FHU-040": ("SRC-AWS-AGENTCORE-202609", "SRC-DD-AGENTOBS-202609"),
    "FHU-041": ("SRC-SLSA-12-202609",),
    "FHU-042": ("SRC-GH-ATTEST-202609", "SRC-SLSA-12-202609"),
    "FHU-052": ("SRC-OAI-AGENTS-202609", "SRC-GOOGLE-CODEEXEC-202609"),
    "FHU-054": ("SRC-STRIPE-V2-IDEMP-202609",),
    "FHU-057": ("SRC-GOOGLE-EVAL-202609", "SRC-MS-EVAL-202609"),
    "FHU-059": ("SRC-CF-WORKFLOWS-202609", "SRC-GOOGLE-RESTATE-202609", "SRC-OAI-AGENTS-202609"),
    "FHU-069": ("SRC-AWS-AGENTCORE-202609", "SRC-DD-AGENTOBS-202609", "SRC-SN-AICT-202609"),
    "FHU-073": ("SRC-SN-AICT-202609", "SRC-MS-FOUNDRY-202609"),
    "FHU-074": ("SRC-SN-AICT-202609", "SRC-MS-FOUNDRY-202609"),
    "FHU-075": ("SRC-MS-FOUNDRY-202609", "SRC-GOOGLE-AGENTS-CLI-202609"),
    "FHU-081": ("SRC-OAI-AGENTS-202609", "SRC-ANTHROPIC-CODE-202609"),
    "FHU-082": ("SRC-OAI-AGENTS-202609", "SRC-ANTHROPIC-CODE-202609"),
    "FHU-084": ("SRC-MS-FOUNDRY-202609", "SRC-SN-ACTION-202609"),
    "FHU-086": ("SRC-MS-FOUNDRY-202609", "SRC-SN-ACTION-202609"),
    "FHU-090": ("SRC-GOOGLE-EVAL-202609", "SRC-MS-FOUNDRY-202609"),
    "FHU-094": ("SRC-SN-AICT-202609",),
    "FHU-098": ("SRC-SN-AICT-202609", "SRC-GOOGLE-AGENTS-CLI-202609"),
    "FHU-100": ("SRC-GOOGLE-AGENTS-CLI-202609", "SRC-SLSA-12-202609", "SRC-OTEL-144-202609"),
}


def _evidence_ids() -> set[str]:
    return {item.source_id for item in FRONTIER_EVIDENCE}


def validate_frontier_evidence() -> None:
    ids = [item.source_id for item in FRONTIER_EVIDENCE]
    if len(ids) != len(set(ids)):
        raise ValueError("FRONTIER_EVIDENCE_DUPLICATE_SOURCE_ID")
    for item in FRONTIER_EVIDENCE:
        if item.grants_authority:
            raise ValueError(f"FRONTIER_EVIDENCE_AUTHORITY_LEAK:{item.source_id}")
        if item.evidence_class != "PUBLIC_OFFICIAL":
            raise ValueError(f"FRONTIER_EVIDENCE_CLASS_INVALID:{item.source_id}")
        if not item.reference.startswith("https://"):
            raise ValueError(f"FRONTIER_EVIDENCE_REFERENCE_INVALID:{item.source_id}")
    known = _evidence_ids()
    for gene_id, refs in STRENGTHENED_GENE_SOURCES.items():
        if not refs or any(ref not in known for ref in refs):
            raise ValueError(f"FRONTIER_EVIDENCE_MAPPING_INVALID:{gene_id}")


def compile_frontier_genome_receipt(genes: Sequence[CapabilityGene] | None = None) -> FrontierGenomeReceipt:
    validate_frontier_evidence()
    genome = tuple(genes or load_genome())
    audits: list[GeneFrontierAudit] = []
    for gene in genome:
        refs = tuple(STRENGTHENED_GENE_SOURCES.get(gene.gene_id, ()))
        if gene.implementation_mode == ImplementationMode.PROVIDER_GATED_CONTRACT:
            state = FrontierState.PROVIDER_GATED
        elif refs:
            state = FrontierState.STRENGTHENED_SOURCE_V2
        elif gene.implementation_mode == ImplementationMode.REUSE_VERIFIED:
            state = FrontierState.REUSE_VERIFIED
        else:
            state = FrontierState.SOURCE_COMPOSITION_V1
        audits.append(
            GeneFrontierAudit(
                gene_id=gene.gene_id,
                domain=gene.domain,
                improvement=gene.improvement,
                state=state,
                implementation_target=gene.implementation_target,
                acceptance_gate=gene.acceptance_gate,
                frontier_sources=refs,
            )
        )
    routed = [item for item in audits if item.state in set(FrontierState)]
    unrouted = tuple(item.gene_id for item in audits if not item.state)
    return FrontierGenomeReceipt(
        schema=SCHEMA,
        gene_count=len(audits),
        routed_count=len(routed),
        strengthened_v2_count=sum(item.state == FrontierState.STRENGTHENED_SOURCE_V2 for item in audits),
        provider_gated_count=sum(item.state == FrontierState.PROVIDER_GATED for item in audits),
        unrouted_gene_ids=unrouted,
        audits=tuple(audits),
    )


def durable_lane_plan(*, expected_runtime_seconds: int, waits_for_external_event: bool = False, human_approval_required: bool = False, resumable_runtime_available: bool = False) -> DurableLanePlan:
    if expected_runtime_seconds < 0:
        raise ValueError("DURABLE_LANE_RUNTIME_INVALID")
    durable = expected_runtime_seconds > 30 or waits_for_external_event or human_approval_required
    if not durable:
        return DurableLanePlan(WorkLane.INTERACTIVE, False, False, False, ())
    reasons = []
    if expected_runtime_seconds > 30:
        reasons.append("long_running")
    if waits_for_external_event:
        reasons.append("external_event_wait")
    if human_approval_required:
        reasons.append("human_approval_wait")
    if not resumable_runtime_available:
        reasons.append("resumable_runtime_provider_open")
    return DurableLanePlan(WorkLane.DURABLE_WORKFLOW if resumable_runtime_available else WorkLane.HOLD, True, waits_for_external_event, human_approval_required, tuple(reasons), provider_runtime_proven=resumable_runtime_available)


def sandbox_execution_plan(*, requires_code_execution: bool, isolated_workspace_available: bool, resumable_session_available: bool, effectful: bool = False, exact_effect_permit: bool = False) -> SandboxExecutionPlan:
    if not requires_code_execution:
        return SandboxExecutionPlan(SandboxState.NOT_REQUIRED, False, False, effectful, ())
    if effectful and not exact_effect_permit:
        return SandboxExecutionPlan(SandboxState.HOLD_EFFECT_AUTHORITY, True, True, True, ("exact_effect_permit_required",))
    if isolated_workspace_available and resumable_session_available:
        return SandboxExecutionPlan(SandboxState.RESUMABLE_SANDBOX_READY, True, True, effectful, (), provider_effect_authorized=effectful and exact_effect_permit)
    missing = []
    if not isolated_workspace_available:
        missing.append("isolated_workspace_provider_open")
    if not resumable_session_available:
        missing.append("resumable_session_provider_open")
    return SandboxExecutionPlan(SandboxState.SOURCE_READY_PROVIDER_OPEN, True, True, effectful, tuple(missing))


def toolbox_governance_plan(tool_versions: Mapping[str, str], *, centralized_registry: bool, centralized_auth: bool) -> ToolboxGovernancePlan:
    tools = tuple(sorted((str(name).strip(), str(version).strip()) for name, version in tool_versions.items()))
    missing: list[str] = []
    if not centralized_registry:
        missing.append("centralized_registry")
    if not centralized_auth:
        missing.append("centralized_auth")
    floating = tuple(name for name, version in tools if not version or version.lower() in {"latest", "main", "*"})
    if floating:
        missing.append("version_pinning:" + ",".join(floating))
    return ToolboxGovernancePlan("TOOLBOX_READY" if not missing else "HOLD_TOOLBOX_GOVERNANCE", tools, centralized_registry, centralized_auth, not floating, tuple(missing))


def evaluation_campaign_plan(*, golden_cases: int, production_failure_cases: int, synthetic_cases: int, minimum_total_cases: int = 20) -> EvaluationCampaignPlan:
    counts = (golden_cases, production_failure_cases, synthetic_cases, minimum_total_cases)
    if any(item < 0 for item in counts) or minimum_total_cases <= 0:
        raise ValueError("EVALUATION_CAMPAIGN_COUNT_INVALID")
    total = golden_cases + production_failure_cases + synthetic_cases
    required: list[str] = []
    if golden_cases == 0:
        required.append("add_golden_semantic_cases")
    if production_failure_cases == 0:
        required.append("harvest_real_failure_clusters")
    if total < minimum_total_cases:
        required.append("synthesize_additional_cases")
    return EvaluationCampaignPlan("EVAL_CAMPAIGN_READY" if not required else "EVAL_CAMPAIGN_FORMATION_REQUIRED", golden_cases, production_failure_cases, synthetic_cases, total, tuple(required))


def agent_optimizer_gate(*, baseline_score: float, candidate_score: float, paired_cases: int, hard_regressions: int, owner_value_observed: bool, provider_runtime_proven: bool) -> AgentOptimizerDecision:
    if not 0 <= baseline_score <= 1 or not 0 <= candidate_score <= 1:
        raise ValueError("AGENT_OPTIMIZER_SCORE_INVALID")
    if paired_cases < 0 or hard_regressions < 0:
        raise ValueError("AGENT_OPTIMIZER_SAMPLE_INVALID")
    delta = candidate_score - baseline_score
    if hard_regressions:
        state = "REJECT_REGRESSION"
    elif paired_cases < 20:
        state = "HOLD_INSUFFICIENT_PAIRED_EVALS"
    elif delta <= 0:
        state = "REJECT_NO_MEASURED_GAIN"
    elif not provider_runtime_proven:
        state = "CANDIDATE_SOURCE_ONLY_PROVIDER_OPEN"
    elif not owner_value_observed:
        state = "CANDIDATE_RUNTIME_VALUE_OPEN"
    else:
        state = "CANDIDATE_PROMOTION_REVIEW"
    return AgentOptimizerDecision(state, baseline_score, candidate_score, delta, paired_cases, hard_regressions, owner_value_observed, provider_runtime_proven, False)


def ai_asset_inventory_gate(assets: Sequence[Mapping[str, object]]) -> AIAssetInventoryReceipt:
    required = ("asset_id", "asset_type", "owner", "lineage", "risk_state", "value_state", "proof_ref")
    complete: list[str] = []
    incomplete: list[str] = []
    seen: set[str] = set()
    for raw in assets:
        asset_id = str(raw.get("asset_id") or "").strip()
        if not asset_id or asset_id in seen:
            raise ValueError("AI_ASSET_ID_REQUIRED_UNIQUE")
        seen.add(asset_id)
        if all(str(raw.get(field) or "").strip() for field in required):
            complete.append(asset_id)
        else:
            incomplete.append(asset_id)
    return AIAssetInventoryReceipt("AI_ASSET_INVENTORY_COMPLETE" if not incomplete else "AI_ASSET_INVENTORY_GAPS", len(assets), tuple(sorted(complete)), tuple(sorted(incomplete)), required)


def agent_telemetry_gate(observed_fields: Iterable[str], *, sensitive_payloads_enabled: bool = False) -> AgentTelemetryReceipt:
    required = {"mission.trace_id", "agent.id", "agent.turn", "tool.name", "tool.result_state", "guardrail.state", "handoff.target", "latency_ms", "token.input", "token.output", "error.type", "memory.operation", "gateway.operation"}
    observed = set(str(item).strip() for item in observed_fields if str(item).strip())
    missing = tuple(sorted(required - observed))
    if sensitive_payloads_enabled:
        missing = tuple(sorted(set(missing) | {"sensitive_payload_suppression"}))
    return AgentTelemetryReceipt("AGENT_TELEMETRY_READY" if not missing else "AGENT_TELEMETRY_GAPS", tuple(sorted(observed)), missing, OTEL_SEMCONV_VERSION, sensitive_payloads_enabled)


def supply_chain_v12_gate(*, release_class: str, source_provenance: bool, build_provenance: bool, hosted_build: bool, artifact_attestation: bool) -> SupplyChainV12Receipt:
    release = release_class.strip().upper()
    if release not in {"DEV", "INTERNAL", "CANARY", "STABLE"}:
        raise ValueError("SUPPLY_CHAIN_RELEASE_CLASS_INVALID")
    missing: list[str] = []
    if not source_provenance:
        missing.append("source_provenance")
    if not build_provenance:
        missing.append("build_provenance")
    if release in {"CANARY", "STABLE"} and not hosted_build:
        missing.append("hosted_build")
    attestation_required = release == "STABLE"
    if attestation_required and not artifact_attestation:
        missing.append("artifact_attestation")
    return SupplyChainV12Receipt("SUPPLY_CHAIN_V12_READY" if not missing else "HOLD_SUPPLY_CHAIN_V12", release, tuple(missing), source_provenance, build_provenance and (hosted_build or release in {"DEV", "INTERNAL"}), attestation_required)


def idempotency_v2_contract(*, method: str, key: str, endpoint: str, account_scope: str, age_days: int, parameters_match: bool) -> IdempotencyV2Receipt:
    verb = method.strip().upper()
    if age_days < 0:
        raise ValueError("IDEMPOTENCY_V2_AGE_INVALID")
    if verb == "GET":
        return IdempotencyV2Receipt("KEY_NOT_REQUIRED_GET_IDEMPOTENT", verb, False, True, bool(endpoint.strip() and account_scope.strip()), age_days, "GET is idempotent by definition")
    if verb not in {"POST", "DELETE"}:
        return IdempotencyV2Receipt("HOLD_METHOD_OUTSIDE_V2_CONTRACT", verb, True, False, False, age_days, "Only POST/DELETE are covered by this source contract")
    scope_bound = bool(key.strip() and endpoint.strip() and account_scope.strip())
    if not scope_bound:
        state, reason, eligible = "HOLD_IDEMPOTENCY_SCOPE_INCOMPLETE", "key, endpoint and account/sandbox scope are required", False
    elif age_days > 30:
        state, reason, eligible = "HOLD_IDEMPOTENCY_WINDOW_EXPIRED", "replay window exceeded", False
    elif not parameters_match:
        state, reason, eligible = "REJECT_PARAMETER_MISMATCH", "same key cannot represent different operation parameters", False
    else:
        state, reason, eligible = "IDEMPOTENT_REPLAY_ELIGIBLE", "scope, replay window and operation identity match", True
    return IdempotencyV2Receipt(state, verb, True, eligible, scope_bound, age_days, reason)


def hook_execution_policy(*, trusted_source: bool, reviewed: bool, sandboxed: bool, effectful: bool, exact_effect_permit: bool) -> HookExecutionReceipt:
    if not trusted_source:
        state = "REJECT_UNTRUSTED_HOOK"
    elif not reviewed:
        state = "HOLD_HOOK_REVIEW_REQUIRED"
    elif effectful and not exact_effect_permit:
        state = "HOLD_EFFECT_PERMIT_REQUIRED"
    elif effectful and not sandboxed:
        state = "HOLD_EFFECTFUL_HOOK_NOT_SANDBOXED"
    else:
        state = "HOOK_SOURCE_POLICY_READY"
    return HookExecutionReceipt(state, trusted_source, reviewed, sandboxed, effectful, exact_effect_permit, False)


def benchmark_20_dimensions() -> tuple[tuple[str, float, float, str], ...]:
    """Full CFBE 20-dimension heuristic snapshot; not vendor certification."""
    return (
        ("Agent platform & lifecycle", 86.0, 67.0, "sandbox/toolbox/provider runtime proof"),
        ("Models & intelligent routing", 78.0, 52.0, "multi-provider same-task observed routing"),
        ("Tools/connectors/APIs/MCP", 90.0, 75.0, "managed versioned toolbox proof"),
        ("Grounding/knowledge/semantic context", 91.0, 76.0, "production retrieval quality/value"),
        ("Workflow automation & eventing", 91.0, 77.0, "always-on durable provider workflow proof"),
        ("Multi-agent orchestration", 89.0, 70.0, "prospective task/value comparisons"),
        ("Observability/tracing/evaluation", 90.0, 73.0, "standardized live agent telemetry/evals"),
        ("Identity/secrets/Zero Trust", 81.0, 54.0, "canonical workload identity and action readback"),
        ("AI safety/red teaming/runtime guards", 94.0, 83.0, "live effect-route adversarial evidence"),
        ("Secure SDLC/CI/supply chain", 92.0, 80.0, "SLSA source+build and artifact attestation"),
        ("Reliability/SRE/incident operations", 91.0, 76.0, "provider SLO/RTO/RPO outcome cohorts"),
        ("Governance/provenance/auditability", 97.0, 91.0, "cross-provider AI asset inventory/value proof"),
        ("Data/analytics/semantic BI", 80.0, 58.0, "unified operational analytics/value telemetry"),
        ("Cloud runtime/elasticity/scaling", 74.0, 46.0, "provider-hosted autoscale and durable runtime"),
        ("AI infrastructure/edge/physical AI", 58.0, 24.0, "strategic optional; provider proof sparse"),
        ("Developer experience/platform engineering", 87.0, 72.0, "paved-road sandbox/toolbox automation"),
        ("Enterprise productivity UX", 79.0, 55.0, "measured workflow/user adoption outcomes"),
        ("Continuous learning/institutional memory", 95.0, 84.0, "prospective value and drift outcomes"),
        ("FinOps/performance efficiency", 87.0, 64.0, "real mission cost/value and capacity telemetry"),
        ("Operating model/team capability", 88.0, 72.0, "measured flow/effectiveness over time"),
    )


def benchmark_20_dimension_summary() -> dict[str, object]:
    rows = benchmark_20_dimensions()
    return {
        "schema": "CFBE-20-DIMENSION-BENCHMARK-V2",
        "dimension_count": len(rows),
        "raw_architecture_average": round(sum(row[1] for row in rows) / len(rows), 2),
        "proof_adjusted_average": round(sum(row[2] for row in rows) / len(rows), 2),
        "lowest_proof_dimensions": tuple(name for name, _, score, _ in sorted(rows, key=lambda row: row[2])[:5]),
        "highest_proof_dimensions": tuple(name for name, _, score, _ in sorted(rows, key=lambda row: row[2], reverse=True)[:5]),
        "vendor_certified": False,
        "provider_effect_authorized": False,
    }
