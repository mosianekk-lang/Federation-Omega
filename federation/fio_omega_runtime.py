"""FIO-Ω / SIR-Ω v1.4 — provider-neutral sovereign intelligence + creative runtime.

This module is deliberately a composition substrate, not a new authority plane.
It binds to external Human Mission Contract and MissionIR fingerprints, treats
providers as replaceable processors, delegates effects to existing Federation
execution authorities, and preserves SOVARA creative-state identity across
cross-medium Golden Creative Paths.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def digest(value: Any) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


def _digest_ok(value: str) -> bool:
    return value.startswith("sha256:") and len(value) == 71


class Risk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Medium(str, Enum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    VECTOR = "VECTOR"
    LAYOUT = "LAYOUT"
    UI = "UI"
    WEB = "WEB"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    MOTION = "MOTION"
    THREE_D = "3D"
    GAME = "GAME"
    DOCUMENT = "DOCUMENT"
    PRESENTATION = "PRESENTATION"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class MissionBinding:
    mission_id: str
    owner: str
    hmc_fingerprint: str
    mission_ir_digest: str
    objective_digest: str

    def validate(self) -> None:
        if not self.mission_id.strip() or not self.owner.strip():
            raise ValueError("MISSION_BINDING_IDENTITY_REQUIRED")
        for value in (self.hmc_fingerprint, self.mission_ir_digest, self.objective_digest):
            if not _digest_ok(value):
                raise ValueError("MISSION_BINDING_DIGEST_INVALID")

    @property
    def binding_digest(self) -> str:
        self.validate()
        return digest(asdict(self))


@dataclass(frozen=True, slots=True)
class ProcessorManifest:
    processor_id: str
    provider: str
    model: str
    snapshot: str
    capabilities: tuple[str, ...]
    local_or_sovereign: bool = False
    supports_async_tools: bool = False
    supports_tool_search: bool = False
    supports_searchable_context: bool = False
    supports_sandbox: bool = False

    def validate(self) -> None:
        if not all((self.processor_id.strip(), self.provider.strip(), self.model.strip(), self.snapshot.strip())):
            raise ValueError("PROCESSOR_MANIFEST_IDENTITY_REQUIRED")
        if not self.capabilities:
            raise ValueError("PROCESSOR_CAPABILITIES_REQUIRED")


@dataclass(frozen=True, slots=True)
class ProcessorAttestation:
    processor_id: str
    provider_live: bool
    semantic_readback_ready: bool
    authorized: bool
    healthy: bool
    quality: float
    latency_ms: float | None = None
    cost_microunits: int | None = None
    proof_refs: tuple[str, ...] = ()
    observed_at: str = ""

    def validate(self) -> None:
        if not self.processor_id.strip():
            raise ValueError("PROCESSOR_ATTESTATION_ID_REQUIRED")
        if not 0 <= float(self.quality) <= 1:
            raise ValueError("PROCESSOR_ATTESTATION_QUALITY_INVALID")
        if self.provider_live and not self.proof_refs:
            raise ValueError("PROCESSOR_ATTESTATION_PROOF_REQUIRED")


@dataclass(frozen=True, slots=True)
class IntelligenceTask:
    task_id: str
    mission_id: str
    objective: str
    required_capabilities: tuple[str, ...]
    risk: Risk = Risk.MEDIUM
    minimum_quality: float = 0.0
    provider_diversity_floor: int = 1
    sensitive: bool = False
    external_effect: bool = False

    def validate(self) -> None:
        if not all((self.task_id.strip(), self.mission_id.strip(), self.objective.strip())):
            raise ValueError("INTELLIGENCE_TASK_IDENTITY_REQUIRED")
        if not self.required_capabilities:
            raise ValueError("INTELLIGENCE_TASK_CAPABILITY_REQUIRED")
        if not 0 <= float(self.minimum_quality) <= 1:
            raise ValueError("INTELLIGENCE_TASK_QUALITY_INVALID")
        if self.provider_diversity_floor < 1:
            raise ValueError("INTELLIGENCE_TASK_DIVERSITY_INVALID")


@dataclass(frozen=True, slots=True)
class ProcessorCandidate:
    processor_id: str
    provider: str
    score: float
    local_or_sovereign: bool
    proof_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RoutePlan:
    state: str
    candidates: tuple[ProcessorCandidate, ...]
    selected_processor_id: str = ""
    selected_provider: str = ""
    reasons: tuple[str, ...] = ()
    requires_external_executor: bool = False


class ProcessorPortfolio:
    """Proof-weighted capability census. It never grants provider authority."""

    def __init__(self, manifests: Sequence[ProcessorManifest]):
        for item in manifests:
            item.validate()
        if len({item.processor_id for item in manifests}) != len(manifests):
            raise ValueError("DUPLICATE_PROCESSOR_ID")
        self.manifests = {item.processor_id: item for item in manifests}

    def route(self, task: IntelligenceTask, attestations: Sequence[ProcessorAttestation]) -> RoutePlan:
        task.validate()
        if task.external_effect:
            return RoutePlan("DELEGATE_TO_SOVARA_MODISA_FDOF", (), reasons=("FIO_CANNOT_EXECUTE_EXTERNAL_EFFECTS",), requires_external_executor=True)
        health = {item.processor_id: item for item in attestations}
        candidates: list[ProcessorCandidate] = []
        for manifest in self.manifests.values():
            if not set(task.required_capabilities).issubset(set(manifest.capabilities)):
                continue
            status = health.get(manifest.processor_id)
            if status is None:
                continue
            status.validate()
            if not (status.provider_live and status.semantic_readback_ready and status.authorized and status.healthy):
                continue
            if status.quality < task.minimum_quality:
                continue
            if task.sensitive and not manifest.local_or_sovereign:
                continue
            latency = status.latency_ms or 0
            cost = status.cost_microunits or 0
            score = 100 * status.quality - min(20.0, latency / 1000.0) - min(20.0, cost / 1_000_000.0)
            if manifest.local_or_sovereign and task.sensitive:
                score += 20
            candidates.append(ProcessorCandidate(manifest.processor_id, manifest.provider, round(score, 6), manifest.local_or_sovereign, tuple(status.proof_refs)))
        candidates.sort(key=lambda item: (item.score, item.processor_id), reverse=True)
        if not candidates:
            return RoutePlan("PROCESSOR_GATED", (), reasons=("NO_CURRENT_PROVEN_PROCESSOR",))
        providers = {item.provider for item in candidates}
        if len(providers) < task.provider_diversity_floor:
            return RoutePlan("PROCESSOR_GATED", tuple(candidates), reasons=("PROVIDER_DIVERSITY_FLOOR_UNMET",))
        return RoutePlan("INTELLIGENCE_ROUTE_CANDIDATE", tuple(candidates), candidates[0].processor_id, candidates[0].provider, ("PROOF_WEIGHTED_PROCESSOR_PORTFOLIO",))


@dataclass(frozen=True, slots=True)
class CapabilityGene:
    gene_id: str
    mechanism: str
    source_refs: tuple[str, ...]
    clean_room: bool
    receiver: str
    tests_required: tuple[str, ...]
    benchmark_required: bool = True
    authority_expansion: bool = False

    def validate(self) -> None:
        if not all((self.gene_id.strip(), self.mechanism.strip(), self.receiver.strip())):
            raise ValueError("CAPABILITY_GENE_IDENTITY_REQUIRED")
        if not self.source_refs or not self.clean_room:
            raise ValueError("CAPABILITY_GENE_CLEAN_ROOM_PROOF_REQUIRED")
        if self.authority_expansion:
            raise ValueError("CAPABILITY_GENE_AUTHORITY_EXPANSION_PROHIBITED")


@dataclass(frozen=True, slots=True)
class CreativeStateRef:
    mission_id: str
    graph_id: str
    graph_version: str
    version_tree_ref: str
    taste_fingerprint: str
    rights_state: str
    privacy_class: str
    reference_hashes: tuple[str, ...] = ()

    def validate(self) -> None:
        if not all((self.mission_id.strip(), self.graph_id.strip(), self.graph_version.strip(), self.version_tree_ref.strip(), self.rights_state.strip(), self.privacy_class.strip())):
            raise ValueError("CREATIVE_STATE_IDENTITY_REQUIRED")
        if not _digest_ok(self.taste_fingerprint):
            raise ValueError("CREATIVE_TASTE_FINGERPRINT_INVALID")
        if any(not _digest_ok(item) for item in self.reference_hashes):
            raise ValueError("CREATIVE_REFERENCE_HASH_INVALID")

    @property
    def state_digest(self) -> str:
        self.validate()
        return digest(asdict(self))


@dataclass(frozen=True, slots=True)
class FreedomEnvelope:
    envelope_id: str
    mission_id: str
    mediums: tuple[Medium, ...]
    novelty_target: float = 0.8
    reference_fidelity_target: float = 0.8
    identity_consistency_target: float = 0.8
    editability_target: float = 0.8
    provider_diversity_floor: int = 1
    sensitive: bool = False
    materialization_budget: int = 24

    def validate(self) -> None:
        if not self.envelope_id.strip() or not self.mission_id.strip() or not self.mediums:
            raise ValueError("FREEDOM_ENVELOPE_IDENTITY_REQUIRED")
        for value in (self.novelty_target, self.reference_fidelity_target, self.identity_consistency_target, self.editability_target):
            if not 0 <= float(value) <= 1:
                raise ValueError("FREEDOM_ENVELOPE_TARGET_INVALID")
        if self.provider_diversity_floor < 1 or self.materialization_budget < 1:
            raise ValueError("FREEDOM_ENVELOPE_BUDGET_INVALID")

    @property
    def envelope_digest(self) -> str:
        self.validate()
        return digest({**asdict(self), "mediums": [item.value for item in self.mediums]})


@dataclass(frozen=True, slots=True)
class DesignIR:
    design_id: str
    mission_id: str
    creative_state_digest: str
    freedom_envelope_digest: str
    medium: Medium
    objective: str
    graph_node_refs: tuple[str, ...]
    style_controls: Mapping[str, Any] = field(default_factory=dict)
    identity_controls: Mapping[str, Any] = field(default_factory=dict)
    content: Mapping[str, Any] = field(default_factory=dict)
    output_spec: Mapping[str, Any] = field(default_factory=dict)
    required_capabilities: tuple[str, ...] = ()

    def validate(self) -> None:
        if not all((self.design_id.strip(), self.mission_id.strip(), self.objective.strip())):
            raise ValueError("DESIGN_IR_IDENTITY_REQUIRED")
        if not _digest_ok(self.creative_state_digest) or not _digest_ok(self.freedom_envelope_digest):
            raise ValueError("DESIGN_IR_DIGEST_INVALID")
        if not self.graph_node_refs:
            raise ValueError("DESIGN_IR_GRAPH_NODE_REQUIRED")

    @property
    def design_digest(self) -> str:
        self.validate()
        return digest({**asdict(self), "medium": self.medium.value})


@dataclass(frozen=True, slots=True)
class BranchAddress:
    path: tuple[str, ...]
    branch_id: str


class CreativeUniverse:
    """Lazy logical namespace. Branching is not tied to render quotas or provider context."""

    def __init__(self, root: DesignIR):
        root.validate()
        self.root = root

    def branch(self, *labels: str) -> BranchAddress:
        if not labels or any(not str(label).strip() for label in labels):
            raise ValueError("CREATIVE_BRANCH_LABEL_REQUIRED")
        path = tuple(str(label).strip() for label in labels)
        return BranchAddress(path, "branch_" + digest({"root": self.root.design_digest, "path": path})[7:31])

    def child(self, parent: BranchAddress, label: str) -> BranchAddress:
        return self.branch(*(parent.path + (label,)))


_DEFAULT_CAPS: dict[Medium, tuple[str, ...]] = {
    Medium.IMAGE: ("CREATIVE_GENERATE", "REFERENCE_CONTROL"),
    Medium.THREE_D: ("THREE_D_GENERATE",),
    Medium.VIDEO: ("VIDEO_GENERATE", "TIMELINE"),
    Medium.UI: ("UI_LAYOUT", "TEXT_LAYOUT"),
    Medium.WEB: ("WEB_BUILD", "UI_LAYOUT"),
    Medium.PRESENTATION: ("PRESENTATION_BUILD", "TEXT_LAYOUT"),
    Medium.DOCUMENT: ("DOCUMENT_BUILD", "TEXT_LAYOUT"),
    Medium.AUDIO: ("AUDIO_GENERATE",),
    Medium.MOTION: ("MOTION_GENERATE", "TIMELINE"),
    Medium.TEXT: ("TEXT_GENERATE",),
    Medium.VECTOR: ("VECTOR_GENERATE",),
    Medium.LAYOUT: ("LAYOUT", "TEXT_LAYOUT"),
    Medium.GAME: ("GAME_BUILD",),
    Medium.OTHER: ("CREATIVE_GENERATE",),
}


@dataclass(frozen=True, slots=True)
class StageSpec:
    stage_id: str
    medium: Medium
    objective: str
    depends_on: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    mandatory: bool = True
    materialization_weight: float = 1.0

    def validate(self) -> None:
        if not self.stage_id.strip() or not self.objective.strip():
            raise ValueError("GOLDEN_STAGE_IDENTITY_REQUIRED")
        if self.materialization_weight <= 0:
            raise ValueError("GOLDEN_STAGE_WEIGHT_INVALID")

    @property
    def capabilities(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.required_capabilities or _DEFAULT_CAPS[self.medium])))


@dataclass(frozen=True, slots=True)
class StageDesign:
    stage: StageSpec
    design: DesignIR
    parent_design_digest: str


@dataclass(frozen=True, slots=True)
class GoldenCreativePath:
    path_id: str
    mission_id: str
    state_digest: str
    envelope_digest: str
    graph_version: str
    taste_fingerprint: str
    root_design_digest: str
    stages: tuple[StageSpec, ...]
    references: tuple[str, ...]
    invariants: tuple[str, ...] = ("IDENTITY", "STYLE", "REFERENCE", "TASTE", "NARRATIVE")

    def validate(self) -> None:
        if not all((self.path_id.strip(), self.mission_id.strip(), self.graph_version.strip())):
            raise ValueError("GOLDEN_PATH_IDENTITY_REQUIRED")
        for item in (self.state_digest, self.envelope_digest, self.taste_fingerprint, self.root_design_digest):
            if not _digest_ok(item):
                raise ValueError("GOLDEN_PATH_DIGEST_INVALID")
        ids = [stage.stage_id for stage in self.stages]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("GOLDEN_PATH_STAGE_ID_INVALID")
        prior: set[str] = set()
        for stage in self.stages:
            stage.validate()
            if any(dep not in prior for dep in stage.depends_on):
                raise ValueError("GOLDEN_PATH_DEPENDENCY_NOT_PRIOR")
            prior.add(stage.stage_id)

    @property
    def path_digest(self) -> str:
        self.validate()
        return digest({**asdict(self), "stages": [{**asdict(stage), "medium": stage.medium.value} for stage in self.stages]})


class GoldenPathCompiler:
    """Cross-medium compiler. It preserves the same SOVARA state above every provider."""

    def compile(self, state: CreativeStateRef, envelope: FreedomEnvelope, root: DesignIR, *, path_id: str, stages: Sequence[StageSpec]) -> tuple[GoldenCreativePath, tuple[StageDesign, ...]]:
        state.validate(); envelope.validate(); root.validate()
        if state.mission_id != envelope.mission_id or root.mission_id != state.mission_id:
            raise ValueError("GOLDEN_PATH_MISSION_MISMATCH")
        if root.creative_state_digest != state.state_digest or root.freedom_envelope_digest != envelope.envelope_digest:
            raise ValueError("GOLDEN_PATH_ROOT_BINDING_DRIFT")
        if any(stage.medium not in envelope.mediums for stage in stages):
            raise ValueError("GOLDEN_PATH_STAGE_MEDIUM_OUTSIDE_ENVELOPE")
        path = GoldenCreativePath(path_id, state.mission_id, state.state_digest, envelope.envelope_digest, state.graph_version, state.taste_fingerprint, root.design_digest, tuple(stages), tuple(state.reference_hashes))
        path.validate()
        designs: list[StageDesign] = []
        parent = root
        for stage in path.stages:
            design = DesignIR(
                design_id=f"{path.path_id}:{stage.stage_id}", mission_id=state.mission_id,
                creative_state_digest=state.state_digest, freedom_envelope_digest=envelope.envelope_digest,
                medium=stage.medium, objective=stage.objective, graph_node_refs=parent.graph_node_refs,
                style_controls={**dict(parent.style_controls), "golden_path_id": path.path_id, "invariants": list(path.invariants)},
                identity_controls={**dict(parent.identity_controls), "taste_fingerprint": state.taste_fingerprint, "root_design_digest": root.design_digest},
                content={**dict(parent.content), "source_medium": parent.medium.value, "target_medium": stage.medium.value, "parent_design_digest": parent.design_digest},
                output_spec=dict(parent.output_spec), required_capabilities=stage.capabilities,
            )
            designs.append(StageDesign(stage, design, parent.design_digest))
            parent = design
        return path, tuple(designs)


@dataclass(frozen=True, slots=True)
class MaterializationPlan:
    total_variants: int
    stage_variants: tuple[tuple[str, int], ...]
    logical_branch_space_bounded: bool = False


class MaterializationBudget:
    def allocate(self, path: GoldenCreativePath, max_variants: int) -> MaterializationPlan:
        path.validate()
        mandatory = [stage for stage in path.stages if stage.mandatory]
        if max_variants < len(mandatory):
            raise ValueError("MATERIALIZATION_BUDGET_BELOW_MANDATORY_FLOOR")
        allocation = {stage.stage_id: 1 if stage.mandatory else 0 for stage in path.stages}
        remaining = max_variants - sum(allocation.values())
        order = sorted(path.stages, key=lambda stage: (-stage.materialization_weight, stage.stage_id))
        while remaining:
            for stage in order:
                if not remaining:
                    break
                allocation[stage.stage_id] += 1
                remaining -= 1
        return MaterializationPlan(sum(allocation.values()), tuple((stage.stage_id, allocation[stage.stage_id]) for stage in path.stages), False)


@dataclass(frozen=True, slots=True)
class ContinuityObservation:
    stage_id: str
    design_digest: str
    state_digest: str
    envelope_digest: str
    graph_version: str
    taste_fingerprint: str
    references: tuple[str, ...]
    identity_consistency: float
    style_alignment: float
    reference_fidelity: float
    narrative_continuity: float
    proof_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CourtDecision:
    state: str
    stage_id: str
    promotable: bool
    reasons: tuple[str, ...]


class ContinuityCourt:
    def evaluate(self, path: GoldenCreativePath, stage_design: StageDesign, obs: ContinuityObservation, envelope: FreedomEnvelope) -> CourtDecision:
        path.validate(); stage_design.design.validate(); envelope.validate()
        reasons: list[str] = []
        if obs.stage_id != stage_design.stage.stage_id: reasons.append("STAGE_ID_MISMATCH")
        if obs.design_digest != stage_design.design.design_digest: reasons.append("DESIGN_DIGEST_DRIFT")
        if obs.state_digest != path.state_digest: reasons.append("CREATIVE_STATE_DRIFT")
        if obs.envelope_digest != path.envelope_digest: reasons.append("FREEDOM_ENVELOPE_DRIFT")
        if obs.graph_version != path.graph_version: reasons.append("GRAPH_VERSION_DRIFT")
        if obs.taste_fingerprint != path.taste_fingerprint: reasons.append("TASTE_DRIFT")
        if tuple(obs.references) != tuple(path.references): reasons.append("REFERENCE_SET_DRIFT")
        if not obs.proof_refs: reasons.append("CONTINUITY_PROOF_REQUIRED")
        if obs.identity_consistency < envelope.identity_consistency_target: reasons.append("IDENTITY_BELOW_TARGET")
        if obs.reference_fidelity < envelope.reference_fidelity_target: reasons.append("REFERENCE_FIDELITY_BELOW_TARGET")
        if obs.style_alignment < 0.75: reasons.append("STYLE_ALIGNMENT_BELOW_FLOOR")
        if obs.narrative_continuity < 0.75: reasons.append("NARRATIVE_CONTINUITY_BELOW_FLOOR")
        return CourtDecision("CROSS_MEDIUM_CONTINUITY_PASS" if not reasons else "CROSS_MEDIUM_CONTINUITY_HOLD", obs.stage_id, not reasons, tuple(reasons or ("CREATIVE_STATE_PRESERVED",)))


@dataclass(frozen=True, slots=True)
class CreativeOutput:
    stage_id: str
    provider: str
    artifact_digest: str
    reference_fidelity: float
    composition_quality: float
    identity_consistency: float
    editability: float
    novelty: float
    style_alignment: float
    proof_refs: tuple[str, ...]
    judge_provider: str = ""
    judge_proof_refs: tuple[str, ...] = ()


class CreativeQualityCourt:
    def evaluate(self, output: CreativeOutput, envelope: FreedomEnvelope, *, high_consequence: bool = True) -> CourtDecision:
        envelope.validate(); reasons: list[str] = []
        if not _digest_ok(output.artifact_digest): reasons.append("ARTIFACT_DIGEST_INVALID")
        if not output.proof_refs: reasons.append("OUTPUT_PROOF_REQUIRED")
        if output.reference_fidelity < envelope.reference_fidelity_target: reasons.append("REFERENCE_FIDELITY_BELOW_TARGET")
        if output.identity_consistency < envelope.identity_consistency_target: reasons.append("IDENTITY_BELOW_TARGET")
        if output.editability < envelope.editability_target: reasons.append("EDITABILITY_BELOW_TARGET")
        if output.novelty < envelope.novelty_target: reasons.append("NOVELTY_BELOW_TARGET")
        if output.style_alignment < 0.75: reasons.append("STYLE_ALIGNMENT_BELOW_FLOOR")
        if high_consequence and (not output.judge_provider or not output.judge_proof_refs): reasons.append("INDEPENDENT_JUDGE_REQUIRED")
        if high_consequence and output.judge_provider == output.provider: reasons.append("SELF_JUDGING_PROVIDER_NOT_SUFFICIENT")
        return CourtDecision("CREATIVE_OUTPUT_ACCEPTABLE" if not reasons else "CREATIVE_OUTPUT_HOLD", output.stage_id, not reasons, tuple(reasons or ("QUALITY_TARGETS_MET",)))


@dataclass(frozen=True, slots=True)
class StageRecovery:
    state: str
    stage_id: str
    next_processor_id: str = ""
    preserve_design_ir: bool = True
    preserve_graph_version: bool = True
    preserve_taste: bool = True
    preserve_references: bool = True
    reasons: tuple[str, ...] = ()


class StageFailover:
    def recover(self, stage_id: str, route: RoutePlan, *, failed_processor_id: str) -> StageRecovery:
        if route.state != "INTELLIGENCE_ROUTE_CANDIDATE":
            return StageRecovery("STAGE_ROUTE_REDISCOVERY_REQUIRED", stage_id, reasons=("NO_READY_ROUTE",))
        backups = [item for item in route.candidates if item.processor_id != failed_processor_id]
        if not backups:
            return StageRecovery("STAGE_ROUTE_REDISCOVERY_REQUIRED", stage_id, reasons=("PORTFOLIO_EXHAUSTED",))
        return StageRecovery("STAGE_FAILOVER_READY", stage_id, backups[0].processor_id, True, True, True, True, ("FAILED_PROVIDER_DID_NOT_INVALIDATE_CREATIVE_STATE",))


@dataclass(frozen=True, slots=True)
class CompletionDecision:
    state: str
    complete: bool
    missing_stages: tuple[str, ...]
    held_stages: tuple[str, ...]
    reasons: tuple[str, ...]


class GoldenPathCompletionCourt:
    def evaluate(self, path: GoldenCreativePath, quality: Mapping[str, CourtDecision], continuity: Mapping[str, CourtDecision]) -> CompletionDecision:
        path.validate(); missing: list[str] = []; held: list[str] = []
        for stage in path.stages:
            if not stage.mandatory: continue
            q = quality.get(stage.stage_id); c = continuity.get(stage.stage_id)
            if q is None or c is None: missing.append(stage.stage_id); continue
            if not q.promotable or not c.promotable: held.append(stage.stage_id)
        complete = not missing and not held
        reasons = ("ALL_MANDATORY_CROSS_MEDIUM_STAGES_VERIFIED",) if complete else tuple(filter(None, ("MANDATORY_STAGE_PROOF_MISSING" if missing else "", "MANDATORY_STAGE_QUALITY_OR_CONTINUITY_HELD" if held else "")))
        return CompletionDecision("GOLDEN_PATH_VERIFIED_COMPLETE" if complete else "GOLDEN_PATH_INCOMPLETE", complete, tuple(sorted(missing)), tuple(sorted(held)), reasons)


@dataclass(frozen=True, slots=True)
class FederationPorts:
    human_first: Any = None
    forest_first: Any = None
    air: Any = None
    provider_mesh: Any = None
    execution: Any = None
    proof: Any = None
    completion: Any = None
    durable_memory: Any = None
    sovara_creative: Any = None


class SovereignIntelligenceRuntime:
    """Composition kernel. Missing authority ports fail closed rather than self-promote."""

    def __init__(self, binding: MissionBinding, portfolio: ProcessorPortfolio, ports: FederationPorts = FederationPorts()):
        binding.validate(); self.binding = binding; self.portfolio = portfolio; self.ports = ports

    def assert_binding(self, hmc_fingerprint: str, mission_ir_digest: str) -> None:
        if hmc_fingerprint != self.binding.hmc_fingerprint: raise ValueError("HMC_FINGERPRINT_DRIFT")
        if mission_ir_digest != self.binding.mission_ir_digest: raise ValueError("MISSION_IR_DIGEST_DRIFT")

    def route(self, task: IntelligenceTask, attestations: Sequence[ProcessorAttestation]) -> RoutePlan:
        if task.mission_id != self.binding.mission_id: raise ValueError("TASK_MISSION_MISMATCH")
        return self.portfolio.route(task, attestations)

    def before_final(self, mission_state: Mapping[str, Any], candidate_response: str = "") -> Mapping[str, Any]:
        if self.ports.completion is None:
            return {"state": "COMPLETION_PORT_REQUIRED", "allow_final": False, "continue_work": True, "reasons": ("CHATGOV_OR_EQUIVALENT_REQUIRED",)}
        return self.ports.completion.before_final(self.binding.mission_id, dict(mission_state), candidate_response)


__all__ = [
    "Risk", "Medium", "MissionBinding", "ProcessorManifest", "ProcessorAttestation", "IntelligenceTask",
    "ProcessorCandidate", "RoutePlan", "ProcessorPortfolio", "CapabilityGene", "CreativeStateRef", "FreedomEnvelope",
    "DesignIR", "CreativeUniverse", "BranchAddress", "StageSpec", "StageDesign", "GoldenCreativePath", "GoldenPathCompiler",
    "MaterializationPlan", "MaterializationBudget", "ContinuityObservation", "CourtDecision", "ContinuityCourt", "CreativeOutput",
    "CreativeQualityCourt", "StageRecovery", "StageFailover", "CompletionDecision", "GoldenPathCompletionCourt",
    "FederationPorts", "SovereignIntelligenceRuntime", "digest",
]
