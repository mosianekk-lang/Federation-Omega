from __future__ import annotations

"""CFBE Ω-HARVEST MAX v2 — deep mechanism-mining extension.

This module *extends* the admitted CFBE Wave-2 scientific capability compiler.
It is not a new sovereign scheduler, memory root, provider executor, proof plane,
or authority plane. The focus is deeper public-source archaeology, negative-
evidence harvesting, experiment fairness, and receiver-local capability genetics.

External/provider effects remain disabled. Public evidence, repository source,
benchmarks, history, licenses, advisories, and standards are candidate evidence;
none of them alone prove provider deployment, market superiority, or owner value.
"""

from dataclasses import asdict, dataclass, field
from enum import IntEnum, Enum
import ast
from hashlib import sha256
import json
import math
import re
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "CFBE_OMEGA_HARVEST_MAX_V2"
BASE_COMPILER = "benchmarking.cfbe_omega.scientific_capability_compiler_v2"

# These are Wave-2 genes that previously existed as source/admission contracts but
# are deepened here with deterministic executable courts. No new gene namespace is
# created: this is a receiver-local extension of the existing 100-gene genome.
DEEPENED_GENE_IDS = frozenset({
    "CF2-004", "CF2-005", "CF2-006", "CF2-007", "CF2-009",
    "CF2-010", "CF2-011", "CF2-012", "CF2-014", "CF2-017",
    "CF2-018", "CF2-019", "CF2-022", "CF2-024", "CF2-025",
    "CF2-026", "CF2-027", "CF2-028", "CF2-029", "CF2-030",
})

ARCHAEOLOGY_STAGES = (
    "FRONTIER_CENSUS",
    "PROVENANCE_AND_LICENSE",
    "REPOSITORY_TOPOLOGY",
    "DEPENDENCY_GRAPH",
    "SYNTAX_AND_STRUCTURAL_IR",
    "CALL_DATA_STATE_FLOW",
    "CONCURRENCY_AND_RECOVERY",
    "PERFORMANCE_AND_RESOURCE_MODEL",
    "EVOLUTION_HISTORY",
    "FAILURE_SECURITY_NEGATIVE_EVIDENCE",
    "BENCHMARK_COMPARABILITY",
    "MECHANISM_AND_PRIMITIVE_EXTRACTION",
    "CLEAN_ROOM_CAPABILITY_GENE",
    "RECEIVER_EXPERIMENT_AND_VALUE",
)


class HarvestDepth(IntEnum):
    H0_SIGNAL = 0
    H1_PRODUCT = 1
    H2_SOURCE = 2
    H3_EXECUTION = 3
    H4_PERFORMANCE = 4
    H5_EVOLUTION = 5
    H6_NEGATIVE = 6
    H7_GENE = 7
    H8_CANDIDATE = 8
    H9_EMPIRICAL = 9
    H10_VALUE = 10


class SourceFamily(str, Enum):
    OFFICIAL_DOC = "OFFICIAL_DOC"
    STANDARD = "STANDARD"
    SOURCE_CODE = "SOURCE_CODE"
    TEST = "TEST"
    BENCHMARK = "BENCHMARK"
    RELEASE_NOTE = "RELEASE_NOTE"
    COMMIT = "COMMIT"
    PULL_REQUEST = "PULL_REQUEST"
    ISSUE = "ISSUE"
    SECURITY_ADVISORY = "SECURITY_ADVISORY"
    PACKAGE_METADATA = "PACKAGE_METADATA"
    RESEARCH = "RESEARCH"


class HarvestDisposition(str, Enum):
    REUSE = "REUSE"
    EXTEND = "EXTEND"
    COMPOSE = "COMPOSE"
    CLEAN_ROOM_REIMPLEMENT = "CLEAN_ROOM_REIMPLEMENT"
    EXPERIMENT = "EXPERIMENT"
    HOLD = "HOLD"
    REJECT = "REJECT"


def _hash(value: Any) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("utf-8")
    ).hexdigest()


def _norm_items(values: Iterable[Any] | None) -> tuple[str, ...]:
    return tuple(sorted({str(v).strip() for v in (values or ()) if str(v).strip()}))


def _tokens(value: str) -> frozenset[str]:
    return frozenset(t for t in re.findall(r"[a-z0-9_]+", str(value).lower()) if len(t) > 1)


def _jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    left, right = set(a), set(b)
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _clamp01(v: float) -> float:
    return min(1.0, max(0.0, float(v)))


@dataclass(frozen=True, slots=True)
class SourceEvidence:
    source_id: str
    family: SourceFamily
    locator: str
    content_sha256: str
    observed_at: str
    authority_weight: float
    independent_group: str
    license_spdx: str = ""
    public_evidence: bool = True
    negative_evidence: bool = False

    def validate(self) -> "SourceEvidence":
        if not self.source_id or not self.locator or len(self.content_sha256) != 64:
            raise ValueError("HARVEST_SOURCE_ID_LOCATOR_DIGEST_REQUIRED")
        if not 0 <= self.authority_weight <= 1:
            raise ValueError("HARVEST_SOURCE_AUTHORITY_WEIGHT_INVALID")
        if not self.public_evidence:
            raise ValueError("HARVEST_MAX_PUBLIC_EVIDENCE_ONLY")
        if not self.independent_group:
            raise ValueError("HARVEST_SOURCE_INDEPENDENCE_GROUP_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class SourceUniversePlan:
    mission_id: str
    capability_query: str
    required_families: tuple[SourceFamily, ...]
    optional_families: tuple[SourceFamily, ...]
    max_sources_per_family: int = 8
    delta_first: bool = True
    public_only: bool = True

    def validate(self) -> "SourceUniversePlan":
        if not self.mission_id or not self.capability_query:
            raise ValueError("HARVEST_SOURCE_PLAN_MISSION_QUERY_REQUIRED")
        if self.max_sources_per_family < 1:
            raise ValueError("HARVEST_SOURCE_PLAN_LIMIT_INVALID")
        if not self.required_families:
            raise ValueError("HARVEST_SOURCE_PLAN_REQUIRED_FAMILIES_EMPTY")
        if not self.public_only:
            raise ValueError("HARVEST_PRIVATE_SOURCE_DISCOVERY_PROHIBITED")
        return self


def default_source_universe(mission_id: str, capability_query: str) -> SourceUniversePlan:
    return SourceUniversePlan(
        mission_id=mission_id.strip(),
        capability_query=capability_query.strip(),
        required_families=(
            SourceFamily.OFFICIAL_DOC,
            SourceFamily.SOURCE_CODE,
            SourceFamily.TEST,
            SourceFamily.BENCHMARK,
            SourceFamily.COMMIT,
            SourceFamily.ISSUE,
        ),
        optional_families=(
            SourceFamily.STANDARD,
            SourceFamily.RELEASE_NOTE,
            SourceFamily.PULL_REQUEST,
            SourceFamily.SECURITY_ADVISORY,
            SourceFamily.PACKAGE_METADATA,
            SourceFamily.RESEARCH,
        ),
    ).validate()


@dataclass(frozen=True, slots=True)
class HarvestCursor:
    source_hashes: Mapping[str, str] = field(default_factory=dict)

    def changed(self, evidence: SourceEvidence) -> bool:
        evidence.validate()
        return self.source_hashes.get(evidence.source_id) != evidence.content_sha256

    def advance(self, evidence: Sequence[SourceEvidence]) -> "HarvestCursor":
        out = dict(self.source_hashes)
        for item in evidence:
            item.validate()
            out[item.source_id] = item.content_sha256
        return HarvestCursor(source_hashes=out)


@dataclass(frozen=True, slots=True)
class RepositoryFileSignal:
    path: str
    bytes_size: int
    symbol_hits: int = 0
    change_count: int = 0
    benchmark_hits: int = 0
    test_hits: int = 0
    dependency_centrality: float = 0.0
    failure_hits: int = 0

    def score(self) -> float:
        size_penalty = math.log10(max(self.bytes_size, 10)) / 8.0
        raw = (
            2.5 * self.symbol_hits
            + 1.4 * self.change_count
            + 2.4 * self.benchmark_hits
            + 2.0 * self.test_hits
            + 3.0 * _clamp01(self.dependency_centrality)
            + 2.6 * self.failure_hits
            - size_penalty
        )
        return round(raw, 6)


def plan_repository_slice(files: Sequence[RepositoryFileSignal], *, limit: int = 25) -> tuple[RepositoryFileSignal, ...]:
    if limit < 1:
        raise ValueError("HARVEST_SLICE_LIMIT_INVALID")
    unique: dict[str, RepositoryFileSignal] = {}
    for item in files:
        if not item.path or item.bytes_size < 0:
            raise ValueError("HARVEST_FILE_SIGNAL_INVALID")
        prior = unique.get(item.path)
        if prior is None or item.score() > prior.score():
            unique[item.path] = item
    return tuple(sorted(unique.values(), key=lambda x: (-x.score(), x.path))[:limit])


@dataclass(frozen=True, slots=True)
class StructuralFingerprint:
    language: str
    node_types: tuple[str, ...]
    call_names: tuple[str, ...]
    async_count: int
    loop_count: int
    branch_count: int
    exception_count: int
    stateful_count: int
    digest_sha256: str


def python_structural_fingerprint(source: str) -> StructuralFingerprint:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError("HARVEST_PYTHON_PARSE_FAILED") from exc
    node_types: list[str] = []
    calls: list[str] = []
    async_count = loop_count = branch_count = exception_count = stateful_count = 0
    for node in ast.walk(tree):
        name = type(node).__name__
        node_types.append(name)
        if isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.AsyncFor, ast.AsyncWith)):
            async_count += 1
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While, ast.comprehension)):
            loop_count += 1
        if isinstance(node, (ast.If, ast.IfExp, ast.Match)):
            branch_count += 1
        if isinstance(node, (ast.Try, ast.Raise, ast.ExceptHandler)):
            exception_count += 1
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            stateful_count += 1
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.append(node.func.attr)
    payload = {
        "language": "python",
        "node_types": sorted(node_types),
        "call_names": sorted(calls),
        "async_count": async_count,
        "loop_count": loop_count,
        "branch_count": branch_count,
        "exception_count": exception_count,
        "stateful_count": stateful_count,
    }
    return StructuralFingerprint(
        language="python",
        node_types=tuple(payload["node_types"]),
        call_names=tuple(payload["call_names"]),
        async_count=async_count,
        loop_count=loop_count,
        branch_count=branch_count,
        exception_count=exception_count,
        stateful_count=stateful_count,
        digest_sha256=_hash(payload),
    )


def structural_similarity(left: StructuralFingerprint, right: StructuralFingerprint) -> float:
    node = _jaccard(left.node_types, right.node_types)
    calls = _jaccard(left.call_names, right.call_names)
    counts_left = (left.async_count, left.loop_count, left.branch_count, left.exception_count, left.stateful_count)
    counts_right = (right.async_count, right.loop_count, right.branch_count, right.exception_count, right.stateful_count)
    denom = sum(max(a, b) for a, b in zip(counts_left, counts_right)) or 1
    count_similarity = 1.0 - sum(abs(a - b) for a, b in zip(counts_left, counts_right)) / denom
    return round(_clamp01(0.45 * node + 0.35 * calls + 0.20 * count_similarity), 6)


@dataclass(frozen=True, slots=True)
class CapabilityMechanism:
    capability_id: str
    objective: str
    primitives: tuple[str, ...]
    invariants: tuple[str, ...]
    outputs: tuple[str, ...]
    dependencies: tuple[str, ...]
    failure_modes: tuple[str, ...]

    def validate(self) -> "CapabilityMechanism":
        if not self.capability_id or not self.objective or not self.primitives:
            raise ValueError("HARVEST_MECHANISM_ID_OBJECTIVE_PRIMITIVES_REQUIRED")
        return self


def capability_equivalence(left: CapabilityMechanism, right: CapabilityMechanism) -> float:
    left.validate(); right.validate()
    scores = (
        _jaccard(_tokens(left.objective), _tokens(right.objective)),
        _jaccard(left.primitives, right.primitives),
        _jaccard(left.invariants, right.invariants),
        _jaccard(left.outputs, right.outputs),
        _jaccard(left.dependencies, right.dependencies),
    )
    weights = (0.20, 0.35, 0.20, 0.15, 0.10)
    return round(sum(w * s for w, s in zip(weights, scores)), 6)


@dataclass(frozen=True, slots=True)
class SupersetReceipt:
    candidate_id: str
    incumbent_id: str
    primitive_coverage: float
    invariant_coverage: float
    output_coverage: float
    missing_incumbent_requirements: tuple[str, ...]
    candidate_extras: tuple[str, ...]
    is_superset: bool


def capability_superset(candidate: CapabilityMechanism, incumbent: CapabilityMechanism) -> SupersetReceipt:
    candidate.validate(); incumbent.validate()
    c_pr, i_pr = set(candidate.primitives), set(incumbent.primitives)
    c_inv, i_inv = set(candidate.invariants), set(incumbent.invariants)
    c_out, i_out = set(candidate.outputs), set(incumbent.outputs)
    def coverage(c: set[str], i: set[str]) -> float:
        return 1.0 if not i else len(c & i) / len(i)
    missing = sorted((i_pr - c_pr) | (i_inv - c_inv) | (i_out - c_out))
    extras = sorted((c_pr - i_pr) | (c_inv - i_inv) | (c_out - i_out))
    p, inv, out = coverage(c_pr, i_pr), coverage(c_inv, i_inv), coverage(c_out, i_out)
    return SupersetReceipt(
        candidate_id=candidate.capability_id,
        incumbent_id=incumbent.capability_id,
        primitive_coverage=round(p, 6),
        invariant_coverage=round(inv, 6),
        output_coverage=round(out, 6),
        missing_incumbent_requirements=tuple(missing),
        candidate_extras=tuple(extras),
        is_superset=(not missing and bool(extras)),
    )


@dataclass(frozen=True, slots=True)
class FrontierFreshness:
    age_days: float
    nominal_half_life_days: float
    drift_events: int = 0
    release_events: int = 0


def frontier_freshness_score(value: FrontierFreshness) -> float:
    if value.nominal_half_life_days <= 0 or value.age_days < 0 or value.drift_events < 0 or value.release_events < 0:
        raise ValueError("HARVEST_FRONTIER_FRESHNESS_INPUT_INVALID")
    decay = 0.5 ** (value.age_days / value.nominal_half_life_days)
    pressure = 1.0 / (1.0 + 0.20 * value.drift_events + 0.10 * value.release_events)
    return round(_clamp01(decay * pressure), 6)


def standardization_momentum(*, independent_implementations: int, vendors: int, standards_releases: int, months_observed: float) -> float:
    if min(independent_implementations, vendors, standards_releases) < 0 or months_observed <= 0:
        raise ValueError("HARVEST_STANDARD_MOMENTUM_INPUT_INVALID")
    implementation_signal = 1.0 - math.exp(-independent_implementations / 4.0)
    vendor_signal = 1.0 - math.exp(-vendors / 5.0)
    release_rate = standards_releases / months_observed
    release_signal = 1.0 - math.exp(-release_rate * 4.0)
    return round(_clamp01(0.45 * implementation_signal + 0.35 * vendor_signal + 0.20 * release_signal), 6)


@dataclass(frozen=True, slots=True)
class NegativeFinding:
    finding_id: str
    failure_mode: str
    causal_mechanism: str
    rejected_approach: str
    recovery_pattern: str
    evidence_refs: tuple[str, ...]


def harvest_negative_design(findings: Sequence[NegativeFinding]) -> tuple[str, ...]:
    rules: set[str] = set()
    for item in findings:
        if not item.finding_id or not item.failure_mode or not item.causal_mechanism or not item.evidence_refs:
            raise ValueError("HARVEST_NEGATIVE_FINDING_PROOF_REQUIRED")
        bad = item.rejected_approach.strip() or item.causal_mechanism.strip()
        repair = item.recovery_pattern.strip() or "require an independently verified alternative"
        rules.add(f"DO_NOT_REPEAT[{bad}] WHEN[{item.causal_mechanism}]; PREFER[{repair}]")
    return tuple(sorted(rules))


@dataclass(frozen=True, slots=True)
class EvolutionChange:
    change_id: str
    message: str
    changed_paths: tuple[str, ...]
    additions: int
    deletions: int
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvolutionMiningReceipt:
    change_count: int
    performance_changes: tuple[str, ...]
    regression_or_revert_changes: tuple[str, ...]
    security_changes: tuple[str, ...]
    architecture_changes: tuple[str, ...]
    test_or_benchmark_changes: tuple[str, ...]
    hotspot_paths: tuple[str, ...]


def mine_evolution_history(changes: Sequence[EvolutionChange], *, hotspot_limit: int = 10) -> EvolutionMiningReceipt:
    if hotspot_limit < 1:
        raise ValueError("HARVEST_EVOLUTION_HOTSPOT_LIMIT_INVALID")
    perf: list[str] = []; regress: list[str] = []; security: list[str] = []; architecture: list[str] = []; tests: list[str] = []
    path_counts: dict[str, int] = {}
    for item in changes:
        if not item.change_id or item.additions < 0 or item.deletions < 0 or not item.evidence_refs:
            raise ValueError("HARVEST_EVOLUTION_CHANGE_PROOF_REQUIRED")
        text = item.message.casefold()
        if re.search(r"\b(perf|performance|latency|throughput|speed|faster|optimi[sz]|cache|batch|memory)\b", text):
            perf.append(item.change_id)
        if re.search(r"\b(revert|rollback|regression|restore|backout|degrad|slowdown)\b", text):
            regress.append(item.change_id)
        if re.search(r"\b(security|cve|vulnerab|auth|permission|secret|sandbox|injection|taint)\b", text):
            security.append(item.change_id)
        if re.search(r"\b(architecture|refactor|scheduler|queue|pipeline|runtime|worker|shard|distributed|async|concurr)\b", text):
            architecture.append(item.change_id)
        if re.search(r"\b(test|benchmark|eval|fixture|fuzz|canary|shadow)\b", text):
            tests.append(item.change_id)
        for path in item.changed_paths:
            path_counts[path] = path_counts.get(path, 0) + 1
    hotspots = tuple(path for path, _ in sorted(path_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:hotspot_limit])
    return EvolutionMiningReceipt(
        change_count=len(changes), performance_changes=tuple(sorted(perf)),
        regression_or_revert_changes=tuple(sorted(regress)), security_changes=tuple(sorted(security)),
        architecture_changes=tuple(sorted(architecture)), test_or_benchmark_changes=tuple(sorted(tests)),
        hotspot_paths=hotspots,
    )


@dataclass(frozen=True, slots=True)
class ArchitectureGraph:
    nodes: frozenset[str]
    edges: frozenset[tuple[str, str, str]]


@dataclass(frozen=True, slots=True)
class ArchitectureDiff:
    added_nodes: tuple[str, ...]
    removed_nodes: tuple[str, ...]
    added_edges: tuple[tuple[str, str, str], ...]
    removed_edges: tuple[tuple[str, str, str], ...]
    overlap_ratio: float


def architecture_diff(incumbent: ArchitectureGraph, challenger: ArchitectureGraph) -> ArchitectureDiff:
    added_nodes = tuple(sorted(challenger.nodes - incumbent.nodes))
    removed_nodes = tuple(sorted(incumbent.nodes - challenger.nodes))
    added_edges = tuple(sorted(challenger.edges - incumbent.edges))
    removed_edges = tuple(sorted(incumbent.edges - challenger.edges))
    universe = incumbent.nodes | challenger.nodes
    overlap = 1.0 if not universe else len(incumbent.nodes & challenger.nodes) / len(universe)
    return ArchitectureDiff(added_nodes, removed_nodes, added_edges, removed_edges, round(overlap, 6))


@dataclass(frozen=True, slots=True)
class CostSurface:
    paid_services: int = 0
    remote_calls_per_unit: float = 0.0
    accelerator_count: int = 0
    persistent_state_services: int = 0
    build_dependencies: int = 0
    operational_components: int = 0
    manual_steps: int = 0


def hidden_cost_index(value: CostSurface) -> float:
    vals = asdict(value)
    if any(float(v) < 0 for v in vals.values()):
        raise ValueError("HARVEST_COST_SURFACE_NEGATIVE")
    raw = (
        4.0 * value.paid_services
        + 0.7 * value.remote_calls_per_unit
        + 2.0 * value.accelerator_count
        + 2.5 * value.persistent_state_services
        + 0.25 * value.build_dependencies
        + 0.6 * value.operational_components
        + 3.0 * value.manual_steps
    )
    return round(raw, 6)


_PERMISSIVE_HINTS = frozenset({"MIT", "BSD-2-CLAUSE", "BSD-3-CLAUSE", "APACHE-2.0", "ISC", "CC0-1.0"})
_COPYLEFT_HINTS = frozenset({"GPL-2.0", "GPL-2.0-ONLY", "GPL-3.0", "GPL-3.0-ONLY", "AGPL-3.0", "AGPL-3.0-ONLY", "LGPL-2.1", "LGPL-3.0"})


@dataclass(frozen=True, slots=True)
class LicenseAdmissibility:
    classification: str
    code_copy_allowed_by_this_court: bool
    clean_room_allowed: bool
    requires_human_license_review: bool
    reasons: tuple[str, ...]


def classify_license_admissibility(*, license_spdx: str, public_spec_available: bool, proprietary_source: bool) -> LicenseAdmissibility:
    text = license_spdx.strip().upper()
    reasons: list[str] = []
    if proprietary_source:
        return LicenseAdmissibility("PROPRIETARY_HOLD", False, bool(public_spec_available), True, ("PROPRIETARY_SOURCE",))
    if not text or text in {"UNKNOWN", "NON-STANDARD", "PROPRIETARY"}:
        reasons.append("LICENSE_UNKNOWN_OR_NON_STANDARD")
        return LicenseAdmissibility("LICENSE_REVIEW_REQUIRED", False, bool(public_spec_available), True, tuple(reasons))
    if any(h in text for h in _COPYLEFT_HINTS):
        reasons.append("COPYLEFT_DETECTED_REVIEW_SCOPE_AND_OBLIGATIONS")
        return LicenseAdmissibility("COPYLEFT_REVIEW_REQUIRED", False, True, True, tuple(reasons))
    if any(h in text for h in _PERMISSIVE_HINTS):
        reasons.append("KNOWN_PERMISSIVE_IDENTIFIER_DETECTED")
        return LicenseAdmissibility("PUBLIC_SOURCE_CANDIDATE", True, True, False, tuple(reasons))
    return LicenseAdmissibility("LICENSE_REVIEW_REQUIRED", False, bool(public_spec_available), True, ("UNCLASSIFIED_SPDX_EXPRESSION",))


@dataclass(frozen=True, slots=True)
class ClaimObservation:
    claim_id: str
    direction: str
    strength: float
    evidence: SourceEvidence


@dataclass(frozen=True, slots=True)
class TriangulationReceipt:
    claim_id: str
    independent_groups: int
    source_families: int
    support_weight: float
    oppose_weight: float
    confidence: float
    contradictory: bool
    sufficient_for_gene: bool


def triangulate_claim(observations: Sequence[ClaimObservation], *, minimum_groups: int = 2, minimum_families: int = 2) -> TriangulationReceipt:
    if not observations:
        raise ValueError("HARVEST_TRIANGULATION_OBSERVATIONS_REQUIRED")
    claim_ids = {o.claim_id for o in observations}
    if len(claim_ids) != 1:
        raise ValueError("HARVEST_TRIANGULATION_CLAIM_MISMATCH")
    support = oppose = 0.0
    groups: set[str] = set(); families: set[SourceFamily] = set()
    for o in observations:
        o.evidence.validate()
        if not 0 <= o.strength <= 1:
            raise ValueError("HARVEST_TRIANGULATION_STRENGTH_INVALID")
        groups.add(o.evidence.independent_group); families.add(o.evidence.family)
        weighted = o.strength * o.evidence.authority_weight
        if o.direction.upper() in {"SUPPORT", "POSITIVE"}:
            support += weighted
        elif o.direction.upper() in {"OPPOSE", "NEGATIVE"}:
            oppose += weighted
        else:
            raise ValueError("HARVEST_TRIANGULATION_DIRECTION_INVALID")
    total = support + oppose
    confidence = 0.0 if total == 0 else abs(support - oppose) / total
    contradictory = support > 0 and oppose > 0
    sufficient = len(groups) >= minimum_groups and len(families) >= minimum_families and support > oppose and confidence >= 0.20
    return TriangulationReceipt(
        claim_id=next(iter(claim_ids)), independent_groups=len(groups), source_families=len(families),
        support_weight=round(support, 6), oppose_weight=round(oppose, 6), confidence=round(confidence, 6),
        contradictory=contradictory, sufficient_for_gene=sufficient,
    )


@dataclass(frozen=True, slots=True)
class ExperimentLock:
    experiment_id: str
    task_id: str
    dataset_sha256: str
    implementation_sha256: str
    environment_sha256: str
    hardware_class: str
    cache_state: str
    authority_class: str
    cost_context: str
    metrics: tuple[str, ...]
    failure_conditions: tuple[str, ...]
    fingerprint_sha256: str


def preregister_experiment(*, experiment_id: str, task_id: str, dataset_sha256: str, implementation_sha256: str,
                           environment_sha256: str, hardware_class: str, cache_state: str, authority_class: str,
                           cost_context: str, metrics: Iterable[str], failure_conditions: Iterable[str]) -> ExperimentLock:
    digest_fields = (dataset_sha256, implementation_sha256, environment_sha256)
    if any(len(v) != 64 for v in digest_fields):
        raise ValueError("HARVEST_EXPERIMENT_DIGEST_REQUIRED")
    body = {
        "experiment_id": experiment_id.strip(), "task_id": task_id.strip(),
        "dataset_sha256": dataset_sha256, "implementation_sha256": implementation_sha256,
        "environment_sha256": environment_sha256, "hardware_class": hardware_class.strip(),
        "cache_state": cache_state.strip().upper(), "authority_class": authority_class.strip(),
        "cost_context": cost_context.strip(), "metrics": _norm_items(metrics),
        "failure_conditions": _norm_items(failure_conditions),
    }
    if not all((body["experiment_id"], body["task_id"], body["hardware_class"], body["cache_state"], body["metrics"], body["failure_conditions"])):
        raise ValueError("HARVEST_EXPERIMENT_LOCK_FIELDS_REQUIRED")
    return ExperimentLock(**body, fingerprint_sha256=_hash(body))


@dataclass(frozen=True, slots=True)
class BenchmarkContext:
    task_id: str
    dataset_sha256: str
    hardware_class: str
    cache_state: str
    authority_class: str
    cost_context: str
    implementation_lineage: str
    evaluation_version: str


@dataclass(frozen=True, slots=True)
class ContaminationReceipt:
    comparable: bool
    contamination_flags: tuple[str, ...]


def benchmark_contamination_court(incumbent: BenchmarkContext, challenger: BenchmarkContext, *, shared_training_or_fixture: bool = False,
                                  cherry_picked_subset: bool = False) -> ContaminationReceipt:
    flags: list[str] = []
    for attr, flag in (
        ("task_id", "TASK_MISMATCH"), ("dataset_sha256", "DATASET_MISMATCH"),
        ("hardware_class", "HARDWARE_MISMATCH"), ("cache_state", "CACHE_STATE_MISMATCH"),
        ("authority_class", "AUTHORITY_MISMATCH"), ("cost_context", "COST_CONTEXT_MISMATCH"),
        ("evaluation_version", "EVALUATION_VERSION_MISMATCH"),
    ):
        if getattr(incumbent, attr) != getattr(challenger, attr):
            flags.append(flag)
    if incumbent.implementation_lineage == challenger.implementation_lineage:
        flags.append("NON_INDEPENDENT_IMPLEMENTATION_LINEAGE")
    if shared_training_or_fixture:
        flags.append("TRAINING_OR_FIXTURE_LEAKAGE")
    if cherry_picked_subset:
        flags.append("CHERRY_PICKED_SUBSET")
    return ContaminationReceipt(comparable=not flags, contamination_flags=tuple(sorted(flags)))


@dataclass(frozen=True, slots=True)
class BetaBelief:
    alpha: float
    beta: float
    mean: float
    evidence_count: int


def bayesian_capability_belief(*, prior_alpha: float = 1.0, prior_beta: float = 1.0, successes: int = 0, failures: int = 0) -> BetaBelief:
    if prior_alpha <= 0 or prior_beta <= 0 or successes < 0 or failures < 0:
        raise ValueError("HARVEST_BAYES_INPUT_INVALID")
    alpha = prior_alpha + successes; beta = prior_beta + failures
    return BetaBelief(alpha, beta, round(alpha / (alpha + beta), 6), successes + failures)


@dataclass(frozen=True, slots=True)
class SequentialEvidenceDecision:
    belief: BetaBelief
    decision: str


def sequential_evidence_court(*, successes: int, failures: int, accept_mean: float = 0.80, reject_mean: float = 0.35,
                              min_observations: int = 5) -> SequentialEvidenceDecision:
    belief = bayesian_capability_belief(successes=successes, failures=failures)
    if belief.evidence_count < min_observations:
        decision = "CONTINUE"
    elif belief.mean >= accept_mean:
        decision = "CANDIDATE_ACCEPT"
    elif belief.mean <= reject_mean:
        decision = "REJECT"
    else:
        decision = "CONTINUE"
    return SequentialEvidenceDecision(belief, decision)


@dataclass(frozen=True, slots=True)
class CounterfactualResult:
    metric: str
    observed_delta: float
    guardrail_regression: bool
    attributable_candidate: bool


def counterfactual_challenger(*, metric: str, incumbent_values: Sequence[float], challenger_values: Sequence[float],
                             guardrail_regression: bool = False) -> CounterfactualResult:
    if not incumbent_values or len(incumbent_values) != len(challenger_values):
        raise ValueError("HARVEST_COUNTERFACTUAL_MATCHED_VALUES_REQUIRED")
    deltas = [float(c) - float(i) for i, c in zip(incumbent_values, challenger_values)]
    observed = sum(deltas) / len(deltas)
    return CounterfactualResult(metric, round(observed, 6), guardrail_regression, not guardrail_regression and observed != 0)


@dataclass(frozen=True, slots=True)
class CalibrationReceipt:
    brier_score: float
    expected_calibration_error: float
    sufficiently_calibrated: bool


def confidence_calibration_court(probabilities: Sequence[float], outcomes: Sequence[int], *, bins: int = 5,
                                 max_brier: float = 0.20, max_ece: float = 0.15) -> CalibrationReceipt:
    if not probabilities or len(probabilities) != len(outcomes) or bins < 1:
        raise ValueError("HARVEST_CALIBRATION_MATCHED_DATA_REQUIRED")
    if any(not 0 <= float(p) <= 1 for p in probabilities) or any(o not in (0, 1) for o in outcomes):
        raise ValueError("HARVEST_CALIBRATION_VALUE_INVALID")
    n = len(probabilities)
    brier = sum((float(p) - o) ** 2 for p, o in zip(probabilities, outcomes)) / n
    ece = 0.0
    for idx in range(bins):
        lo, hi = idx / bins, (idx + 1) / bins
        members = [(float(p), o) for p, o in zip(probabilities, outcomes) if lo <= float(p) <= hi if idx == bins - 1 or float(p) < hi]
        if not members:
            continue
        conf = sum(p for p, _ in members) / len(members)
        acc = sum(o for _, o in members) / len(members)
        ece += (len(members) / n) * abs(conf - acc)
    return CalibrationReceipt(round(brier, 6), round(ece, 6), brier <= max_brier and ece <= max_ece)


@dataclass(frozen=True, slots=True)
class ChallengerArm:
    arm_id: str
    successes: int
    trials: int
    mean_value: float


def allocate_challenger(arms: Sequence[ChallengerArm], *, total_trials: int) -> str:
    if not arms or total_trials < 0:
        raise ValueError("HARVEST_CHALLENGER_ARMS_REQUIRED")
    for arm in arms:
        if arm.trials < 0 or arm.successes < 0 or arm.successes > arm.trials:
            raise ValueError("HARVEST_CHALLENGER_ARM_INVALID")
    untried = sorted(a.arm_id for a in arms if a.trials == 0)
    if untried:
        return untried[0]
    total = max(total_trials, sum(a.trials for a in arms), 1)
    def ucb(a: ChallengerArm) -> float:
        empirical = a.mean_value
        exploration = math.sqrt(2.0 * math.log(total) / a.trials)
        return empirical + exploration
    return max(arms, key=lambda a: (ucb(a), -a.trials, a.arm_id)).arm_id


@dataclass(frozen=True, slots=True)
class FitnessVector:
    candidate_id: str
    quality: float
    reliability: float
    latency: float
    cost: float
    owner_burden: float
    proof: float


def _dominates(a: FitnessVector, b: FitnessVector) -> bool:
    ge = a.quality >= b.quality and a.reliability >= b.reliability and a.proof >= b.proof
    le = a.latency <= b.latency and a.cost <= b.cost and a.owner_burden <= b.owner_burden
    strict = (
        a.quality > b.quality or a.reliability > b.reliability or a.proof > b.proof or
        a.latency < b.latency or a.cost < b.cost or a.owner_burden < b.owner_burden
    )
    return ge and le and strict


def pareto_frontier(candidates: Sequence[FitnessVector]) -> tuple[str, ...]:
    if not candidates:
        raise ValueError("HARVEST_PARETO_CANDIDATES_REQUIRED")
    ids = [c.candidate_id for c in candidates]
    if len(set(ids)) != len(ids):
        raise ValueError("HARVEST_PARETO_DUPLICATE_CANDIDATE")
    survivors = []
    for cand in candidates:
        if not any(_dominates(other, cand) for other in candidates if other.candidate_id != cand.candidate_id):
            survivors.append(cand.candidate_id)
    return tuple(sorted(survivors))


def dominance_stability(windows: Sequence[tuple[FitnessVector, FitnessVector]], *, required_fraction: float = 0.67) -> float:
    if not windows or not 0 < required_fraction <= 1:
        raise ValueError("HARVEST_DOMINANCE_WINDOWS_REQUIRED")
    wins = sum(1 for challenger, incumbent in windows if _dominates(challenger, incumbent))
    fraction = wins / len(windows)
    return round(fraction, 6)


def distribution_shift(reference: Mapping[str, float], current: Mapping[str, float]) -> float:
    keys = set(reference) | set(current)
    if not keys:
        return 0.0
    if any(v < 0 for v in reference.values()) or any(v < 0 for v in current.values()):
        raise ValueError("HARVEST_DISTRIBUTION_NEGATIVE")
    r_total, c_total = sum(reference.values()), sum(current.values())
    if r_total <= 0 or c_total <= 0:
        raise ValueError("HARVEST_DISTRIBUTION_TOTAL_REQUIRED")
    tv = 0.5 * sum(abs(reference.get(k, 0) / r_total - current.get(k, 0) / c_total) for k in keys)
    return round(_clamp01(tv), 6)


@dataclass(frozen=True, slots=True)
class EvaluationPin:
    dataset_sha256: str
    evaluator_version: str
    rubric_sha256: str
    oracle_sha256: str
    environment_sha256: str
    fingerprint_sha256: str


def pin_evaluation(*, dataset_sha256: str, evaluator_version: str, rubric_sha256: str, oracle_sha256: str,
                   environment_sha256: str) -> EvaluationPin:
    digests = (dataset_sha256, rubric_sha256, oracle_sha256, environment_sha256)
    if any(len(d) != 64 for d in digests) or not evaluator_version.strip():
        raise ValueError("HARVEST_EVALUATION_PIN_FIELDS_REQUIRED")
    body = {
        "dataset_sha256": dataset_sha256, "evaluator_version": evaluator_version.strip(),
        "rubric_sha256": rubric_sha256, "oracle_sha256": oracle_sha256,
        "environment_sha256": environment_sha256,
    }
    return EvaluationPin(**body, fingerprint_sha256=_hash(body))


@dataclass(frozen=True, slots=True)
class ProbeCandidate:
    probe_id: str
    information_gain: float
    mission_value: float
    novelty_probability: float
    cost: float
    latency: float
    risk: float

    def utility(self) -> float:
        if min(self.information_gain, self.mission_value, self.novelty_probability, self.cost, self.latency, self.risk) < 0:
            raise ValueError("HARVEST_PROBE_NEGATIVE_INPUT")
        return (
            self.information_gain * self.mission_value * (0.25 + self.novelty_probability)
            / (1.0 + self.cost + self.latency + self.risk)
        )


def select_probe_batch(probes: Sequence[ProbeCandidate], *, max_cost: float, max_count: int) -> tuple[str, ...]:
    if max_cost < 0 or max_count < 1:
        raise ValueError("HARVEST_PROBE_BUDGET_INVALID")
    ranked = sorted(probes, key=lambda p: (-p.utility(), p.probe_id))
    selected: list[str] = []; spent = 0.0
    for probe in ranked:
        if len(selected) >= max_count:
            break
        if spent + probe.cost > max_cost:
            continue
        selected.append(probe.probe_id); spent += probe.cost
    return tuple(selected)


@dataclass(frozen=True, slots=True)
class ArchaeologyStageReceipt:
    stage: str
    completed: bool
    proof_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HarvestCompletionInput:
    candidate_id: str
    depth: HarvestDepth
    stage_receipts: tuple[ArchaeologyStageReceipt, ...]
    evidence: tuple[SourceEvidence, ...]
    estate_diff_complete: bool
    negative_evidence_searched: bool
    license_admissible_or_clean_room: bool
    benchmark_protocol_pinned: bool
    empirical_advantage_proven: bool = False
    owner_value_proven: bool = False


@dataclass(frozen=True, slots=True)
class HarvestCompletionReceipt:
    candidate_id: str
    state: str
    blockers: tuple[str, ...]
    completed_stage_count: int
    independent_source_groups: int
    source_family_count: int
    receiver_adoption_authorized: bool = False
    provider_effect_authorized: bool = False


def harvest_completion_court(value: HarvestCompletionInput) -> HarvestCompletionReceipt:
    if not value.candidate_id:
        raise ValueError("HARVEST_COMPLETION_CANDIDATE_REQUIRED")
    stage_map = {r.stage: r for r in value.stage_receipts}
    completed = sum(1 for stage in ARCHAEOLOGY_STAGES if stage_map.get(stage) and stage_map[stage].completed and stage_map[stage].proof_refs)
    evidence_groups = {e.independent_group for e in value.evidence if e.validate()}
    families = {e.family for e in value.evidence}
    blockers: list[str] = []
    if value.depth < HarvestDepth.H7_GENE:
        blockers.append("H7_GENE_DEPTH_REQUIRED")
    if completed < 10:
        blockers.append("ARCHAEOLOGY_STAGE_COVERAGE_INSUFFICIENT")
    if len(evidence_groups) < 3:
        blockers.append("THREE_INDEPENDENT_SOURCE_GROUPS_REQUIRED")
    if len(families) < 4:
        blockers.append("FOUR_SOURCE_FAMILIES_REQUIRED")
    if not value.estate_diff_complete:
        blockers.append("ESTATE_DIFF_REQUIRED")
    if not value.negative_evidence_searched:
        blockers.append("NEGATIVE_EVIDENCE_SEARCH_REQUIRED")
    if not value.license_admissible_or_clean_room:
        blockers.append("LICENSE_OR_CLEAN_ROOM_GATE_REQUIRED")
    if not value.benchmark_protocol_pinned:
        blockers.append("PINNED_BENCHMARK_PROTOCOL_REQUIRED")
    if value.depth >= HarvestDepth.H9_EMPIRICAL and not value.empirical_advantage_proven:
        blockers.append("EMPIRICAL_ADVANTAGE_REQUIRED_FOR_H9")
    if value.depth >= HarvestDepth.H10_VALUE and not value.owner_value_proven:
        blockers.append("OWNER_VALUE_REQUIRED_FOR_H10")

    if blockers:
        state = "HARVEST_OPEN"
    elif value.depth == HarvestDepth.H7_GENE:
        state = "GENE_FORMED"
    elif value.depth == HarvestDepth.H8_CANDIDATE:
        state = "CANDIDATE_EXECUTABLE"
    elif value.depth == HarvestDepth.H9_EMPIRICAL:
        state = "EMPIRICAL_ADVANTAGE_PROVEN"
    else:
        state = "VALUE_PROVEN"
    return HarvestCompletionReceipt(
        candidate_id=value.candidate_id,
        state=state,
        blockers=tuple(sorted(blockers)),
        completed_stage_count=completed,
        independent_source_groups=len(evidence_groups),
        source_family_count=len(families),
        receiver_adoption_authorized=False,
        provider_effect_authorized=False,
    )


@dataclass(frozen=True, slots=True)
class OmegaHarvestMaxReceipt:
    schema: str
    base_compiler: str
    base_gene_count: int
    base_deep_control_count: int
    newly_deepened_gene_count: int
    total_deep_control_count: int
    archaeology_stage_count: int
    provider_effect_authorized: bool
    stable_promotion_authorized: bool
    truth_boundary: tuple[str, ...]


def upgrade_receipt() -> OmegaHarvestMaxReceipt:
    # Import lazily so this extension can be inspected independently while still
    # binding its counts to the canonical Wave-2 compiler when executed in repo.
    from benchmarking.cfbe_omega import scientific_capability_compiler_v2 as base

    base_receipt = base.compile_wave2_receipt()
    base_ids = {g.gene_id for g in base.load_wave2_genome()}
    if len(base_ids) != 100 or not DEEPENED_GENE_IDS.issubset(base_ids):
        raise ValueError("HARVEST_MAX_BASE_GENOME_MISMATCH")
    overlap = DEEPENED_GENE_IDS & set(base.DEEP_GENE_IDS)
    if overlap:
        raise ValueError(f"HARVEST_MAX_DEEPENED_GENE_OVERLAP:{sorted(overlap)}")
    total = base_receipt.deep_control_count + len(DEEPENED_GENE_IDS)
    return OmegaHarvestMaxReceipt(
        schema=SCHEMA,
        base_compiler=BASE_COMPILER,
        base_gene_count=base_receipt.gene_count,
        base_deep_control_count=base_receipt.deep_control_count,
        newly_deepened_gene_count=len(DEEPENED_GENE_IDS),
        total_deep_control_count=total,
        archaeology_stage_count=len(ARCHAEOLOGY_STAGES),
        provider_effect_authorized=False,
        stable_promotion_authorized=False,
        truth_boundary=(
            "source/control extension only until hosted CI readback passes",
            "public evidence and source archaeology do not prove provider deployment",
            "license classifier is triage support and not legal advice",
            "H9 requires same-task empirical advantage; H10 requires receiver-local owner value",
            "no benchmark result expands authority, credentials, spend, publication, or external effects",
        ),
    )
