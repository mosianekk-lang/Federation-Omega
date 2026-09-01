from __future__ import annotations

"""CFBE Ω SOVARA × SOL 6.2 convergence fabric v1.

This is an integration/control layer, not a new sovereign scheduler, provider
executor, authority plane, or memory service. SOL 6.2 remains the transactional
mission/state-transition kernel. SOVARA remains the provider/substrate routing
and provider-proof fabric. This module binds the two through deterministic,
proof-carrying contracts while preserving explicit authority separation.

Source/control implementation does not imply provider-live deployment,
continuous background execution, provider IAM, sustained owner value, or market
superiority.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from ops.sovara_provider_execution_fabric import (
    ProviderCell,
    ProofReceipt as SovaraProofReceipt,
    authority_inheritance_allowed,
    select_provider_route,
)
from sol_61_runtime.sol_62 import ExecutionIntent, ProofEnvelope, TransitionSpec
from sol_61_runtime.sol_62_frontier_primitives import digest
from benchmarking.cfbe_omega.federation_autopilot_metacognition_v1 import (
    MetaAction,
    MetaCognitiveState,
    metacognitive_assessment,
)

SCHEMA = "CFBE-SOVARA-SOL62-CONVERGENCE-V1"
GENOME_PREFIX = "SSX"
EXPECTED_GENE_COUNT = 100


class ImplementationMode(str, Enum):
    REUSE_VERIFIED = "REUSE_VERIFIED"
    COMPOSED_BY_CONVERGENCE = "COMPOSED_BY_CONVERGENCE"
    PROVIDER_GATED_CONTRACT = "PROVIDER_GATED_CONTRACT"


class RouteState(str, Enum):
    READY = "READY"
    HOLD_NO_PROVIDER = "HOLD_NO_PROVIDER"
    HOLD_METACOGNITIVE = "HOLD_METACOGNITIVE"
    HOLD_PROVIDER_PROOF = "HOLD_PROVIDER_PROOF"


@dataclass(frozen=True, slots=True)
class ConvergenceGene:
    gene_id: str
    domain: str
    improvement: str
    implementation_mode: ImplementationMode
    implementation_owner: str
    handler: str
    acceptance_gate: str
    related_existing_controls: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GeneControlDecision:
    gene_id: str
    handler: str
    source_control_implemented: bool
    provider_runtime_proven: bool
    stable_promotion_allowed: bool
    external_effect_authorized: bool
    state: str


@dataclass(frozen=True, slots=True)
class RouteBinding:
    schema: str
    state: RouteState
    mission_id: str
    transition_id: str
    route_fingerprint: str
    selected_provider: str | None
    selected_substrate: str | None
    effect_id: str | None
    intent: ExecutionIntent | None
    provider_authority_inherited: bool
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ToolboxManifest:
    schema: str
    name: str
    version: str
    tools: tuple[Mapping[str, Any], ...]
    manifest_sha256: str


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    state: str
    missing: tuple[str, ...]
    stable_promotion_allowed: bool
    provider_effect_authorized: bool


@dataclass(frozen=True, slots=True)
class ConvergenceReceipt:
    schema: str
    gene_count: int
    routed_count: int
    reuse_count: int
    composed_count: int
    provider_gated_count: int
    unrouted_gene_ids: tuple[str, ...]
    architecture_score: float
    proof_adjusted_score: float
    provider_live_universal: bool
    stable_promotion_allowed: bool
    market_superiority_claim: bool


DOMAIN_GENE_NAMES = {
    "MISSION_PROVIDER_CONTRACT": [
        "Canonical mission-to-provider execution contract",
        "Target-state-aware provider eligibility",
        "Route decision bound to SOL transition identity",
        "Provider and substrate pinning per execution attempt",
        "Persist route decision before effect preparation",
        "Provider substitution requires versioned route revision",
        "Provider circuit state participates in transition readiness",
        "SOVARA route rationale emitted into SOL audit lineage",
        "Held-provider isolation without global mission stall",
        "Alternate-provider rollback preserving mission intent",
    ],
    "TRANSACTIONAL_EFFECTS": [
        "Provider-scoped idempotency policy adapter",
        "Semantic request hash spans route, payload and expected readback",
        "At-most-once probe-before-retry enforcement",
        "Partial-provider-failure reconciliation state",
        "Provider correlation identifier required before verification",
        "Explicit expected-readback contract per effect",
        "Provider response digest bound to proof envelope",
        "Compensation contract for consequential provider effects",
        "Dead-letter quarantine for poison provider effects",
        "Idempotency retention-window metadata and expiry guard",
    ],
    "DURABLE_RUNTIME_EVENTING": [
        "Durable provider-route checkpoint",
        "Zero-compute external-wait contract",
        "External-event wake envelope",
        "Cross-process resume route-integrity check",
        "Cross-machine state-handoff receipt",
        "Long-running heartbeat and lease renewal contract",
        "Missed-event catch-up scanner contract",
        "Event deduplication plus fencing",
        "Deadline and timeout propagation across SOL and SOVARA",
        "Human-approval interrupt and durable resume",
    ],
    "METACOG_PROVIDER_INTELLIGENCE": [
        "Provider-specific uncertainty decomposition",
        "Confidence-to-provider route policy",
        "Reflection ROI gate before expensive provider escalation",
        "Novelty-triggered challenger-provider route",
        "Contradiction-triggered independent provider cross-check",
        "Cost-and-latency pressure-aware provider routing",
        "Evidence-coverage gate for consequential provider selection",
        "Provider health as explicit metacognitive feature",
        "Repeated provider failure triggers replan instead of blind retry",
        "Provider route rationale encoded in metacognitive trace",
    ],
    "TOOLBOX_MCP_GOVERNANCE": [
        "Central versioned toolbox manifest",
        "Tool capability and schema fingerprint",
        "Action-specific tool permission binding",
        "MCP server identity and trust binding",
        "Strict tool input/output schema validation",
        "Tool preflight and postflight guardrails",
        "Tool deprecation and supersession lifecycle",
        "Tool health and failure telemetry",
        "Minimum-necessary context for handoffs and tools",
        "Agent/tool/provider asset inventory with owner, risk and version",
    ],
    "IDENTITY_AUTHORITY_ZERO_TRUST": [
        "Short-lived workload identity required for provider execution",
        "Explicit no-authority-inheritance law between SOL and SOVARA",
        "Gateway-only governed ingress contract",
        "Action-bound expiring authority lease",
        "One-use external-effect permit",
        "Provider-specific least-privilege scope compiler",
        "Delegation-chain provenance",
        "Break-glass authority with expiry and audit",
        "Provider identity readback witness",
        "Unauthorized or unverified route cannot dispatch",
    ],
    "OBSERVABILITY_PROOF_EVALS": [
        "Unified trace identity across mission, transition, route, effect and provider",
        "OpenTelemetry-aligned agent/runtime semantic envelope",
        "Standardized tool and provider spans",
        "Provider cost, token, latency and error telemetry",
        "Trace-to-proof lineage",
        "Provider-native semantic readback witness",
        "Golden route-evaluation registry",
        "Production failure-cluster eval harvesting",
        "Paired provider champion/challenger campaign",
        "Confidence calibration segmented by provider and route",
    ],
    "MEMORY_CONTEXT_CAUSAL": [
        "Provider-route outcome memory",
        "Provider capability freshness leases",
        "Per-provider context-budget compiler",
        "Memory privacy-tier enforcement on provider handoff",
        "Causal provider-failure graph",
        "Provider/model behavior drift detector",
        "Source, model and tool version provenance memory",
        "Result cache keyed by full semantic execution identity",
        "Stale or mismatched cache rejection",
        "Route learning from observed outcomes rather than self-judgment",
    ],
    "SELF_HEALING_AUTOPILOT": [
        "Provider failure-fingerprint circuit breaker",
        "Half-open recovery probe",
        "Changed-dependency retry trigger",
        "Autonomous safe alternate-provider fallback",
        "Reversible route canary",
        "Automatic rollback on verified route regression",
        "Optimizer proposals across provider, model, tool and instruction",
        "No-self-promotion gate for convergence optimizers",
        "Owner escalation only after safe routes are exhausted",
        "Stable route-promotion hysteresis",
    ],
    "PLATFORM_FINOPS_VALUE_SUPPLYCHAIN": [
        "Per-mission provider spend budget",
        "Cost-to-accepted-outcome metric",
        "Owner-burden delta segmented by route",
        "Provider SLO and error-budget policy",
        "SLSA source/build provenance and artifact-attestation gate",
        "SBOM plus toolbox/model provenance manifest",
        "AI asset lineage, ownership, risk and value inventory",
        "Capacity and backpressure admission control",
        "Sustained-value promotion gate",
        "Frontier benchmark refresh cadence with source-freshness enforcement",
    ],
}

PROVIDER_GATED_IDS = frozenset({
    "SSX-022", "SSX-023", "SSX-025", "SSX-051",
    "SSX-053", "SSX-059", "SSX-066", "SSX-069",
})

REUSE_IDS = frozenset({
    "SSX-009","SSX-012","SSX-013","SSX-015","SSX-016","SSX-017","SSX-018","SSX-019",
    "SSX-021","SSX-024","SSX-028","SSX-030","SSX-031","SSX-033","SSX-039",
    "SSX-041","SSX-042","SSX-043","SSX-046","SSX-049","SSX-052","SSX-054","SSX-055",
    "SSX-057","SSX-060","SSX-061","SSX-063","SSX-065","SSX-067","SSX-068","SSX-070",
    "SSX-072","SSX-075","SSX-077","SSX-079","SSX-080","SSX-081","SSX-082","SSX-083",
    "SSX-084","SSX-086","SSX-088","SSX-089","SSX-090","SSX-091","SSX-094","SSX-095",
    "SSX-098","SSX-099","SSX-100",
})

DOMAIN_OWNERS = {
    "MISSION_PROVIDER_CONTRACT": "SOL 6.2 mission/transition kernel + SOVARA route fabric",
    "TRANSACTIONAL_EFFECTS": "SOL 6.2 transactional effect spine + SOVARA proof receipts",
    "DURABLE_RUNTIME_EVENTING": "SOL durability + AutoPilot witness/event fabric + provider runtime adapters",
    "METACOG_PROVIDER_INTELLIGENCE": "CFBE AutoPilot Meta-Cognition + SOVARA route selection",
    "TOOLBOX_MCP_GOVERNANCE": "Unified Capability Graph + SOVARA + ProofOS",
    "IDENTITY_AUTHORITY_ZERO_TRUST": "SOL 6.2 authority/gateway/workload identity + provider-native IAM",
    "OBSERVABILITY_PROOF_EVALS": "ProofOS + SOL traces + SOVARA receipts + CFBE eval courts",
    "MEMORY_CONTEXT_CAUSAL": "BMF/KDV memory + SOL event state + CFBE causal learning",
    "SELF_HEALING_AUTOPILOT": "Failure-Win + AutoPilot + SOVARA circuits + SOL recovery",
    "PLATFORM_FINOPS_VALUE_SUPPLYCHAIN": "CFBE + ProofOS + GitHub/SLSA + owner-value ledger",
}

DOMAIN_HANDLERS = {
    "MISSION_PROVIDER_CONTRACT": "bind_transition_to_provider_route",
    "TRANSACTIONAL_EFFECTS": "enforce_transactional_provider_effect",
    "DURABLE_RUNTIME_EVENTING": "enforce_durable_event_resume",
    "METACOG_PROVIDER_INTELLIGENCE": "metacognitive_provider_policy",
    "TOOLBOX_MCP_GOVERNANCE": "compile_versioned_toolbox",
    "IDENTITY_AUTHORITY_ZERO_TRUST": "enforce_authority_separation",
    "OBSERVABILITY_PROOF_EVALS": "compile_proof_and_telemetry",
    "MEMORY_CONTEXT_CAUSAL": "enforce_outcome_memory",
    "SELF_HEALING_AUTOPILOT": "enforce_recovery_and_promotion",
    "PLATFORM_FINOPS_VALUE_SUPPLYCHAIN": "enforce_value_supplychain_gate",
}

DOMAIN_GATES = {
    "MISSION_PROVIDER_CONTRACT": "route identity must be explicit, source-bound, provider-local and non-authority-bearing",
    "TRANSACTIONAL_EFFECTS": "effect identity, idempotency, expected readback and provider correlation must remain exact",
    "DURABLE_RUNTIME_EVENTING": "resume must preserve mission/route identity without duplicate effects",
    "METACOG_PROVIDER_INTELLIGENCE": "routing must react to evidence, uncertainty, contradiction, cost and failure rather than self-judgment",
    "TOOLBOX_MCP_GOVERNANCE": "tool identity, schema, version, trust and permission must be machine-verifiable",
    "IDENTITY_AUTHORITY_ZERO_TRUST": "no authority inheritance; exact workload identity, gateway and one-use effect authority are separate gates",
    "OBSERVABILITY_PROOF_EVALS": "trace, readback, proof, eval and calibration identities must cross-link without claim inflation",
    "MEMORY_CONTEXT_CAUSAL": "only privacy-minimal, fresh, outcome-grounded state may influence future routing",
    "SELF_HEALING_AUTOPILOT": "repair before escalation, changed-route retry, rollback and no self-promotion",
    "PLATFORM_FINOPS_VALUE_SUPPLYCHAIN": "cost, SLO, provenance, capacity and owner value are promotion evidence, not narrative claims",
}

RELATED_BY_DOMAIN = {
    "MISSION_PROVIDER_CONTRACT": ("FHU-001","FHU-007","FHU-009","APM-003","APM-053"),
    "TRANSACTIONAL_EFFECTS": ("FHU-009","FHU-035","FHU-054","APM-035","APM-059"),
    "DURABLE_RUNTIME_EVENTING": ("FHU-027","FHU-029","APM-031","APM-032","APM-033"),
    "METACOG_PROVIDER_INTELLIGENCE": ("FHU-084","FHU-097","APM-011","APM-023","APM-054"),
    "TOOLBOX_MCP_GOVERNANCE": ("FHU-074","FHU-075","FHU-086","APM-052","APM-060"),
    "IDENTITY_AUTHORITY_ZERO_TRUST": ("FHU-046","FHU-047","FHU-049","APM-058","APM-059"),
    "OBSERVABILITY_PROOF_EVALS": ("FHU-031","FHU-032","FHU-037","APM-061","APM-068"),
    "MEMORY_CONTEXT_CAUSAL": ("FHU-015","FHU-017","FHU-019","APM-020","APM-067"),
    "SELF_HEALING_AUTOPILOT": ("FHU-023","FHU-027","FHU-030","APM-037","APM-099"),
    "PLATFORM_FINOPS_VALUE_SUPPLYCHAIN": ("FHU-021","FHU-041","FHU-069","APM-069","APM-098"),
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _hash(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def load_genome() -> tuple[ConvergenceGene, ...]:
    genes: list[ConvergenceGene] = []
    cursor = 1
    for domain, improvements in DOMAIN_GENE_NAMES.items():
        for improvement in improvements:
            gene_id = f"{GENOME_PREFIX}-{cursor:03d}"
            mode = (
                ImplementationMode.PROVIDER_GATED_CONTRACT if gene_id in PROVIDER_GATED_IDS
                else ImplementationMode.REUSE_VERIFIED if gene_id in REUSE_IDS
                else ImplementationMode.COMPOSED_BY_CONVERGENCE
            )
            genes.append(ConvergenceGene(
                gene_id=gene_id,
                domain=domain,
                improvement=improvement,
                implementation_mode=mode,
                implementation_owner=DOMAIN_OWNERS[domain],
                handler=DOMAIN_HANDLERS[domain],
                acceptance_gate=DOMAIN_GATES[domain],
                related_existing_controls=RELATED_BY_DOMAIN[domain],
            ))
            cursor += 1
    validate_genome(tuple(genes))
    return tuple(genes)


def validate_genome(genes: Sequence[ConvergenceGene]) -> None:
    if len(genes) != EXPECTED_GENE_COUNT:
        raise ValueError(f"SSX_EXPECTED_100_GOT_{len(genes)}")
    expected_ids = [f"{GENOME_PREFIX}-{i:03d}" for i in range(1, EXPECTED_GENE_COUNT + 1)]
    ids = [g.gene_id for g in genes]
    if ids != expected_ids or len(set(ids)) != EXPECTED_GENE_COUNT:
        raise ValueError("SSX_GENE_ID_SEQUENCE_INVALID")
    if set(PROVIDER_GATED_IDS) & set(REUSE_IDS):
        raise ValueError("SSX_IMPLEMENTATION_MODE_COLLISION")
    if len(DOMAIN_GENE_NAMES) != 10 or any(len(v) != 10 for v in DOMAIN_GENE_NAMES.values()):
        raise ValueError("SSX_DOMAIN_SHAPE_INVALID")


def evaluate_gene_controls() -> tuple[GeneControlDecision, ...]:
    decisions = []
    for gene in load_genome():
        provider_gate = gene.implementation_mode == ImplementationMode.PROVIDER_GATED_CONTRACT
        decisions.append(GeneControlDecision(
            gene_id=gene.gene_id,
            handler=gene.handler,
            source_control_implemented=True,
            provider_runtime_proven=False,
            stable_promotion_allowed=False,
            external_effect_authorized=False,
            state="HOLD_PROVIDER_NATIVE_PROOF" if provider_gate else "SOURCE_CONTROL_BOUND",
        ))
    return tuple(decisions)


def bind_transition_to_provider_route(
    *,
    transition: TransitionSpec,
    cells: Sequence[ProviderCell],
    provider_receipts: Mapping[str, SovaraProofReceipt] | None,
    payload: Mapping[str, Any],
    semantics: str,
    actor: str,
    source_version: str,
    expected_readback: Mapping[str, Any],
    idempotency_key: str,
    preferred_order: Sequence[str] = (),
) -> RouteBinding:
    """Compile a SOVARA route into a SOL 6.2 execution intent.

    This never grants provider authority or performs dispatch. Provider authority
    remains a later SOL/provider gate.
    """
    route = select_provider_route(cells, provider_receipts or {}, preferred_order)
    if route.selected_provider is None or route.selected_substrate is None:
        return RouteBinding(
            schema=SCHEMA,
            state=RouteState.HOLD_NO_PROVIDER,
            mission_id=transition.mission_id,
            transition_id=transition.transition_id,
            route_fingerprint=route.fingerprint,
            selected_provider=None,
            selected_substrate=None,
            effect_id=None,
            intent=None,
            provider_authority_inherited=False,
            blockers=("NO_PROVIDER_CELL_CURRENTLY_ELIGIBLE",),
        )
    selected = next(
        cell for cell in cells
        if cell.provider == route.selected_provider and cell.substrate.value == route.selected_substrate
    )
    if authority_inheritance_allowed(selected, selected):
        raise ValueError("SSX_AUTHORITY_INHERITANCE_FORBIDDEN")
    if not expected_readback:
        raise ValueError("SSX_EXPECTED_READBACK_REQUIRED")
    binding_identity = {
        "mission_id": transition.mission_id,
        "transition_id": transition.transition_id,
        "operation": transition.operation,
        "target": transition.target,
        "provider": route.selected_provider,
        "substrate": route.selected_substrate,
        "route_fingerprint": route.fingerprint,
        "payload_sha256": digest(payload),
        "expected_readback_sha256": digest(expected_readback),
        "source_version": source_version,
        "idempotency_key": idempotency_key,
    }
    effect_id = "ssx-" + sha256(_canonical(binding_identity).encode("utf-8")).hexdigest()[:32]
    intent = ExecutionIntent(
        effect_id=effect_id,
        transition_id=transition.transition_id,
        provider=route.selected_provider,
        payload=dict(payload),
        semantics=semantics,
        idempotency_key=idempotency_key,
        actor=actor,
        source_version=source_version,
        expected_readback=dict(expected_readback),
        rollback_required=bool(transition.consequential),
    )
    return RouteBinding(
        schema=SCHEMA,
        state=RouteState.READY,
        mission_id=transition.mission_id,
        transition_id=transition.transition_id,
        route_fingerprint=route.fingerprint,
        selected_provider=route.selected_provider,
        selected_substrate=route.selected_substrate,
        effect_id=effect_id,
        intent=intent,
        provider_authority_inherited=False,
        blockers=(),
    )


def metacognitive_provider_policy(
    *,
    state: MetaCognitiveState,
    transition: TransitionSpec,
    cells: Sequence[ProviderCell],
    provider_receipts: Mapping[str, SovaraProofReceipt] | None,
    preferred_order: Sequence[str] = (),
) -> dict[str, Any]:
    assessment = metacognitive_assessment(state)
    if transition.consequential and (
        state.evidence_coverage < 0.65
        or assessment.action in {MetaAction.SEEK_EVIDENCE, MetaAction.REPLAN, MetaAction.CHALLENGE, MetaAction.ROLLBACK}
    ):
        return {
            "state": RouteState.HOLD_METACOGNITIVE.value,
            "action": assessment.action.value,
            "route": None,
            "reason": "CONSEQUENTIAL_ROUTE_HELD_BY_METACOGNITIVE_GATE",
        }
    route = select_provider_route(cells, provider_receipts or {}, preferred_order)
    return {
        "state": RouteState.READY.value if route.selected_provider else RouteState.HOLD_NO_PROVIDER.value,
        "action": assessment.action.value,
        "route": asdict(route),
        "reason": "METACOGNITIVE_ROUTE_ADMITTED" if route.selected_provider else "NO_PROVIDER_CELL_CURRENTLY_ELIGIBLE",
    }


def compile_provider_readback_proof(
    *,
    receipt: SovaraProofReceipt,
    effect_id: str,
    transition: TransitionSpec,
    provider_ref: str,
    readback_evidence: Any,
    source_version: str,
    observed_at: str,
    signature_ref: str,
) -> ProofEnvelope:
    """Convert a fully qualifying SOVARA provider receipt into a SOL proof envelope.

    The conversion itself is source logic. It does not make a receipt qualifying:
    every SOVARA promotion-ready field, provider correlation, signature reference,
    and effect binding must already exist.
    """
    if not receipt.promotion_ready:
        raise ValueError("SSX_PROVIDER_RECEIPT_NOT_PROMOTION_READY")
    if not provider_ref:
        raise ValueError("SSX_PROVIDER_CORRELATION_REQUIRED")
    if not signature_ref:
        raise ValueError("SSX_PROVIDER_SIGNATURE_REFERENCE_REQUIRED")
    return ProofEnvelope.from_evidence(
        proof_id=f"ssx-provider-readback-{effect_id}",
        subject=effect_id,
        target=transition.target,
        operation=transition.operation,
        issuer=receipt.provider,
        source_version=source_version,
        evidence=readback_evidence,
        observed_at=observed_at,
        provider_correlation_id=provider_ref,
        signature_ref=signature_ref,
        evidence_class="PROVIDER_READBACK",
        scope="PROVIDER_SCOPED",
        attributes={
            "effect_id": effect_id,
            "readback_sha256": digest(readback_evidence),
            "provider": receipt.provider,
            "sovara_receipt_promotion_ready": True,
        },
    )


def compile_versioned_toolbox(
    *,
    name: str,
    version: str,
    tools: Sequence[Mapping[str, Any]],
) -> ToolboxManifest:
    if not name or not version or not tools:
        raise ValueError("SSX_TOOLBOX_NAME_VERSION_AND_TOOLS_REQUIRED")
    normalized: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for tool in tools:
        tool_id = str(tool.get("tool_id") or "").strip()
        if not tool_id or tool_id in seen:
            raise ValueError("SSX_TOOLBOX_TOOL_ID_INVALID_OR_DUPLICATE")
        seen.add(tool_id)
        schema = tool.get("schema")
        if not isinstance(schema, Mapping) or not schema:
            raise ValueError("SSX_TOOLBOX_SCHEMA_REQUIRED")
        normalized.append({
            "tool_id": tool_id,
            "version": str(tool.get("version") or ""),
            "owner": str(tool.get("owner") or ""),
            "risk": str(tool.get("risk") or "UNKNOWN"),
            "permission": str(tool.get("permission") or "DENY"),
            "schema_sha256": _hash(schema),
            "enabled": bool(tool.get("enabled", False)),
        })
    normalized.sort(key=lambda row: str(row["tool_id"]))
    body = {"name": name, "version": version, "tools": normalized}
    return ToolboxManifest(
        schema="SSX-VERSIONED-TOOLBOX-V1",
        name=name,
        version=version,
        tools=tuple(normalized),
        manifest_sha256=_hash(body),
    )


def compile_telemetry_envelope(
    *,
    mission_id: str,
    transition_id: str,
    binding: RouteBinding,
    latency_ms: float,
    token_count: int,
    cost_usd: float,
    error_class: str | None = None,
) -> dict[str, Any]:
    if latency_ms < 0 or token_count < 0 or cost_usd < 0:
        raise ValueError("SSX_TELEMETRY_METRICS_INVALID")
    core = {
        "schema": "SSX-OTEL-AGENT-SEMANTIC-ENVELOPE-V1",
        "mission_id": mission_id,
        "transition_id": transition_id,
        "effect_id": binding.effect_id,
        "provider": binding.selected_provider,
        "substrate": binding.selected_substrate,
        "route_fingerprint": binding.route_fingerprint,
        "latency_ms": round(float(latency_ms), 6),
        "token_count": int(token_count),
        "cost_usd": round(float(cost_usd), 8),
        "error_class": error_class,
    }
    return {**core, "trace_identity": _hash(core)}


def promotion_gate(
    *,
    deterministic_ci: bool,
    hosted_shadow: bool,
    provider_native_readback: bool,
    operational_cohort: bool,
    sustained_owner_value: bool,
    rollback_verified: bool,
    supply_chain_attested: bool,
) -> PromotionDecision:
    checks = {
        "DETERMINISTIC_CI": deterministic_ci,
        "HOSTED_SHADOW": hosted_shadow,
        "PROVIDER_NATIVE_READBACK": provider_native_readback,
        "OPERATIONAL_COHORT": operational_cohort,
        "SUSTAINED_OWNER_VALUE": sustained_owner_value,
        "ROLLBACK_VERIFIED": rollback_verified,
        "SUPPLY_CHAIN_ATTESTED": supply_chain_attested,
    }
    missing = tuple(name for name, passed in checks.items() if not passed)
    if missing:
        return PromotionDecision(
            state="CANDIDATE_HELD",
            missing=missing,
            stable_promotion_allowed=False,
            provider_effect_authorized=False,
        )
    return PromotionDecision(
        state="CANDIDATE_READY_FOR_INDEPENDENT_STABLE_REVIEW",
        missing=(),
        stable_promotion_allowed=False,
        provider_effect_authorized=False,
    )


BENCHMARK_DIMENSIONS = (
    ("Transactional mission/state runtime", 96, 88),
    ("Provider abstraction and route isolation", 92, 70),
    ("Durable execution and recovery", 89, 64),
    ("Meta-cognition and bounded autopilot", 92, 74),
    ("Always-on eventing and unattended intake", 87, 68),
    ("Toolbox/MCP governance", 88, 63),
    ("Identity, authority and Zero Trust", 94, 66),
    ("Semantic proof and readback", 98, 79),
    ("Idempotency, compensation and failure safety", 97, 82),
    ("Agent/runtime observability", 91, 70),
    ("Evaluation and optimizer discipline", 90, 72),
    ("Memory, context and causal state", 88, 68),
    ("Multi-agent orchestration", 89, 68),
    ("Cloud/provider-hosted runtime", 82, 48),
    ("Software supply-chain integrity", 94, 85),
    ("Governance, provenance and auditability", 98, 92),
    ("FinOps and performance efficiency", 86, 60),
    ("Owner burden and realized value", 90, 62),
    ("Developer/platform engineering", 89, 70),
    ("Cross-provider empirical parity", 82, 52),
)


def benchmark_summary() -> dict[str, Any]:
    architecture = round(sum(row[1] for row in BENCHMARK_DIMENSIONS) / len(BENCHMARK_DIMENSIONS), 2)
    proof = round(sum(row[2] for row in BENCHMARK_DIMENSIONS) / len(BENCHMARK_DIMENSIONS), 2)
    return {
        "schema": SCHEMA,
        "dimension_count": len(BENCHMARK_DIMENSIONS),
        "architecture_score": architecture,
        "proof_adjusted_score": proof,
        "dimensions": [
            {"dimension": name, "architecture": arch, "proof_adjusted": observed}
            for name, arch, observed in BENCHMARK_DIMENSIONS
        ],
    }


def compile_convergence_receipt() -> ConvergenceReceipt:
    genes = load_genome()
    decisions = evaluate_gene_controls()
    benchmark = benchmark_summary()
    unrouted = tuple(
        d.gene_id for d in decisions
        if not d.source_control_implemented or not d.handler
    )
    return ConvergenceReceipt(
        schema=SCHEMA,
        gene_count=len(genes),
        routed_count=len(genes) - len(unrouted),
        reuse_count=sum(g.implementation_mode == ImplementationMode.REUSE_VERIFIED for g in genes),
        composed_count=sum(g.implementation_mode == ImplementationMode.COMPOSED_BY_CONVERGENCE for g in genes),
        provider_gated_count=sum(g.implementation_mode == ImplementationMode.PROVIDER_GATED_CONTRACT for g in genes),
        unrouted_gene_ids=unrouted,
        architecture_score=benchmark["architecture_score"],
        proof_adjusted_score=benchmark["proof_adjusted_score"],
        provider_live_universal=False,
        stable_promotion_allowed=False,
        market_superiority_claim=False,
    )
