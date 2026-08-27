from __future__ import annotations

from datetime import datetime, timezone

from .adaptive_cycle import AdaptiveCycleEngine, AdaptiveCycleRequest
from .cost_governor import PreRevenueCostGovernor
from .event_bus import EventBus
from .evolution import (
    EntropyController,
    HumanAttentionGovernor,
    LearningEvent,
    LearningLedger,
    MarginalInformationGainGate,
    PolicyEvolution,
)
from .failure_win_v2 import FailureToOperationalWinKernelV2
from .forest_omega import ForestFirstOmega
from .graphs import MissionGraph, ProofGraph, StateFabric
from .horizon import HorizonOmega
from .intelligence_router import AdaptiveIntelligenceRouter, IntelligenceRouteDecision
from .models import FederationEvent, Maturity, RiskClass
from .resource_market import ResourceMarket
from .science_and_routes import FederationDigitalTwin, FormationEngine, OmegaScientia


BOUNDARY_CLASSES = {
    "UNSUPPORTED",
    "UNAVAILABLE",
    "AUTH_FAILURE",
    "MISSING_CONNECTOR",
    "MISSING_API",
    "MISSING_PERMISSION",
    "SCHEMA_FAILURE",
    "TIMEOUT",
    "CONTEXT_LIMIT",
    "PROVIDER_MISMATCH",
    "SEMANTIC_FAILURE",
    "CAPABILITY_LOST",
}

FAILURE_WIN_EVENT_TYPES = (
    "FAILURE",
    "TIMEOUT",
    "REGRESSION",
    "CLAIM_FRUIT_CONTRADICTION",
    "PROVIDER_ERROR",
    "SLO_BREACH",
    "CANARY_FAILURE",
    "PRECURSOR_RISK",
)


class AdaptiveScheduler:
    def choose_mode(self, risk_class: RiskClass, *, uncertainty: float = 0.0, irreversibility: float = 0.0) -> str:
        if risk_class == RiskClass.CRITICAL or irreversibility >= 0.8:
            return "CRITICAL"
        if risk_class == RiskClass.HIGH or uncertainty >= 0.6:
            return "DEEP"
        if risk_class == RiskClass.MODERATE:
            return "STANDARD"
        return "RAPID"


class SemanticReadbackFirewall:
    def evaluate(self, *, transport_ok: bool, semantic_match: bool) -> str:
        if not transport_ok:
            return "TRANSPORT_FAILURE"
        if not semantic_match:
            return "SEMANTIC_FAILURE"
        return "SUCCESS"


class BoundaryBuildEngine:
    def classify(self, failure_type: str) -> str:
        if failure_type in BOUNDARY_CLASSES:
            return "UNRESOLVED_ENGINEERING_BUILD"
        return "NORMAL_FAILURE"


class JarvisAssuranceMesh:
    def audit_transition(self, *, intended_execution: bool, provider_dependent: bool, readback_present: bool, state_changed: bool) -> dict[str, object]:
        defects: list[str] = []
        if provider_dependent and intended_execution and not readback_present:
            defects.append("PROVIDER_READBACK_MISSING")
        if intended_execution and readback_present and not state_changed:
            defects.append("NO_STATE_DELTA_AFTER_EXECUTION")
        return {"defects": defects, "hold": bool(defects)}


class AOHarmonicV3:
    VERSION = "3.3.0"
    AUTHORITY_CEILING = "A1_INTERNAL"
    EXTERNAL_EFFECT_DEFAULT = False

    def __init__(self) -> None:
        self.events = EventBus()
        self.state = StateFabric()
        self.missions = MissionGraph()
        self.proof = ProofGraph()
        self.resources = ResourceMarket()
        self.scheduler = AdaptiveScheduler()
        self.formation = FormationEngine()
        self.scientia = OmegaScientia()
        self.digital_twin = FederationDigitalTwin()
        self.horizon = HorizonOmega()
        self.cost = PreRevenueCostGovernor()
        self.intelligence = AdaptiveIntelligenceRouter(cost_governor=self.cost)
        self.forest = ForestFirstOmega(
            horizon=self.horizon,
            scientia=self.scientia,
            formation=self.formation,
            digital_twin=self.digital_twin,
        )
        self.failure_win = FailureToOperationalWinKernelV2(
            horizon=self.horizon,
            formation=self.formation,
        )
        self.policy = PolicyEvolution()
        self.attention = HumanAttentionGovernor()
        self.mig = MarginalInformationGainGate()
        self.entropy = EntropyController()
        self.learning = LearningLedger(max_records=64)
        self.adaptive_cycle = AdaptiveCycleEngine()
        self.jarvis = JarvisAssuranceMesh()
        self.boundary_build = BoundaryBuildEngine()
        self.semantic_firewall = SemanticReadbackFirewall()
        self._bind_events()

    def _bind_events(self) -> None:
        self.events.subscribe("TOOL_FAILURE", self._tool_failure)
        self.events.subscribe("OWNER_CORRECTION", self._owner_correction)
        self.events.subscribe("CAPABILITY_DISCOVERED", self._capability_discovered)
        self.events.subscribe("NEW_EVIDENCE", self._new_evidence)
        for event_type in FAILURE_WIN_EVENT_TYPES:
            self.events.subscribe(event_type, self._failure_win_event)

    def prepare_openai_responses_request(
        self,
        decision: IntelligenceRouteDecision,
        input_data: object,
        *,
        previous_response_id: str | None = None,
    ) -> dict[str, object]:
        """Prepare a provider-safe request body without invoking OpenAI."""
        return self.intelligence.to_openai_responses_payload(
            decision,
            input_data,
            previous_response_id=previous_response_id,
        )

    def run_adaptive_cycle(self, request: AdaptiveCycleRequest) -> dict[str, object]:
        """Run one measured improvement cycle and retain only bounded deltas."""
        result = self.adaptive_cycle.run(request)
        learning_record = self.record_terminal_learning(
            cycle_id=request.cycle_id,
            objective=request.objective,
            terminal_state=result.outcome.value,
            actual_result=result.claim_state,
            proof_refs=request.proof_refs,
            proposed_patch=result.next_action,
            fitness_score=result.candidate_score,
        )
        payload = result.to_dict()
        payload["learning_record"] = learning_record
        payload["learning_snapshot"] = self.learning.snapshot()
        payload["adaptive_memory_snapshot"] = self.adaptive_cycle.memory.snapshot()
        return payload

    def _tool_failure(self, event: FederationEvent) -> dict[str, object]:
        failure_type = str(event.payload.get("failure_type", "UNKNOWN"))
        return {
            "classification": self.boundary_build.classify(failure_type),
            "formation": "ROUTE_SEARCH_REQUIRED",
            "forest_first_omega": "AUTO_REROUTE_REMODEL_THEN_BUILD",
            "adaptive_intelligence_router": "REASSESS_AFTER_FAILURE_BEFORE_UNCHANGED_RETRY",
            "adaptive_2x_cycle": "RESTRUCTURE_COMPACT_REBUILD_AND_REMEASURE",
            "failure_to_operational_win_v2": self.failure_win.observe_federation_event(event),
            "cost_governor": "CHEAPEST_EQUIVALENT_ROUTE_BEFORE_PAID_ESCALATION",
            "owner_surface": "OBJECTIVE_LEVEL_ONLY",
            "unchanged_retry": "PROHIBITED_AFTER_REPEAT_FINGERPRINT",
        }

    def _failure_win_event(self, event: FederationEvent) -> dict[str, object]:
        return {
            "failure_to_operational_win_v2": self.failure_win.observe_federation_event(event),
            "authority_ceiling": self.AUTHORITY_CEILING,
            "external_effect_default": self.EXTERNAL_EFFECT_DEFAULT,
        }

    def _owner_correction(self, event: FederationEvent) -> dict[str, object]:
        return {
            "failure_genome": "CREATE_OR_UPDATE",
            "scientific_review": "REQUIRED",
            "forest_first_omega": "REMODEL_AND_CREATE_LEARNING_CANDIDATE",
            "adaptive_intelligence_router": "REASSESS_AND_RAISE_TIER_IF_CORRECTION_REVEALS_MATERIAL_UNCERTAINTY",
            "adaptive_2x_cycle": "SET_CORRECTED_STATE_AS_NEW_BASELINE_AND_REBUILD",
            "failure_to_operational_win_v2": self.failure_win.observe_federation_event(event),
            "policy_candidate": "ELIGIBLE",
            "event_id": event.event_id,
        }

    @staticmethod
    def _capability_discovered(event: FederationEvent) -> dict[str, object]:
        return {
            "resource_market": "REFRESH",
            "open_builds": "RECHECK",
            "forest_first_omega": "RECOMPUTE_PATHS_AND_HORIZON",
            "failure_to_operational_win_v2": "RECHECK_OPEN_GENOMES_AND_PREWARM_ELIGIBLE_ROUTES",
            "adaptive_intelligence_router": "RECHECK_PROVIDER_MODEL_AND_REASONING_BINDINGS",
            "adaptive_2x_cycle": "GENERATE_NEW_CANDIDATE_AND_COMPARE_AGAINST_CURRENT_BASELINE",
            "cost_governor": "RECHECK_CHEAPER_INCLUDED_OR_SCALE_TO_ZERO_ROUTE",
            "shortest_safe_canary": "REQUIRED_BEFORE_PROMOTION",
            "event_id": event.event_id,
        }

    @staticmethod
    def _new_evidence(event: FederationEvent) -> dict[str, object]:
        return {
            "evidenceops": "INGEST",
            "truthgrid": "REVALIDATE",
            "proof_graph": "PROPAGATE",
            "mission_graph": "RECOMPUTE",
            "forest_first_omega": "REMODEL_ROOTS_FOREST_HORIZON_AND_PATHS",
            "failure_to_operational_win_v2": "RECOMPUTE_CAUSAL_AND_PROOF_GRAPH",
            "adaptive_intelligence_router": "REASSESS_IF_EVIDENCE_CHANGES_UNCERTAINTY_CONTRADICTIONS_OR_CONSEQUENCE",
            "adaptive_2x_cycle": "DELTA_ONLY_CONTEXT_REFRESH_AND_CANDIDATE_REMEASUREMENT",
            "event_id": event.event_id,
        }

    def record_terminal_learning(
        self,
        *,
        cycle_id: str,
        objective: str,
        terminal_state: str,
        actual_result: str,
        proof_refs: tuple[str, ...] = (),
        proposed_patch: str | None = None,
        fitness_score: float = 0.0,
    ) -> dict[str, object]:
        return self.learning.append(LearningEvent(
            cycle_id=cycle_id,
            objective=objective,
            terminal_state=terminal_state,
            actual_result=actual_result,
            proof_refs=proof_refs,
            proposed_patch=proposed_patch,
            fitness_score=fitness_score,
        ))

    def restore_acceptance_test(self) -> dict[str, object]:
        required = {
            "CHATGOV_AUTHORITY_ROOT",
            "JARVIS_ASSURANCE_MESH",
            "FOREST_FIRST_OMEGA",
            "FOREST_FIRST_JUSTICE_GATE",
            "FOREST_FIRST_ANTICIPATORY_ENGINE",
            "FOREST_FIRST_CREATOR_MODE",
            "HORIZON_OMEGA",
            "ADAPTIVE_INTELLIGENCE_ROUTER",
            "ADAPTIVE_2X_CYCLE_ENGINE",
            "FAILURE_TO_OPERATIONAL_WIN_V2",
            "DYNAMIC_RECEIVER_ATTESTATION",
            "FAILURE_GENOME_AND_PREEMPTION",
            "BOUNDED_CONTEXT_COMPACTION",
            "BOUNDED_DELTA_MEMORY",
            "PRE_REVENUE_COST_GOVERNOR",
            "OMEGA_SCIENTIA",
            "LEX_DOMAIN_AUTHORITY",
            "TRUTHGRID_EVIDENCEOPS",
            "BUBBLES_EXECUTION",
            "EVENT_NERVOUS_SYSTEM",
            "MISSION_GRAPH",
            "STATE_FABRIC",
            "PROOF_GRAPH",
            "RESOURCE_MARKET",
            "ADAPTIVE_SCHEDULER",
            "FORMATION_ENGINE",
            "ALPHA_OMEGA_COMPILER_CONTRACT",
            "DIGITAL_TWIN",
            "POLICY_EVOLUTION",
            "LEARNING_HASH_CHAIN",
            "ENTROPY_CONTROL",
            "SEMANTIC_READBACK_FIREWALL",
        }
        return {
            "required": sorted(required),
            "status": Maturity.SOURCE_IMPLEMENTED.value,
            "runtime_verified": False,
            "authority_ceiling": self.AUTHORITY_CEILING,
            "external_effect_default": self.EXTERNAL_EFFECT_DEFAULT,
            "cost_posture": "PRE_REVENUE_ZERO_BASE",
            "intelligence_routing": "ADAPTIVE-INTELLIGENCE-ROUTER-V1",
            "improvement_target": "MULTI_DIMENSIONAL_PARETO_OR_MISSION_VALUE_GAIN_WITH_PROTECTED_FLOORS",
            "failure_win_kernel": self.failure_win.KERNEL_ID,
            "failure_win_version": self.failure_win.VERSION,
            "working_memory": "BOUNDED_DEDUPLICATED_DELTA_CAPSULES_WITH_HASH_CHECKPOINTS",
            "cognitive_cycle": "DETECT->PRESERVE->CLASSIFY->RECALL->MODEL_CAUSES->FALSIFY->SEARCH_CAPABILITIES->SIMULATE->RANK_ROUTES->AUTHORIZE->EXECUTE->READBACK->REGRESSION->SOAK->VALUE->LEARN->DIFFUSE->PREVENT",
        }


def bootstrap() -> dict[str, object]:
    runtime = AOHarmonicV3()
    return {
        "runtime": "AO-HARMONIC-GENOME",
        "version": runtime.VERSION,
        "architecture": "FEDERATION_COGNITIVE_OPERATING_FABRIC",
        "strategic_perception": "FOREST-FIRST-OMEGA",
        "foresight": "HORIZON-OMEGA",
        "intelligence_routing": "ADAPTIVE-INTELLIGENCE-ROUTER-V1",
        "adaptive_improvement": "ADAPTIVE-2X-CYCLE-ENGINE-V1",
        "failure_to_operational_win": "FAILURE-TO-OPERATIONAL-WIN-V2",
        "prevention_path": "PREDICT->PREWARM->AVOID_FAILURE",
        "context_management": "BOUNDED-CONTEXT-COMPACTION-V1",
        "cost_governance": "PRE_REVENUE_ZERO_BASE",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "acceptance": runtime.restore_acceptance_test(),
        "truth_boundary": {
            "source_implemented": True,
            "deterministic_tests_observed": False,
            "provider_deployed": False,
            "operationally_verified": False,
            "provider_billing_caps_configured": False,
            "model_or_reasoning_selection_executed": False,
            "measured_2x_operational_gain_verified": False,
            "failure_win_behavior_proven_across_receivers": False,
            "durable_external_context_archive_bound": False,
        },
    }
