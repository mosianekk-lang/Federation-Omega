from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Iterable, Mapping, Sequence


AUTHORITY_CEILING = "A1_INTERNAL"

_AUTHORITY_LEVEL = {
    "A0": 0,
    "A0_READ": 0,
    "A1_INTERNAL": 1,
}


class EvolutionStage(IntEnum):
    OBJECTIVE_COMPILER = 1
    CAPABILITY_DIGITAL_TWIN = 2
    CAPABILITY_DEPENDENCY_GRAPH = 3
    AUTONOMOUS_ROUTE_SYNTHESIZER = 4
    ROUTE_PORTFOLIO_OPTIMIZER = 5
    SEMANTIC_FAILURE_CLASSIFIER = 6
    SELF_HEALING_ROUTE_ENGINE = 7
    SUCCESS_ROUTE_MEMORY = 8
    FAILURE_FINGERPRINT_MEMORY = 9
    PREDICTIVE_CAPABILITY_PRELOADING = 10
    TERMINAL_STATE_FIREWALL = 11
    NEGATIVE_PROOF_ENGINE = 12
    COUNTERFACTUAL_ENGINE = 13
    MISSION_CONTINUATION_KERNEL = 14
    EXECUTABLE_WORK_ZERO_ENGINE = 15
    CROSS_CHAT_RUNTIME_ATTESTATION = 16
    AUTONOMOUS_REGRESSION_LAB = 17
    EVOLUTION_GOVERNOR = 18
    CAPABILITY_FORMATION_ENGINE = 19
    AUTONOMOUS_MATURITY_DOMINANCE_CONTROLLER = 20


ALL_STAGES = tuple(EvolutionStage)


class StrategyMode(str, Enum):
    INHERIT_CORE = "INHERIT_CORE"
    SPECIALIZED = "SPECIALIZED"
    STRICTER_SPECIALIZED = "STRICTER_SPECIALIZED"


class AutomationClass(str, Enum):
    A0_READ = "A0_READ"
    A1_INTERNAL = "A1_INTERNAL"
    APPROVAL_GATED = "APPROVAL_GATED"
    PROVIDER_PROOF_GATED = "PROVIDER_PROOF_GATED"


class EvolutionMaturity(str, Enum):
    DESIGNED = "DESIGNED"
    FOUNDATION_ACTIVE = "FOUNDATION_ACTIVE"
    DETERMINISTIC_TESTED = "DETERMINISTIC_TESTED"
    SHADOW_VALIDATED = "SHADOW_VALIDATED"
    ADVERSARIALLY_VALIDATED = "ADVERSARIALLY_VALIDATED"
    CANARY_VALIDATED = "CANARY_VALIDATED"
    LIMITED_WORKFLOW_VERIFIED = "LIMITED_WORKFLOW_VERIFIED"
    CROSS_DOMAIN_VERIFIED = "CROSS_DOMAIN_VERIFIED"
    OPERATIONAL_VERIFIED = "OPERATIONAL_VERIFIED"
    ADAPTIVE_DOMINANCE_CANDIDATE = "ADAPTIVE_DOMINANCE_CANDIDATE"


@dataclass(frozen=True)
class StageSpec:
    stage: EvolutionStage
    purpose: str
    automation_class: AutomationClass = AutomationClass.A1_INTERNAL
    hard_requirements: tuple[str, ...] = ()


STAGE_SPECS: Mapping[EvolutionStage, StageSpec] = {
    EvolutionStage.OBJECTIVE_COMPILER: StageSpec(
        EvolutionStage.OBJECTIVE_COMPILER,
        "Compile the exact user/mission outcome independently of implementation route.",
        hard_requirements=("objective_contract", "completion_test", "scope_boundary"),
    ),
    EvolutionStage.CAPABILITY_DIGITAL_TWIN: StageSpec(
        EvolutionStage.CAPABILITY_DIGITAL_TWIN,
        "Maintain time- and scope-bound capability truth rather than binary can/cannot state.",
        hard_requirements=("freshness", "authority", "semantic_state", "readback_state"),
    ),
    EvolutionStage.CAPABILITY_DEPENDENCY_GRAPH: StageSpec(
        EvolutionStage.CAPABILITY_DEPENDENCY_GRAPH,
        "Map dependencies so one broken edge does not freeze unrelated lanes.",
        hard_requirements=("dependency_graph", "failure_isolation"),
    ),
    EvolutionStage.AUTONOMOUS_ROUTE_SYNTHESIZER: StageSpec(
        EvolutionStage.AUTONOMOUS_ROUTE_SYNTHESIZER,
        "Generate materially distinct objective-preserving routes before declaring limitation.",
        hard_requirements=("alternate_routes", "scope_preservation"),
    ),
    EvolutionStage.ROUTE_PORTFOLIO_OPTIMIZER: StageSpec(
        EvolutionStage.ROUTE_PORTFOLIO_OPTIMIZER,
        "Rank candidate routes by success probability, proof, authority, reversibility, cost and burden.",
        hard_requirements=("route_scores", "selection_reason"),
    ),
    EvolutionStage.SEMANTIC_FAILURE_CLASSIFIER: StageSpec(
        EvolutionStage.SEMANTIC_FAILURE_CLASSIFIER,
        "Classify failures precisely instead of collapsing errors into unavailable.",
        hard_requirements=("typed_failure", "failure_evidence"),
    ),
    EvolutionStage.SELF_HEALING_ROUTE_ENGINE: StageSpec(
        EvolutionStage.SELF_HEALING_ROUTE_ENGINE,
        "Convert typed failure into bounded repair, reroute or circuit break while preserving evidence.",
        hard_requirements=("repair_policy", "rollback", "unaffected_lane_continuity"),
    ),
    EvolutionStage.SUCCESS_ROUTE_MEMORY: StageSpec(
        EvolutionStage.SUCCESS_ROUTE_MEMORY,
        "Persist successful routes as reusable operational recipes.",
        hard_requirements=("route_receipt", "prerequisites", "freshness_rule"),
    ),
    EvolutionStage.FAILURE_FINGERPRINT_MEMORY: StageSpec(
        EvolutionStage.FAILURE_FINGERPRINT_MEMORY,
        "Preserve failure fingerprints and bind them to proven repairs.",
        hard_requirements=("failure_fingerprint", "repair_link"),
    ),
    EvolutionStage.PREDICTIVE_CAPABILITY_PRELOADING: StageSpec(
        EvolutionStage.PREDICTIVE_CAPABILITY_PRELOADING,
        "Predict likely capability needs and resolve them before execution stalls.",
        hard_requirements=("predicted_roles", "preflight_result"),
    ),
    EvolutionStage.TERMINAL_STATE_FIREWALL: StageSpec(
        EvolutionStage.TERMINAL_STATE_FIREWALL,
        "Protect CAN/CANNOT/DONE/LIVE/DEPLOYED/COMPLETE and equivalent terminal language.",
        hard_requirements=("terminal_claim_gate", "proof_threshold"),
    ),
    EvolutionStage.NEGATIVE_PROOF_ENGINE: StageSpec(
        EvolutionStage.NEGATIVE_PROOF_ENGINE,
        "Require bounded search/route exhaustion before non-existence or incapability claims.",
        hard_requirements=("negative_scope", "exhaustion_receipt"),
    ),
    EvolutionStage.COUNTERFACTUAL_ENGINE: StageSpec(
        EvolutionStage.COUNTERFACTUAL_ENGINE,
        "Identify the minimum changed condition that would make a blocked objective executable.",
        hard_requirements=("counterfactual_dependency", "next_route"),
    ),
    EvolutionStage.MISSION_CONTINUATION_KERNEL: StageSpec(
        EvolutionStage.MISSION_CONTINUATION_KERNEL,
        "Separate answer completion from mission completion and continue safe executable work.",
        hard_requirements=("parent_mission_lock", "continuation_state"),
    ),
    EvolutionStage.EXECUTABLE_WORK_ZERO_ENGINE: StageSpec(
        EvolutionStage.EXECUTABLE_WORK_ZERO_ENGINE,
        "Require zero executable internal dependencies before mission completion.",
        hard_requirements=("internal_work_count", "external_dependency_separation"),
    ),
    EvolutionStage.CROSS_CHAT_RUNTIME_ATTESTATION: StageSpec(
        EvolutionStage.CROSS_CHAT_RUNTIME_ATTESTATION,
        "Prove which canonical controls and current mission state were actually loaded on activation.",
        hard_requirements=("startup_receipt", "restore_receipt"),
    ),
    EvolutionStage.AUTONOMOUS_REGRESSION_LAB: StageSpec(
        EvolutionStage.AUTONOMOUS_REGRESSION_LAB,
        "Generate adversarial regressions from every material failure and prevent recurrence.",
        hard_requirements=("regression_case", "regression_pass"),
    ),
    EvolutionStage.EVOLUTION_GOVERNOR: StageSpec(
        EvolutionStage.EVOLUTION_GOVERNOR,
        "Promote only measured improvements that beat the incumbent without fatal regression.",
        hard_requirements=("baseline", "candidate_metrics", "promotion_decision"),
    ),
    EvolutionStage.CAPABILITY_FORMATION_ENGINE: StageSpec(
        EvolutionStage.CAPABILITY_FORMATION_ENGINE,
        "Create missing internal capabilities through governed design, build, test and proof paths.",
        hard_requirements=("capability_gap", "build_identity", "qualification_plan"),
    ),
    EvolutionStage.AUTONOMOUS_MATURITY_DOMINANCE_CONTROLLER: StageSpec(
        EvolutionStage.AUTONOMOUS_MATURITY_DOMINANCE_CONTROLLER,
        "Continuously select weaknesses, generate improvements, qualify them and preserve rollback.",
        automation_class=AutomationClass.PROVIDER_PROOF_GATED,
        hard_requirements=("all_prior_stages", "cross_domain_proof", "operational_readback", "rollback"),
    ),
}


@dataclass(frozen=True)
class SystemEvolutionProfile:
    system_id: str
    canonical_name: str
    family: str
    optimization_objective: str
    strategy_mode: StrategyMode
    specialized_algorithms: tuple[str, ...]
    vetoes: tuple[str, ...]
    mandatory_stages: tuple[EvolutionStage, ...] = ALL_STAGES
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect_default: bool = False

    def validate(self) -> "SystemEvolutionProfile":
        if not self.system_id.strip() or not self.canonical_name.strip():
            raise ValueError("system_id and canonical_name are required")
        if tuple(self.mandatory_stages) != ALL_STAGES:
            raise ValueError("compatible systems may specialize but may not weaken or skip the 20-stage spine")
        authority_level = _AUTHORITY_LEVEL.get(self.authority_ceiling)
        federation_max = _AUTHORITY_LEVEL[AUTHORITY_CEILING]
        if authority_level is None or authority_level > federation_max:
            raise ValueError("unsupported authority ceiling")
        if self.external_effect_default:
            raise ValueError("Federation evolution defaults to no external effect")
        if self.strategy_mode != StrategyMode.INHERIT_CORE and not self.specialized_algorithms:
            raise ValueError("specialized strategies must declare stronger domain-specific algorithms")
        return self


@dataclass(frozen=True)
class StageEvidence:
    stage: EvolutionStage
    passed: bool
    proof_ref: str = ""
    score: float = 0.0
    regression_passed: bool = False
    rollback_available: bool = False
    provider_readback: bool = False
    external_effect: bool = False

    def validate(self) -> "StageEvidence":
        if not 0.0 <= float(self.score) <= 1.0:
            raise ValueError("score must be in [0,1]")
        if self.external_effect:
            raise ValueError("A1 internal evolution evidence may not create external effects")
        if self.passed and not self.proof_ref.strip():
            raise ValueError("passed stages require proof_ref")
        if self.stage >= EvolutionStage.AUTONOMOUS_REGRESSION_LAB and self.passed and not self.regression_passed:
            raise ValueError("stages 17-20 require regression proof")
        if self.stage >= EvolutionStage.CAPABILITY_FORMATION_ENGINE and self.passed and not self.rollback_available:
            raise ValueError("stages 19-20 require rollback availability")
        return self


@dataclass(frozen=True)
class SystemEvolutionState:
    system_id: str
    evidence: tuple[StageEvidence, ...] = ()
    critical_failures: tuple[str, ...] = ()
    open_external_dependencies: tuple[str, ...] = ()

    def evidence_map(self) -> Mapping[EvolutionStage, StageEvidence]:
        result: dict[EvolutionStage, StageEvidence] = {}
        for item in self.evidence:
            item.validate()
            if item.stage in result:
                raise ValueError(f"duplicate stage evidence: {item.stage.name}")
            result[item.stage] = item
        return result


@dataclass(frozen=True)
class EvolutionDecision:
    system_id: str
    maturity: EvolutionMaturity
    completed_stages: tuple[EvolutionStage, ...]
    next_stage: EvolutionStage | None
    automatic_next_actions: tuple[str, ...]
    critical_failures: tuple[str, ...]
    open_external_dependencies: tuple[str, ...]
    dominance_candidate: bool
    reason_codes: tuple[str, ...]


_MATURITY_BY_STAGE = (
    (20, EvolutionMaturity.ADAPTIVE_DOMINANCE_CANDIDATE),
    (19, EvolutionMaturity.OPERATIONAL_VERIFIED),
    (18, EvolutionMaturity.CROSS_DOMAIN_VERIFIED),
    (16, EvolutionMaturity.LIMITED_WORKFLOW_VERIFIED),
    (15, EvolutionMaturity.CANARY_VALIDATED),
    (14, EvolutionMaturity.ADVERSARIALLY_VALIDATED),
    (12, EvolutionMaturity.SHADOW_VALIDATED),
    (8, EvolutionMaturity.DETERMINISTIC_TESTED),
    (1, EvolutionMaturity.FOUNDATION_ACTIVE),
    (0, EvolutionMaturity.DESIGNED),
)


class FederationEvolutionOrchestrator:
    """Fail-closed common maturity spine with stronger per-system specialisation.

    This is an A1 internal decision/orchestration layer. It does not schedule itself,
    mutate providers, or grant authority. Provider/external execution remains separately
    proof- and approval-gated.
    """

    def __init__(self, profiles: Mapping[str, SystemEvolutionProfile] | None = None) -> None:
        source = dict(profiles or SYSTEM_PROFILES)
        self._profiles = {key: value.validate() for key, value in source.items()}

    def profile(self, system_id: str) -> SystemEvolutionProfile:
        try:
            return self._profiles[system_id]
        except KeyError as exc:
            raise KeyError(f"unregistered Federation evolution system: {system_id}") from exc

    def evaluate(self, state: SystemEvolutionState) -> EvolutionDecision:
        profile = self.profile(state.system_id)
        evidence = state.evidence_map()
        completed: list[EvolutionStage] = []
        reasons: list[str] = []

        # Sequential maturity prevents stage-20 theatre built over missing foundations.
        for stage in profile.mandatory_stages:
            item = evidence.get(stage)
            if item is None or not item.passed:
                break
            completed.append(stage)

        next_stage = None if len(completed) == len(ALL_STAGES) else ALL_STAGES[len(completed)]
        maturity = self._maturity(len(completed))

        if state.critical_failures:
            reasons.append("CRITICAL_FAILURE_PRESENT")
        if next_stage is not None:
            reasons.append(f"NEXT_STAGE:{next_stage.name}")
        if profile.strategy_mode != StrategyMode.INHERIT_CORE:
            reasons.append(f"SPECIALIZED_PATH:{profile.strategy_mode.value}")

        dominance_candidate = self._dominance_candidate(profile, state, evidence, completed)
        if not dominance_candidate and len(completed) == len(ALL_STAGES):
            reasons.append("ALL_STAGES_PRESENT_BUT_DOMINANCE_PROOF_INSUFFICIENT")

        actions = self._automatic_next_actions(profile, next_stage, state)
        return EvolutionDecision(
            system_id=state.system_id,
            maturity=maturity,
            completed_stages=tuple(completed),
            next_stage=next_stage,
            automatic_next_actions=actions,
            critical_failures=tuple(state.critical_failures),
            open_external_dependencies=tuple(state.open_external_dependencies),
            dominance_candidate=dominance_candidate,
            reason_codes=tuple(reasons),
        )

    @staticmethod
    def _maturity(completed_count: int) -> EvolutionMaturity:
        for threshold, maturity in _MATURITY_BY_STAGE:
            if completed_count >= threshold:
                return maturity
        return EvolutionMaturity.DESIGNED

    @staticmethod
    def _dominance_candidate(
        profile: SystemEvolutionProfile,
        state: SystemEvolutionState,
        evidence: Mapping[EvolutionStage, StageEvidence],
        completed: Sequence[EvolutionStage],
    ) -> bool:
        if len(completed) != len(ALL_STAGES) or state.critical_failures:
            return False
        final = evidence[EvolutionStage.AUTONOMOUS_MATURITY_DOMINANCE_CONTROLLER]
        if not (final.provider_readback and final.regression_passed and final.rollback_available and final.score >= 0.90):
            return False
        # Specialised systems must prove their stronger path rather than inherit the label by name.
        return profile.strategy_mode == StrategyMode.INHERIT_CORE or bool(profile.specialized_algorithms)

    @staticmethod
    def _automatic_next_actions(
        profile: SystemEvolutionProfile,
        next_stage: EvolutionStage | None,
        state: SystemEvolutionState,
    ) -> tuple[str, ...]:
        actions: list[str] = []
        if next_stage is not None:
            spec = STAGE_SPECS[next_stage]
            actions.append(f"EXECUTE_STAGE:{next_stage.value:02d}:{next_stage.name}")
            actions.append("REQUIRE:" + ",".join(spec.hard_requirements))
            if profile.specialized_algorithms:
                actions.append("APPLY_SPECIALIZED:" + ",".join(profile.specialized_algorithms))
        for failure in state.critical_failures:
            actions.append(f"REPAIR_CRITICAL:{failure}")
        for dependency in state.open_external_dependencies:
            actions.append(f"DISPOSITION_EXTERNAL:{dependency}")
        if next_stage is None and not state.critical_failures:
            actions.append("RUN_CONTINUOUS_REGRESSION_AND_FRESHNESS_REVALIDATION")
        return tuple(actions)

    def federation_rollup(self, states: Iterable[SystemEvolutionState]) -> Mapping[str, object]:
        decisions = [self.evaluate(state) for state in states]
        return {
            "systems": len(decisions),
            "dominance_candidates": tuple(sorted(d.system_id for d in decisions if d.dominance_candidate)),
            "next_actions": {
                d.system_id: d.automatic_next_actions for d in decisions if d.automatic_next_actions
            },
            "maturity": {d.system_id: d.maturity.value for d in decisions},
            "authority_ceiling": AUTHORITY_CEILING,
            "external_effect": False,
        }


def _profile(
    system_id: str,
    name: str,
    family: str,
    objective: str,
    algorithms: Sequence[str],
    vetoes: Sequence[str],
    mode: StrategyMode = StrategyMode.SPECIALIZED,
    authority_ceiling: str = AUTHORITY_CEILING,
) -> SystemEvolutionProfile:
    return SystemEvolutionProfile(
        system_id=system_id,
        canonical_name=name,
        family=family,
        optimization_objective=objective,
        strategy_mode=mode,
        specialized_algorithms=tuple(algorithms),
        vetoes=tuple(vetoes),
        authority_ceiling=authority_ceiling,
    ).validate()


SYSTEM_PROFILES: Mapping[str, SystemEvolutionProfile] = {
    "EVIDENCEOPS": _profile(
        "EVIDENCEOPS", "EvidenceOps", "GOVERNANCE_OS",
        "Maximize proof-bound mission completion with zero uncontrolled authority expansion.",
        ("MISSION_GRAPH", "PROOF_ENVELOPE", "EXECUTABLE_WORK_ZERO", "EVOLUTION_GOVERNOR"),
        ("FALSE_COMPLETION", "UNPROVEN_AUTHORITY", "CASE_WALL_CONTAMINATION"),
        StrategyMode.STRICTER_SPECIALIZED,
    ),
    "OMEGA_MAX": _profile(
        "OMEGA_MAX", "Omega-Max", "INTELLIGENCE_RUNTIME",
        "Maximize reasoning quality, specialist routing and bounded execution reliability.",
        ("SPECIALIST_ROUTER", "CRITIC_REFLEXION", "MINIMUM_SUFFICIENT_CAPABILITY", "REASONING_REGRESSION"),
        ("ROLE_INFLATION", "UNVERIFIED_TOOL_USE", "REASONING_DRIFT"),
    ),
    "FEDERATION_OMEGA": _profile(
        "FEDERATION_OMEGA", "Federation Omega", "ENGINEERING_ESTATE",
        "Maximize reproducible, reversible and admitted engineering change.",
        ("STALE_BASE_ANCESTRY", "AIRLOCK", "LEAK_GUARD", "ROLLBACK_FIRST_DEPLOYMENT"),
        ("DIRECT_MAIN_MUTATION", "AIRLOCK_BYPASS", "UNREADBACK_DEPLOYMENT"),
        StrategyMode.STRICTER_SPECIALIZED,
    ),
    "ARCHITRON": _profile(
        "ARCHITRON", "ARCHITRON", "EXECUTION_WORKER",
        "Maximize recoverable execution while isolating failed lanes and preserving checkpoints.",
        ("CIRCUIT_BREAKER", "CHECKPOINT_RESUME", "SEMANTIC_RESPONSE_CONTRACT", "UNTOUCHED_LANE_CONTINUITY"),
        ("REPEAT_BROKEN_ROUTE", "GENERIC_HEALTH_AS_ACTION_PROOF", "STATE_CORRUPTION"),
    ),
    "SUPERIOR_LOGIC": _profile(
        "SUPERIOR_LOGIC", "Superior Logic", "QUALITY_REASONING",
        "Maximize enforced reasoning quality rather than doctrine volume.",
        ("NO_LIMIT_BEFORE_SWEEP", "DEFICIENCY_TO_RESOLUTION", "RECURRENCE_ESCALATION", "RULE_RUNTIME_BINDING"),
        ("CRITIQUE_ONLY_WHEN_EXECUTABLE", "PROSE_ONLY_REPAIR", "UNBOUNDED_CANNOT"),
    ),
    "VERITAS": _profile(
        "VERITAS", "Veritas-Ω", "TRUTH_ASSURANCE",
        "Minimize unresolved contradictions and unsupported factual certainty.",
        ("CONTRADICTION_CLUSTERING", "SOURCE_SUPREMACY", "ADVERSE_EVIDENCE_SEARCH", "FALSIFICATION"),
        ("INFERENCE_AS_FACT", "NEGATIVE_SEARCH_OVERCLAIM", "CONTRADICTION_SUPPRESSION"),
        authority_ceiling="A0",
    ),
    "EVI": _profile(
        "EVI", "EVI Force Multiplier", "PARALLEL_AMPLIFICATION",
        "Maximize safe parallel throughput without cross-lane contamination or duplicated work.",
        ("LANE_ISOLATION", "COLLISION_KEYS", "PARALLEL_PROOF_MERGE", "OWNER_BURDEN_MINIMIZER"),
        ("DUPLICATE_EXECUTION", "CROSS_LANE_STATE_WRITE", "UNBOUNDED_PARALLELISM"),
    ),
    "SECURE_CAPABILITY_BOX": _profile(
        "SECURE_CAPABILITY_BOX", "Secure Capability Box", "SECURITY_CAPABILITY",
        "Maximize usable capability under least privilege, freshness and exact-scope authority.",
        ("LEASED_AUTHORITY", "TTL_CAPABILITY_STATE", "IDENTITY_TARGET_SCOPE_ACTION", "SECRET_NON_DISCLOSURE"),
        ("AUTHORITY_INHERITANCE", "STALE_LEASE", "SECRET_EXPOSURE"),
        StrategyMode.STRICTER_SPECIALIZED,
    ),
    "SECONDARY_BRAIN": _profile(
        "SECONDARY_BRAIN", "Secondary Brain", "MEMORY_RETRIEVAL",
        "Maximize current canonical recovery, provenance fidelity and stale-state rejection.",
        ("ROUTE_SUCCESS_MEMORY", "CORRECTION_RETENTION", "PROVENANCE_FIDELITY", "STALE_STATE_REJECTION"),
        ("MEMORY_AS_PRIMARY_EVIDENCE", "SUPERSEDED_STATE_REINTRODUCTION", "HIDDEN_ACCESS_CLAIM"),
    ),
    "MASTER_BIBLE": _profile(
        "MASTER_BIBLE", "Master Bible", "HUMAN_PROJECTION",
        "Maximize faithful human-readable projection of canonical state without becoming a competing state store.",
        ("CANONICAL_REGISTRY_PROJECTION", "NON_DILUTION", "VERSION_RECONCILIATION", "PROJECTION_READBACK"),
        ("BIBLE_AS_PROVIDER_PROOF", "DUPLICATE_CANONICAL_AUTHORITY", "STALE_PROJECTION_PROMOTION"),
    ),
    "CORPUS_FACTORY": _profile(
        "CORPUS_FACTORY", "Universal Corpus Factory", "INGESTION",
        "Maximize complete, deduplicated, provenance-rich evidence ingestion.",
        ("UNIVERSAL_EVIDENCE_OBJECT", "CONTENT_IDENTITY", "PROVENANCE_CHAIN", "DELTA_INGESTION"),
        ("CARRIER_COPY_AS_INDEPENDENT_EVIDENCE", "UNPROVEN_OCR", "SOURCE_LINEAGE_LOSS"),
    ),
    "IN_PLACE_AUDIT": _profile(
        "IN_PLACE_AUDIT", "In-Place Audit Ω", "ASSURANCE",
        "Maximize audit reproducibility, bounded findings and independent proof envelopes.",
        ("AUDIT_ENVELOPE", "FINDING_SOURCE_LINK", "REPERFORMANCE", "CLOSURE_RECEIPT"),
        ("AUDIT_AS_EXECUTION_PROOF", "FINDING_WITHOUT_SOURCE", "SELF_CERTIFIED_CLOSURE"),
    ),
    "HEARTBEAT_MESH": _profile(
        "HEARTBEAT_MESH", "Heartbeat Mesh", "OBSERVABILITY",
        "Maximize current observability while remaining a read-only projection of canonical state.",
        ("TTL_HEARTBEAT", "ADAPTER_STATE", "FRESHNESS_DEGRADATION", "NO_AUTHORITY_PROMOTION"),
        ("STALE_HEARTBEAT_AS_LIVE", "DASHBOARD_AS_STATE_AUTHORITY", "REGISTERED_AS_CONNECTED"),
    ),
    "DIRECT_RUNTIME": _profile(
        "DIRECT_RUNTIME", "Federation Direct Runtime", "EXECUTION_VIEW",
        "Maximize command-to-proof-to-recovery integrity.",
        ("COMMAND_CONTRACT", "SEMANTIC_READBACK", "RECOVERY_LEDGER", "TERMINAL_EVENT"),
        ("TRANSPORT_AS_SEMANTIC_SUCCESS", "UNPROVEN_DONE", "RECOVERY_WITHOUT_ROLLBACK"),
    ),
    "MATTER_LEDGER": _profile(
        "MATTER_LEDGER", "Matter Evidence Operations Ledgers", "MATTER_CONTROL",
        "Maximize matter-specific evidence/work readiness without leaking across case walls.",
        ("MATTER_ASSIGNMENT_GATE", "SOURCE_CLAIM_GRAPH", "ROUTE_SEPARATION", "FILING_DEPENDENCY_MAP"),
        ("CROSS_MATTER_CONTAMINATION", "UNSUPPORTED_LEGAL_CONCLUSION", "GLOBAL_STATE_OVERRIDE"),
    ),
    "TRUTHGRID": _profile(
        "TRUTHGRID", "TruthGrid", "EVIDENTIARY_DECISION_ENGINE",
        "Minimize unresolved material evidentiary uncertainty and prove finality dimensions separately.",
        ("TRUTHSTATE", "EVIDENTIARY_GRAPH", "FALSIFICATION_ENGINE", "COMPLETION_VECTOR", "CLOSURE_OPTIMIZER"),
        ("ROLE_TO_AUTHORITY_INFLATION", "SYSTEM_TO_PERSONAL_ACTION_INFERENCE", "PROCESSING_AVAILABILITY_CONFLATION"),
        StrategyMode.STRICTER_SPECIALIZED,
    ),
    "JFRIE": _profile(
        "JFRIE", "JFRIE / EACIA", "RELEASE_INTEGRITY",
        "Minimize jurisdiction error, evidence contamination and unsafe release.",
        ("JURISDICTION_FIRST", "CONTAMINATION_QUARANTINE", "RELEASE_FIREWALL", "POST_REPAIR_RECHECK"),
        ("WRONG_FORUM", "CONTAMINATED_CLAIM_RELEASE", "BYPASS_OF_RELEASE_VETO"),
        StrategyMode.STRICTER_SPECIALIZED,
    ),
    "LEX_OMEGA": _profile(
        "LEX_OMEGA", "LEX-OMEGA", "LEGAL_REASONING",
        "Maximize current, falsifiable and evidence-bound legal/forensic reasoning.",
        ("AUTHORITY_HIERARCHY", "CURRENT_LAW_REVALIDATION", "COMPETING_LEGAL_HYPOTHESES", "REMEDY_FORUM_MATCH"),
        ("FABRICATED_AUTHORITY", "OUTDATED_LAW_PROMOTION", "WRONG_FORUM"),
        StrategyMode.STRICTER_SPECIALIZED,
    ),
    "CASEFORGE": _profile(
        "CASEFORGE", "CASEFORGE-Ω / SCIENTIA", "SCIENTIFIC_EVOLUTION",
        "Maximize independent falsification, regression learning and measured promotion quality.",
        ("BLIND_RUNNER", "COMPETING_HYPOTHESES", "MUTATION_TESTING", "EVOLUTION_GOVERNOR", "CAPABILITY_FORGE"),
        ("ANSWER_KEY_LEAK", "SELF_PROMOTION", "FATAL_REGRESSION"),
        StrategyMode.STRICTER_SPECIALIZED,
    ),
    "KAIO": _profile(
        "KAIO", "KAIO Fluid Intelligence", "ADAPTIVE_INTELLIGENCE",
        "Maximize adaptive route formation and solution morphogenesis under proof and rollback constraints.",
        ("FLUID_COMPILER", "MORPHOGENESIS", "SHADOW_VARIANTS", "FITNESS_LAB", "REVERSIBLE_ADAPTATION"),
        ("UNTESTED_SELF_MODIFICATION", "FITNESS_WITHOUT_PROOF", "ADAPTATION_AUTHORITY_EXPANSION"),
        StrategyMode.STRICTER_SPECIALIZED,
    ),
    "MODISA": _profile(
        "MODISA", "MODISA Continuum", "MISSION_FORMATION",
        "Maximize self-correcting mission formation, route adaptation and bounded execution continuity.",
        ("FORMATION_FIELD", "MISSION_ROUTER", "SELF_CORRECTION_LOOP", "PROOF_GATED_TRANSITION", "ROLLBACK_FORMATION"),
        ("FORMATION_AS_AUTHORITY", "UNPROVEN_AUTONOMY", "MISSION_DRIFT"),
        StrategyMode.STRICTER_SPECIALIZED,
    ),
    "CHATBRIDGE": _profile(
        "CHATBRIDGE", "ChatBridge", "CROSS_CHAT_CONTINUITY",
        "Maximize deterministic restore of current mission, corrections, successful routes and control bindings.",
        ("STARTUP_ATTESTATION", "RESTORE_POINTER", "CORRECTION_RETENTION", "CAPABILITY_GATE_AUTOLOAD"),
        ("HIDDEN_CHAT_ACCESS_CLAIM", "STALE_CONTEXT_REINTRODUCTION", "RESTORE_WITHOUT_READBACK"),
    ),
    "KIM_DATAVERSE": _profile(
        "KIM_DATAVERSE", "Kim Dataverse", "PRIVATE_CANONICAL_BRIDGE",
        "Maximize private canonical pointer integrity, directive continuity and proof-bound cross-surface state.",
        ("STABLE_POINTERS", "DIRECTIVE_SCOPE_LOCK", "RECEIPT_LEDGER", "BOUNDARY_REGISTRY", "ALIAS_RESOLUTION"),
        ("SECRET_PERSISTENCE", "STALE_POINTER", "BRIDGE_BOUND_AS_PROVIDER_BOUND"),
        StrategyMode.STRICTER_SPECIALIZED,
    ),
}


__all__ = [
    "ALL_STAGES",
    "AUTHORITY_CEILING",
    "AutomationClass",
    "EvolutionDecision",
    "EvolutionMaturity",
    "EvolutionStage",
    "FederationEvolutionOrchestrator",
    "STAGE_SPECS",
    "SYSTEM_PROFILES",
    "StageEvidence",
    "StageSpec",
    "StrategyMode",
    "SystemEvolutionProfile",
    "SystemEvolutionState",
]
