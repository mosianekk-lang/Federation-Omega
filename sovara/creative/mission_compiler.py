from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json

from federation.mission_ir import ContextBudgetIR, MissionIR

from .genome import CreativeMissionGenome, RightsState
from .improvement_catalog import IMPROVEMENT_CATALOG, improvements_for
from .mission_ir_adapter import compile_creative_mission_ir
from .policy import ContentClass, PrivacyClass


_COMPILER_VERSION = "SOVARA-CREATIVE-MISSION-COMPILER-V1"
_PROGRAM_SCHEMA = "SOVARA_CREATIVE_MISSION_PROGRAM_V1"


class AutonomyMode(str, Enum):
    GUIDED = "GUIDED"
    INTERNAL_AUTOPILOT = "INTERNAL_AUTOPILOT"
    GATED_EXTERNAL_AUTOPILOT = "GATED_EXTERNAL_AUTOPILOT"


@dataclass(frozen=True, slots=True)
class CreativeMissionIntent:
    mission_id: str
    objective: str
    content_class: ContentClass
    privacy_class: PrivacyClass
    rights_state: RightsState = RightsState.PENDING
    required_modalities: tuple[str, ...] = field(default_factory=tuple)
    target_channels: tuple[str, ...] = field(default_factory=tuple)
    outcome_contract: str = "Produce one reviewable creative package with proof-bound lineage."
    source_frontier: str = "SOVARA_CREATIVE_CURRENT_SOURCE"
    effect_class: str = "NO_EFFECT"
    autonomy_mode: AutonomyMode = AutonomyMode.INTERNAL_AUTOPILOT
    owner_approval_required: bool = True
    authority_requirements: tuple[str, ...] = field(default_factory=tuple)
    provider_allowlist: tuple[str, ...] = field(default_factory=tuple)
    provider_denylist: tuple[str, ...] = field(default_factory=tuple)
    failure_domain_exclusions: tuple[str, ...] = field(default_factory=tuple)
    proof_requirements: tuple[str, ...] = field(default_factory=tuple)
    value_metrics: tuple[str, ...] = (
        "owner_interventions",
        "owner_minutes",
        "latency_ms",
        "qa_result",
        "accepted_asset_count",
    )
    max_cost_microunits: int | None = None
    latency_target_ms: int | None = None
    context_budget: ContextBudgetIR = field(default_factory=ContextBudgetIR)


@dataclass(frozen=True, slots=True)
class MissionStage:
    stage_id: str
    action: str
    depends_on: tuple[str, ...]
    effect_class: str
    auto_runnable: bool
    authority_required: bool
    proof_requirements: tuple[str, ...]
    repair_strategies: tuple[str, ...]
    learning_hooks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CreativeMissionProgram:
    schema: str
    compiler_version: str
    intent_sha256: str
    genome: CreativeMissionGenome
    mission_ir: MissionIR
    stages: tuple[MissionStage, ...]
    active_improvement_ids: tuple[str, ...]
    evolution_catalog_sha256: str
    authority_ceiling: str
    provider_effect_authorized: bool
    financial_effect_authorized: bool
    publication_authorized: bool
    program_sha256: str

    def stage(self, stage_id: str) -> MissionStage:
        for item in self.stages:
            if item.stage_id == stage_id:
                return item
        raise KeyError(stage_id)


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _intent_record(intent: CreativeMissionIntent) -> dict[str, object]:
    return {
        "mission_id": intent.mission_id.strip(),
        "objective": intent.objective.strip(),
        "content_class": intent.content_class.value,
        "privacy_class": intent.privacy_class.value,
        "rights_state": intent.rights_state.value,
        "required_modalities": sorted({item.strip().lower() for item in intent.required_modalities if item.strip()}),
        "target_channels": sorted({item.strip().lower() for item in intent.target_channels if item.strip()}),
        "outcome_contract": intent.outcome_contract.strip(),
        "source_frontier": intent.source_frontier.strip(),
        "effect_class": intent.effect_class.strip().upper(),
        "autonomy_mode": intent.autonomy_mode.value,
        "owner_approval_required": bool(intent.owner_approval_required),
        "authority_requirements": sorted({item.strip() for item in intent.authority_requirements if item.strip()}),
        "provider_allowlist": sorted({item.strip() for item in intent.provider_allowlist if item.strip()}),
        "provider_denylist": sorted({item.strip() for item in intent.provider_denylist if item.strip()}),
        "failure_domain_exclusions": sorted({item.strip() for item in intent.failure_domain_exclusions if item.strip()}),
        "proof_requirements": sorted({item.strip() for item in intent.proof_requirements if item.strip()}),
        "value_metrics": sorted({item.strip() for item in intent.value_metrics if item.strip()}),
        "max_cost_microunits": intent.max_cost_microunits,
        "latency_target_ms": intent.latency_target_ms,
        "context_budget": asdict(intent.context_budget),
    }


def _stage_record(stage: MissionStage) -> dict[str, object]:
    return {
        "stage_id": stage.stage_id,
        "action": stage.action,
        "depends_on": list(stage.depends_on),
        "effect_class": stage.effect_class,
        "auto_runnable": stage.auto_runnable,
        "authority_required": stage.authority_required,
        "proof_requirements": list(stage.proof_requirements),
        "repair_strategies": list(stage.repair_strategies),
        "learning_hooks": list(stage.learning_hooks),
    }


def _catalog_sha256() -> str:
    return _digest([
        {
            "id": item.improvement_id,
            "category": item.category,
            "title": item.title,
            "frontier_gene": item.frontier_gene,
            "target_module": item.target_module,
            "priority": item.priority,
            "proof_gate": item.proof_gate,
        }
        for item in IMPROVEMENT_CATALOG
    ])


def _validate_stage_dag(stages: tuple[MissionStage, ...]) -> None:
    ids = [item.stage_id for item in stages]
    if len(ids) != len(set(ids)):
        raise ValueError("SOVARA_MISSION_COMPILER_DUPLICATE_STAGE")
    known: set[str] = set()
    for stage in stages:
        if any(dep not in known for dep in stage.depends_on):
            raise ValueError("SOVARA_MISSION_COMPILER_FORWARD_DEPENDENCY")
        if stage.auto_runnable and stage.effect_class not in {"NO_EFFECT", "READ_ONLY"}:
            raise ValueError("SOVARA_MISSION_COMPILER_EFFECTFUL_STAGE_CANNOT_AUTORUN")
        if stage.effect_class not in {"NO_EFFECT", "READ_ONLY", "BOUNDED_EFFECT", "CONSEQUENTIAL_EFFECT"}:
            raise ValueError("SOVARA_MISSION_COMPILER_EFFECT_CLASS_INVALID")
        known.add(stage.stage_id)


class SovaraCreativeMissionCompiler:
    """Compile creative intent into SOVARA-native state plus shared MissionIR.

    SOVARA keeps domain semantics and its own program graph. MissionIR remains the
    federation interoperability contract. This compiler grants no provider, spend,
    publication or consequential-effect authority; effectful stages remain gated.
    """

    def compile(self, intent: CreativeMissionIntent) -> CreativeMissionProgram:
        record = _intent_record(intent)
        if not record["mission_id"] or not record["objective"]:
            raise ValueError("SOVARA_MISSION_COMPILER_INTENT_REQUIRED")
        if not record["outcome_contract"] or not record["source_frontier"]:
            raise ValueError("SOVARA_MISSION_COMPILER_CONTRACT_REQUIRED")

        genome = CreativeMissionGenome.build(
            mission_id=str(record["mission_id"]),
            content_class=intent.content_class,
            objective=str(record["objective"]),
            privacy_class=intent.privacy_class,
            required_modalities=tuple(record["required_modalities"]),
            target_channels=tuple(record["target_channels"]),
            rights_state=intent.rights_state,
            owner_approval_required=intent.owner_approval_required,
        )
        proof_requirements = tuple(record["proof_requirements"]) or (
            "MISSION_PROGRAM_HASH",
            "GRAPH_STATE_HASH",
            "TASTE_STATE_HASH",
            "PRODUCER_PLAN_HASH",
            "QA_RECEIPT",
            "VALUE_RECEIPT",
        )
        mission_ir = compile_creative_mission_ir(
            genome,
            source_frontier=str(record["source_frontier"]),
            outcome_contract=str(record["outcome_contract"]),
            proof_requirements=proof_requirements,
            authority_requirements=tuple(record["authority_requirements"]),
            effect_class=str(record["effect_class"]),
            provider_allowlist=tuple(record["provider_allowlist"]),
            provider_denylist=tuple(record["provider_denylist"]),
            failure_domain_exclusions=tuple(record["failure_domain_exclusions"]),
            value_metrics=tuple(record["value_metrics"]),
            context_budget=intent.context_budget,
            max_cost_microunits=intent.max_cost_microunits,
            latency_target_ms=intent.latency_target_ms,
            rollback_required=True,
        )

        internal_auto = intent.autonomy_mode is not AutonomyMode.GUIDED
        execution_effect = mission_ir.effect_class
        execution_auto = internal_auto and execution_effect in {"NO_EFFECT", "READ_ONLY"}
        stages = (
            MissionStage("00-intent", "NORMALIZE_AND_BIND_OWNER_INTENT", (), "NO_EFFECT", internal_auto, False, ("MISSION_PROGRAM_HASH",), ("RECOMPILE_FROM_INTENT",), ()),
            MissionStage("10-state", "LOAD_AND_VERIFY_CREATIVE_STATE", ("00-intent",), "READ_ONLY", internal_auto, False, ("GRAPH_STATE_HASH", "TASTE_STATE_HASH"), ("RELOAD_DURABLE_STATE", "HOLD_ON_CORRUPTION"), ("STATE_FRESHNESS_OBSERVATION",)),
            MissionStage("20-graph", "COMPILE_OR_REUSE_CREATIVE_GRAPH", ("10-state",), "NO_EFFECT", internal_auto, False, ("GRAPH_STATE_HASH",), ("REBUILD_FROM_LAST_VERIFIED_VERSION",), ("GRAPH_DELTA_LEARNING",)),
            MissionStage("30-producer", "COMPILE_OR_REUSE_PRODUCER_PLAN", ("20-graph",), "NO_EFFECT", internal_auto, False, ("PRODUCER_PLAN_HASH",), ("RESULT_FABRIC_REUSE", "DETERMINISTIC_RECOMPILE"), ("PLAN_REUSE_TELEMETRY",)),
            MissionStage("40-route", "SELECT_MINIMUM_STRONG_PROVIDER_OR_TOOL_ROUTE", ("30-producer",), "NO_EFFECT", internal_auto, False, ("ROUTE_DECISION_RECEIPT",), ("REROUTE", "CIRCUIT_BREAKER"), ("ROUTE_PERFORMANCE_MEMORY",)),
            MissionStage("50-preflight", "VERIFY_POLICY_RIGHTS_PRIVACY_COST_AND_AUTHORITY", ("40-route",), "READ_ONLY", internal_auto, False, ("PREFLIGHT_RECEIPT",), ("REFRESH_PROVIDER_LEASE", "FALLBACK_TO_SAFE_ROUTE"), ("PREFLIGHT_FAILURE_MEMORY",)),
            MissionStage("60-execute", "EXECUTE_SELECTED_CREATIVE_WORK_PACKET", ("50-preflight",), execution_effect, execution_auto, execution_effect not in {"NO_EFFECT", "READ_ONLY"}, ("RUNTIME_RECEIPT", "SEMANTIC_READBACK"), ("BOUNDED_RETRY", "REROUTE", "ROLLBACK"), ("PROVIDER_PERFORMANCE_MEMORY", "FAILURE_WIN_CAPTURE")),
            MissionStage("70-observe", "OBSERVE_OUTPUT_AND_BIND_ASSET_LINEAGE", ("60-execute",), "READ_ONLY", internal_auto, False, ("ASSET_HASH", "PROVENANCE_RECEIPT"), ("READBACK_RECONCILIATION",), ("ASSET_OUTCOME_MEMORY",)),
            MissionStage("80-qa", "EVALUATE_QUALITY_AND_CONSTRAINT_FIT", ("70-observe",), "NO_EFFECT", internal_auto, False, ("QA_RECEIPT",), ("EVALUATOR_OPTIMIZER", "RIPPLE_REGENERATION"), ("QUALITY_LEARNING",)),
            MissionStage("85-learn", "UPDATE_BOUNDED_TASTE_ROUTE_AND_FAILURE_LEARNING", ("80-qa",), "NO_EFFECT", internal_auto, False, ("LEARNING_RECEIPT",), ("REPLAY_PRIOR_VERIFIED_STATE",), ("TASTE_CAPTURE", "ROUTE_LEARNING", "FAILURE_PATTERN_LEARNING")),
            MissionStage("87-repair", "SELF_DIAGNOSE_AND_REPAIR_DETECTED_GAPS", ("85-learn",), "NO_EFFECT", internal_auto, False, ("REPAIR_RECEIPT",), ("FAILURE_WIN_V2", "CFBE_CHALLENGE", "CAPABILITY_FOUNDRY"), ("REPAIR_OUTCOME_LEARNING",)),
            MissionStage("88-value", "MEASURE_OPERATIONAL_USABILITY_AND_COMMERCIAL_VALUE", ("87-repair",), "READ_ONLY", internal_auto, False, ("VALUE_RECEIPT",), ("ROLLBACK_TO_CHAMPION", "CFBE_REINVESTMENT"), ("VALUE_LEARNING",)),
            MissionStage("90-release", "OWNER_OR_EXISTING_AUTHORITY_RELEASE_GATE", ("88-value",), "CONSEQUENTIAL_EFFECT", False, True, ("RELEASE_AUTHORITY_RECEIPT",), ("HOLD_WITHOUT_AUTHORITY",), ()),
        )
        _validate_stage_dag(stages)

        active = tuple(item.improvement_id for item in improvements_for(priorities=("P0",)))
        catalog_sha = _catalog_sha256()
        authority_ceiling = "A1_INTERNAL_AUTOPILOT" if internal_auto else "A0_GUIDED"
        base = {
            "schema": _PROGRAM_SCHEMA,
            "compiler_version": _COMPILER_VERSION,
            "intent_sha256": _digest(record),
            "genome": {
                "mission_id": genome.mission_id,
                "content_class": genome.content_class.value,
                "objective": genome.objective,
                "privacy_class": genome.privacy_class.value,
                "required_modalities": list(genome.required_modalities),
                "target_channels": list(genome.target_channels),
                "rights_state": genome.rights_state.value,
                "owner_approval_required": genome.owner_approval_required,
            },
            "mission_ir": mission_ir.canonical_mapping(),
            "stages": [_stage_record(item) for item in stages],
            "active_improvement_ids": list(active),
            "evolution_catalog_sha256": catalog_sha,
            "authority_ceiling": authority_ceiling,
            "provider_effect_authorized": False,
            "financial_effect_authorized": False,
            "publication_authorized": False,
        }
        return CreativeMissionProgram(
            schema=_PROGRAM_SCHEMA,
            compiler_version=_COMPILER_VERSION,
            intent_sha256=base["intent_sha256"],
            genome=genome,
            mission_ir=mission_ir,
            stages=stages,
            active_improvement_ids=active,
            evolution_catalog_sha256=catalog_sha,
            authority_ceiling=authority_ceiling,
            provider_effect_authorized=False,
            financial_effect_authorized=False,
            publication_authorized=False,
            program_sha256=_digest(base),
        )


def compile_creative_mission(intent: CreativeMissionIntent) -> CreativeMissionProgram:
    return SovaraCreativeMissionCompiler().compile(intent)
