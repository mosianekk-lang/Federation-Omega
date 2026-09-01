from __future__ import annotations

"""CFBE Omega Federation Competitive Upgrade Fabric v1.

Compiles a 100-gene market-harvest genome into bounded, mission-specific controls.
It does not create a second scheduler, provider executor, memory service, or authority
plane. Reused capabilities keep their existing owners. Provider-gated genes remain
explicitly unproven until provider-native authority/readback exists.
"""

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import csv
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

from federation.mission_ir import MissionIR

GENOME_PATH = Path(__file__).with_name("FEDERATION_COMPETITIVE_UPGRADES_100_20260901.csv")
SCHEMA = "CFBE-FEDERATION-COMPETITIVE-UPGRADE-FABRIC-V1"


class ImplementationMode(str, Enum):
    REUSE_VERIFIED = "REUSE_VERIFIED"
    COMPOSED_BY_FABRIC = "COMPOSED_BY_FABRIC"
    PROVIDER_GATED_CONTRACT = "PROVIDER_GATED_CONTRACT"


class ControlBindingKind(str, Enum):
    REUSED_CONTROL_GATE = "REUSED_CONTROL_GATE"
    FABRIC_POLICY_GATE = "FABRIC_POLICY_GATE"
    PROVIDER_AUTHORITY_GATE = "PROVIDER_AUTHORITY_GATE"


class GeneControlState(str, Enum):
    HOLD_MISSING_PROOF = "HOLD_MISSING_PROOF"
    HOLD_PROVIDER_RUNTIME = "HOLD_PROVIDER_RUNTIME"
    READY_FOR_INDEPENDENT_READBACK = "READY_FOR_INDEPENDENT_READBACK"
    READY_FOR_PROVIDER_REVIEW = "READY_FOR_PROVIDER_REVIEW"


class RouteClass(str, Enum):
    DIRECT = "DIRECT"
    PARALLEL = "PARALLEL"
    MULTI_AGENT = "MULTI_AGENT"
    ADVERSARIAL = "ADVERSARIAL"
    EFFECT = "EFFECT"


class ReleaseStage(str, Enum):
    HOLD = "HOLD"
    SHADOW = "SHADOW"
    CANARY = "CANARY"
    STABLE_REVIEW = "STABLE_REVIEW"


@dataclass(frozen=True, slots=True)
class CapabilityGene:
    gene_id: str
    domain: str
    improvement: str
    leader_pattern: str
    implementation_mode: ImplementationMode
    implementation_target: str
    acceptance_gate: str
    priority: int
    wave: str
    control_family: str


@dataclass(frozen=True, slots=True)
class ControlBinding:
    gene_id: str
    kind: ControlBindingKind
    handler_name: str
    required_evidence: tuple[str, ...]
    source_control_implemented: bool


@dataclass(frozen=True, slots=True)
class GeneControlDecision:
    gene_id: str
    state: GeneControlState
    binding_kind: ControlBindingKind
    handler_name: str
    missing_evidence: tuple[str, ...]
    source_control_implemented: bool
    runtime_proven: bool
    stable_promotion_allowed: bool
    provider_effect_authorized: bool


@dataclass(frozen=True, slots=True)
class ResolvedEvidenceRef:
    """Integrity-bound evidence state produced by a trusted resolver.

    A URI-shaped string is not evidence.  This type records the resolver result;
    it still does not grant runtime, provider-effect, or promotion authority.
    """

    evidence_id: str
    subject: str
    verifier_id: str
    payload_sha256: str
    receipt_sha256: str
    independently_read_back: bool

    def valid(self) -> bool:
        digests = (self.payload_sha256, self.receipt_sha256)
        return bool(
            self.evidence_id.strip()
            and self.subject.strip()
            and self.verifier_id.strip()
            and self.independently_read_back
            and all(
                value.startswith("sha256:")
                and len(value) == 71
                and all(character in "0123456789abcdef" for character in value[7:].lower())
                for value in digests
            )
        )


@dataclass(frozen=True, slots=True)
class BenchmarkDimension:
    name: str
    current_design_score: float
    proof_adjusted_operational_score: float
    target_score: float


@dataclass(frozen=True, slots=True)
class ErrorBudgetAssessment:
    slo_target: float
    observed_success_rate: float
    error_budget_fraction_remaining: float
    state: str


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int
    base_delay_ms: int
    max_delay_ms: int
    idempotency_required: bool

    def delay_ms(self, attempt: int, identity: str) -> int:
        if attempt < 1:
            raise ValueError("RETRY_ATTEMPT_INVALID")
        raw = min(self.max_delay_ms, self.base_delay_ms * (2 ** (attempt - 1)))
        digest = int(sha256(f"{identity}:{attempt}".encode()).hexdigest()[:8], 16)
        jitter = digest % max(1, raw // 5 + 1)
        return min(self.max_delay_ms, raw + jitter)


@dataclass(frozen=True, slots=True)
class CircuitBreakerPolicy:
    failure_threshold: int = 3
    recovery_success_threshold: int = 2

    def state(self, consecutive_failures: int, consecutive_recovery_successes: int = 0) -> str:
        if consecutive_failures >= self.failure_threshold:
            if consecutive_recovery_successes >= self.recovery_success_threshold:
                return "HALF_OPEN"
            return "OPEN"
        return "CLOSED"


@dataclass(frozen=True, slots=True)
class RetentionDecision:
    tier: str
    retain_payload: bool
    retain_metadata: bool
    ttl_days: int | None


@dataclass(frozen=True, slots=True)
class ProgressiveDeliveryDecision:
    stage: ReleaseStage
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompetitiveMissionProfile:
    schema: str
    mission_id: str
    route_class: RouteClass
    active_gene_ids: tuple[str, ...]
    reused_gene_ids: tuple[str, ...]
    composed_gene_ids: tuple[str, ...]
    provider_gated_gene_ids: tuple[str, ...]
    required_control_families: tuple[str, ...]
    truth_boundary: tuple[str, ...]


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(v).strip() for v in values if str(v).strip()}))


def load_genome(path: Path = GENOME_PATH) -> tuple[CapabilityGene, ...]:
    rows: list[CapabilityGene] = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            rows.append(
                CapabilityGene(
                    gene_id=row["id"],
                    domain=row["domain"],
                    improvement=row["improvement"],
                    leader_pattern=row["leader_pattern"],
                    implementation_mode=ImplementationMode(row["implementation_mode"]),
                    implementation_target=row["implementation_target"],
                    acceptance_gate=row["acceptance_gate"],
                    priority=int(row["priority"]),
                    wave=row["wave"],
                    control_family=row["control_family"],
                )
            )
    validate_genome(tuple(rows))
    return tuple(rows)


def validate_genome(genes: Sequence[CapabilityGene]) -> None:
    if len(genes) != 100:
        raise ValueError(f"COMPETITIVE_GENOME_EXPECTED_100_GOT_{len(genes)}")
    ids = [g.gene_id for g in genes]
    if len(set(ids)) != len(ids):
        raise ValueError("COMPETITIVE_GENOME_DUPLICATE_ID")
    if ids != [f"FHU-{i:03d}" for i in range(1, 101)]:
        raise ValueError("COMPETITIVE_GENOME_ID_SEQUENCE_INVALID")
    for gene in genes:
        if not gene.domain or not gene.improvement or not gene.acceptance_gate:
            raise ValueError(f"COMPETITIVE_GENOME_INCOMPLETE:{gene.gene_id}")
        if not 1 <= gene.priority <= 100:
            raise ValueError(f"COMPETITIVE_GENOME_PRIORITY_INVALID:{gene.gene_id}")


_BINDING_CONTRACTS: Mapping[ImplementationMode, tuple[ControlBindingKind, str, tuple[str, ...]]] = {
    ImplementationMode.REUSE_VERIFIED: (
        ControlBindingKind.REUSED_CONTROL_GATE,
        "require_reuse_proof",
        ("source_proof", "test_proof", "registration_proof"),
    ),
    ImplementationMode.COMPOSED_BY_FABRIC: (
        ControlBindingKind.FABRIC_POLICY_GATE,
        "require_composition_proof",
        ("source_binding", "test_proof", "owner_binding"),
    ),
    ImplementationMode.PROVIDER_GATED_CONTRACT: (
        ControlBindingKind.PROVIDER_AUTHORITY_GATE,
        "require_provider_native_proof",
        ("provider_authority", "provider_readback", "test_proof"),
    ),
}


def _require_reuse_proof(missing: tuple[str, ...]) -> GeneControlState:
    return GeneControlState.HOLD_MISSING_PROOF if missing else GeneControlState.READY_FOR_INDEPENDENT_READBACK


def _require_composition_proof(missing: tuple[str, ...]) -> GeneControlState:
    return GeneControlState.HOLD_MISSING_PROOF if missing else GeneControlState.READY_FOR_INDEPENDENT_READBACK


def _require_provider_native_proof(missing: tuple[str, ...]) -> GeneControlState:
    return GeneControlState.HOLD_PROVIDER_RUNTIME if missing else GeneControlState.READY_FOR_PROVIDER_REVIEW


_EXECUTABLE_HANDLERS: Mapping[str, Callable[[tuple[str, ...]], GeneControlState]] = {
    "require_reuse_proof": _require_reuse_proof,
    "require_composition_proof": _require_composition_proof,
    "require_provider_native_proof": _require_provider_native_proof,
}


def compile_control_bindings(genes: Sequence[CapabilityGene] | None = None) -> tuple[ControlBinding, ...]:
    """Compile one executable, fail-closed control binding per catalog gene.

    A binding implements the source-level admission policy. It does not prove the
    target capability is deployed, provider-backed, valuable, or promotion-ready.
    """

    items = tuple(genes) if genes is not None else load_genome()
    validate_genome(items)
    bindings = tuple(
        ControlBinding(
            gene_id=gene.gene_id,
            kind=_BINDING_CONTRACTS[gene.implementation_mode][0],
            handler_name=_BINDING_CONTRACTS[gene.implementation_mode][1],
            required_evidence=_BINDING_CONTRACTS[gene.implementation_mode][2],
            source_control_implemented=True,
        )
        for gene in items
    )
    if len(bindings) != 100 or len({item.gene_id for item in bindings}) != 100:
        raise ValueError("COMPETITIVE_BINDING_COVERAGE_INVALID")
    if any(item.handler_name not in _EXECUTABLE_HANDLERS for item in bindings):
        raise ValueError("COMPETITIVE_BINDING_HANDLER_MISSING")
    return bindings


def _is_proof_ref(value: object) -> bool:
    return isinstance(value, ResolvedEvidenceRef) and value.valid()


def evaluate_gene_control(gene_id: str, evidence: Mapping[str, object] | None = None) -> GeneControlDecision:
    """Evaluate a gene's exact proof contract without granting runtime authority."""

    genes = {gene.gene_id: gene for gene in load_genome()}
    bindings = {binding.gene_id: binding for binding in compile_control_bindings(tuple(genes.values()))}
    if gene_id not in genes:
        raise ValueError(f"COMPETITIVE_GENE_UNKNOWN:{gene_id}")
    gene = genes[gene_id]
    binding = bindings[gene_id]
    supplied = evidence or {}
    missing = tuple(key for key in binding.required_evidence if not _is_proof_ref(supplied.get(key)))
    handler = _EXECUTABLE_HANDLERS[binding.handler_name]
    state = handler(missing)
    return GeneControlDecision(
        gene_id=gene_id,
        state=state,
        binding_kind=binding.kind,
        handler_name=binding.handler_name,
        missing_evidence=missing,
        source_control_implemented=True,
        runtime_proven=False,
        stable_promotion_allowed=False,
        provider_effect_authorized=False,
    )


def executable_binding_summary() -> dict[str, object]:
    bindings = compile_control_bindings()
    return {
        "gene_count": 100,
        "executable_binding_count": len(bindings),
        "unique_handler_count": len({item.handler_name for item in bindings}),
        "all_fail_closed_without_proof": all(
            evaluate_gene_control(item.gene_id).state
            in {GeneControlState.HOLD_MISSING_PROOF, GeneControlState.HOLD_PROVIDER_RUNTIME}
            for item in bindings
        ),
        "stable_promotion_allowed": False,
        "provider_effect_authorized": False,
    }


def error_budget_assessment(*, total: int, successful: int, slo_target: float = 0.999) -> ErrorBudgetAssessment:
    if total <= 0 or successful < 0 or successful > total:
        raise ValueError("ERROR_BUDGET_SAMPLE_INVALID")
    if not 0 < slo_target < 1:
        raise ValueError("ERROR_BUDGET_SLO_INVALID")
    rate = successful / total
    allowed_failure = 1.0 - slo_target
    actual_failure = 1.0 - rate
    remaining = max(-1.0, min(1.0, 1.0 - actual_failure / allowed_failure))
    state = "HEALTHY"
    if remaining <= 0:
        state = "EXHAUSTED"
    elif remaining < 0.25:
        state = "CRITICAL"
    elif remaining < 0.5:
        state = "WATCH"
    return ErrorBudgetAssessment(slo_target, rate, remaining, state)


def retention_policy(privacy_class: str, age_days: int) -> RetentionDecision:
    privacy = privacy_class.strip().upper()
    if age_days < 0:
        raise ValueError("RETENTION_AGE_INVALID")
    if privacy in {"SECRET", "HIGHLY_SENSITIVE"}:
        return RetentionDecision("COLD_POINTER_ONLY", False, True, 30)
    if privacy in {"PRIVATE", "RESTRICTED"}:
        return RetentionDecision("WARM_POINTER_FIRST", False, True, 365)
    if age_days <= 14:
        return RetentionDecision("HOT", True, True, 3650)
    if age_days <= 90:
        return RetentionDecision("WARM", True, True, 3650)
    return RetentionDecision("COLD", False, True, None)


def orchestration_route(mission: MissionIR, *, dependency_count: int = 0, uncertainty: float = 0.0) -> RouteClass:
    item = mission.normalized()
    item.validate()
    if dependency_count < 0 or not 0 <= uncertainty <= 1:
        raise ValueError("ORCHESTRATION_ROUTE_INPUT_INVALID")
    if item.effect_class not in {"NO_EFFECT", "READ_ONLY"}:
        return RouteClass.EFFECT
    if item.owner_approval_required or uncertainty >= 0.75:
        return RouteClass.ADVERSARIAL
    if dependency_count >= 8:
        return RouteClass.MULTI_AGENT
    if dependency_count >= 3:
        return RouteClass.PARALLEL
    return RouteClass.DIRECT


def progressive_delivery_gate(*, source_admitted: bool, deterministic_tests_pass: bool, shadow_pairs: int, hard_regressions: int, provider_readback: bool, observed_owner_value: bool) -> ProgressiveDeliveryDecision:
    if not source_admitted or not deterministic_tests_pass or hard_regressions:
        return ProgressiveDeliveryDecision(ReleaseStage.HOLD, ("source_or_test_gate_failed",))
    if shadow_pairs < 10:
        return ProgressiveDeliveryDecision(ReleaseStage.SHADOW, ("insufficient_shadow_evidence",))
    if not provider_readback:
        return ProgressiveDeliveryDecision(ReleaseStage.CANARY, ("provider_readback_open",))
    if not observed_owner_value:
        return ProgressiveDeliveryDecision(ReleaseStage.CANARY, ("owner_value_open",))
    return ProgressiveDeliveryDecision(ReleaseStage.STABLE_REVIEW, ())


def supply_chain_gate(*, provenance: bool, pinned_dependencies: bool, sbom: bool, artifact_attestation: bool, release_requires_attestation: bool) -> tuple[bool, tuple[str, ...]]:
    missing: list[str] = []
    if not provenance:
        missing.append("provenance")
    if not pinned_dependencies:
        missing.append("pinned_dependencies")
    if not sbom:
        missing.append("sbom")
    if release_requires_attestation and not artifact_attestation:
        missing.append("artifact_attestation")
    return not missing, tuple(missing)


def operational_readiness_gate(evidence: Mapping[str, bool]) -> tuple[bool, tuple[str, ...]]:
    required = ("rollback", "observability", "runbook", "capacity", "security", "recovery", "proof_readback")
    missing = tuple(name for name in required if not bool(evidence.get(name)))
    return not missing, missing


def flake_classification(*, failures: int, passes: int, repeated_same_failure: bool) -> str:
    if failures < 0 or passes < 0:
        raise ValueError("FLAKE_COUNTS_INVALID")
    if failures == 0:
        return "CLEAN"
    if repeated_same_failure and passes == 0:
        return "DETERMINISTIC_FAILURE"
    if failures > 0 and passes > 0:
        return "FLAKY_QUARANTINE"
    return "INVESTIGATE"


def benchmark_dimensions() -> tuple[BenchmarkDimension, ...]:
    # CFBE heuristic engineering scores; not vendor-certified rankings.
    values = (
        ("Mission & Orchestration", 86, 72, 97),
        ("Durable Memory & State", 91, 76, 98),
        ("Reliability & Recovery", 84, 68, 97),
        ("Observability & Incident Intelligence", 86, 66, 97),
        ("Security & Supply Chain", 88, 70, 98),
        ("Testing, Evals & Proof", 94, 83, 98),
        ("Performance, Cost & Context", 86, 69, 96),
        ("Developer & Platform Engineering", 83, 68, 96),
        ("AI Agent Intelligence & Guardrails", 85, 64, 97),
        ("Governance, Value & Learning", 90, 70, 98),
    )
    return tuple(BenchmarkDimension(name, float(current), float(ops), float(target)) for name, current, ops, target in values)


def compile_competitive_profile(mission: MissionIR, *, dependency_count: int = 0, uncertainty: float = 0.0, available_control_families: Iterable[str] = ()) -> CompetitiveMissionProfile:
    genes = load_genome()
    item = mission.normalized()
    item.validate()
    route = orchestration_route(item, dependency_count=dependency_count, uncertainty=uncertainty)
    universal = {"RELIABILITY", "SUPPLY_CHAIN_SECURITY", "PROOF_EVAL", "BUDGET_PERFORMANCE", "GOVERNANCE_VALUE"}
    if route in {RouteClass.MULTI_AGENT, RouteClass.ADVERSARIAL, RouteClass.EFFECT}:
        universal.add("AGENT_GUARDRAILS")
    if dependency_count >= 3:
        universal.add("ORCHESTRATION")
    objective = item.objective.casefold()
    if any(term in objective for term in ("memory", "state", "history", "continuity")):
        universal.add("MEMORY")
    if route == RouteClass.EFFECT:
        universal.update({"OBSERVABILITY", "PLATFORM_DELIVERY"})
    supplied = set(_clean(available_control_families))
    active = tuple(g for g in genes if g.wave == "W1" and (g.control_family in universal or g.control_family in supplied))
    return CompetitiveMissionProfile(
        schema=SCHEMA,
        mission_id=item.mission_id,
        route_class=route,
        active_gene_ids=tuple(g.gene_id for g in active),
        reused_gene_ids=tuple(g.gene_id for g in active if g.implementation_mode == ImplementationMode.REUSE_VERIFIED),
        composed_gene_ids=tuple(g.gene_id for g in active if g.implementation_mode == ImplementationMode.COMPOSED_BY_FABRIC),
        provider_gated_gene_ids=tuple(g.gene_id for g in active if g.implementation_mode == ImplementationMode.PROVIDER_GATED_CONTRACT),
        required_control_families=tuple(sorted(universal | supplied)),
        truth_boundary=(
            "source_composition_does_not_prove_provider_runtime",
            "provider_gated_genes_never_inherit_authority",
            "heuristic_benchmark_scores_are_not_vendor_certification",
            "stable_promotion_requires_independent_observed_value_and_readback",
        ),
    )


def benchmark_summary() -> dict[str, object]:
    genes = load_genome()
    dims = benchmark_dimensions()
    return {
        "schema": SCHEMA,
        "gene_count": len(genes),
        "reuse_verified": sum(g.implementation_mode == ImplementationMode.REUSE_VERIFIED for g in genes),
        "composed_by_fabric": sum(g.implementation_mode == ImplementationMode.COMPOSED_BY_FABRIC for g in genes),
        "provider_gated_contract": sum(g.implementation_mode == ImplementationMode.PROVIDER_GATED_CONTRACT for g in genes),
        "current_design_score": round(sum(d.current_design_score for d in dims) / len(dims), 2),
        "proof_adjusted_operational_score": round(sum(d.proof_adjusted_operational_score for d in dims) / len(dims), 2),
        "target_score": round(sum(d.target_score for d in dims) / len(dims), 2),
        "stable_promotion_allowed": False,
        "provider_effect_authorized": False,
    }
