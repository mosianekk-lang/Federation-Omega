from __future__ import annotations

"""CFBE Federation Scientific Fitness Court v1.

A bounded Wave-2 consumer that challenges the Federation itself.  It does not add
an executor, scheduler, memory root, provider authority, or new top-level system.
It converts explicit estate observations into falsifiable actions and a ranked,
no-effect experiment queue.  Unknown value remains unknown: absent owner-value
pairs never become a zero-value claim and provider expansion cannot substitute for
empirical value evidence.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from benchmarking.cfbe_omega.scientific_capability_compiler_v2 import (
    EcologyCapability,
    ExperimentCandidate,
    canonical_hash,
    evaluate_capability_ecology,
    generate_hypothesis,
    select_information_gain_experiment,
)

SCHEMA = "CFBE_FEDERATION_SCIENTIFIC_FITNESS_COURT_V1"
MIN_OWNER_VALUE_PAIRS = 10


class FitnessAction(str, Enum):
    RETAIN = "RETAIN"
    PROVE_OWNER_VALUE = "PROVE_OWNER_VALUE"
    REANCHOR_CURRENT_SOURCE = "REANCHOR_CURRENT_SOURCE"
    RUN_EQUIVALENCE_COURT = "RUN_EQUIVALENCE_COURT"
    PRESERVE_INDEPENDENCE = "PRESERVE_INDEPENDENCE"
    HOLD_PROVIDER_EXPANSION_UNTIL_VALUE = "HOLD_PROVIDER_EXPANSION_UNTIL_VALUE"


@dataclass(frozen=True, slots=True)
class SystemFitnessObservation:
    system_id: str
    role: str
    semantic_cluster: str
    current_projection_verified: bool
    proof_state: str
    provider_runtime_proven: bool
    owner_value_pairs: int
    invocation_evidence_count: int
    complexity_cost: float
    dependency_ids: tuple[str, ...] = ()
    independent_assurance_role: bool = False
    proof_refs: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SystemFitnessObservation":
        return cls(
            system_id=str(value.get("system_id") or "").strip(),
            role=str(value.get("role") or "").strip(),
            semantic_cluster=str(value.get("semantic_cluster") or "").strip(),
            current_projection_verified=value.get("current_projection_verified") is True,
            proof_state=str(value.get("proof_state") or "UNKNOWN").strip().upper(),
            provider_runtime_proven=value.get("provider_runtime_proven") is True,
            owner_value_pairs=int(value.get("owner_value_pairs", 0)),
            invocation_evidence_count=int(value.get("invocation_evidence_count", 0)),
            complexity_cost=float(value.get("complexity_cost", 1.0)),
            dependency_ids=tuple(sorted(set(str(x).strip() for x in value.get("dependency_ids", ()) if str(x).strip()))),
            independent_assurance_role=value.get("independent_assurance_role") is True,
            proof_refs=tuple(sorted(set(str(x).strip() for x in value.get("proof_refs", ()) if str(x).strip()))),
        ).validate()

    def validate(self) -> "SystemFitnessObservation":
        if not self.system_id or not self.role or not self.semantic_cluster:
            raise ValueError("FITNESS_SYSTEM_ID_ROLE_CLUSTER_REQUIRED")
        if self.owner_value_pairs < 0 or self.invocation_evidence_count < 0 or self.complexity_cost <= 0:
            raise ValueError("FITNESS_SYSTEM_METRICS_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class SystemActionReceipt:
    system_id: str
    actions: tuple[FitnessAction, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScientificExperiment:
    experiment_id: str
    targets: tuple[str, ...]
    hypothesis: str
    primary_metric: str
    guardrails: tuple[str, ...]
    prior_uncertainty: float
    expected_posterior_uncertainty: float
    cost: float
    risk: float
    decision_relevance: float
    execution_class: str = "A1_INTERNAL_NO_EFFECT"
    owner_action_required: bool = False
    provider_effect_authorized: bool = False

    def validate(self) -> "ScientificExperiment":
        if not self.experiment_id or not self.targets or not self.hypothesis or not self.primary_metric:
            raise ValueError("FITNESS_EXPERIMENT_IDENTITY_REQUIRED")
        values = (
            self.prior_uncertainty,
            self.expected_posterior_uncertainty,
            self.cost,
            self.risk,
            self.decision_relevance,
        )
        if any(v < 0 for v in values) or self.cost <= 0:
            raise ValueError("FITNESS_EXPERIMENT_METRICS_INVALID")
        if self.expected_posterior_uncertainty > self.prior_uncertainty:
            raise ValueError("FITNESS_POSTERIOR_UNCERTAINTY_INVALID")
        if self.provider_effect_authorized:
            raise ValueError("FITNESS_COURT_MUST_NOT_AUTHORIZE_PROVIDER_EFFECT")
        return self

    @property
    def candidate(self) -> ExperimentCandidate:
        return ExperimentCandidate(
            self.experiment_id,
            self.prior_uncertainty,
            self.expected_posterior_uncertainty,
            self.cost,
            self.risk,
            self.decision_relevance,
        )


@dataclass(frozen=True, slots=True)
class FitnessCourtReceipt:
    schema: str
    source_main_sha: str
    system_count: int
    owner_value_pair_count: int
    owner_value_pair_deficit: int
    actions: tuple[SystemActionReceipt, ...]
    overlap_clusters: tuple[str, ...]
    ranked_experiment_ids: tuple[str, ...]
    next_experiment_id: str
    structural_ecology_actions: tuple[str, ...]
    new_top_level_system_required: bool
    provider_effect_authorized: bool
    stable_promotion_authorized: bool
    truth_boundary: tuple[str, ...]
    receipt_sha256: str

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": self.schema,
            "source_main_sha": self.source_main_sha,
            "system_count": self.system_count,
            "owner_value_pair_count": self.owner_value_pair_count,
            "owner_value_pair_deficit": self.owner_value_pair_deficit,
            "actions": [
                {"system_id": a.system_id, "actions": [x.value for x in a.actions], "reasons": list(a.reasons)}
                for a in self.actions
            ],
            "overlap_clusters": list(self.overlap_clusters),
            "ranked_experiment_ids": list(self.ranked_experiment_ids),
            "next_experiment_id": self.next_experiment_id,
            "structural_ecology_actions": list(self.structural_ecology_actions),
            "new_top_level_system_required": self.new_top_level_system_required,
            "provider_effect_authorized": self.provider_effect_authorized,
            "stable_promotion_authorized": self.stable_promotion_authorized,
            "truth_boundary": list(self.truth_boundary),
        }
        if include_hash:
            payload["receipt_sha256"] = self.receipt_sha256
        return payload


def derive_system_actions(item: SystemFitnessObservation) -> SystemActionReceipt:
    item.validate()
    actions: list[FitnessAction] = []
    reasons: list[str] = []
    if not item.current_projection_verified:
        actions.append(FitnessAction.REANCHOR_CURRENT_SOURCE)
        reasons.append("current comparison target not verified")
    if item.owner_value_pairs < MIN_OWNER_VALUE_PAIRS:
        actions.append(FitnessAction.PROVE_OWNER_VALUE)
        reasons.append("strict owner-value cohort incomplete")
    if not item.provider_runtime_proven and item.owner_value_pairs < MIN_OWNER_VALUE_PAIRS:
        actions.append(FitnessAction.HOLD_PROVIDER_EXPANSION_UNTIL_VALUE)
        reasons.append("provider expansion cannot substitute for value proof")
    if item.independent_assurance_role:
        actions.append(FitnessAction.PRESERVE_INDEPENDENCE)
        reasons.append("independent assurance must not be subsumed by benchmark authority")
    if not actions:
        actions.append(FitnessAction.RETAIN)
        reasons.append("no material fitness action identified")
    return SystemActionReceipt(item.system_id, tuple(actions), tuple(reasons))


def _structural_ecology(systems: Sequence[SystemFitnessObservation]):
    capabilities = []
    for item in systems:
        # This is deliberately an evidence-coverage proxy, not an owner-value score.
        evidence_proxy = 1.0 if item.owner_value_pairs >= MIN_OWNER_VALUE_PAIRS else 0.0
        capabilities.append(
            EcologyCapability(
                capability_id=item.system_id,
                value_score=evidence_proxy,
                complexity_cost=item.complexity_cost,
                invocation_count=item.invocation_evidence_count,
                dependency_ids=item.dependency_ids,
                semantic_cluster=item.semantic_cluster,
            )
        )
    return evaluate_capability_ecology(tuple(capabilities), dormant_threshold=0)


def rank_experiments(experiments: Sequence[ScientificExperiment]) -> tuple[ScientificExperiment, ...]:
    if not experiments:
        raise ValueError("FITNESS_EXPERIMENTS_REQUIRED")
    by_id: dict[str, ScientificExperiment] = {}
    for item in experiments:
        item.validate()
        if item.experiment_id in by_id:
            raise ValueError("FITNESS_EXPERIMENT_IDS_UNIQUE_REQUIRED")
        by_id[item.experiment_id] = item
    remaining = list(experiments)
    ordered: list[ScientificExperiment] = []
    while remaining:
        selected = select_information_gain_experiment([item.candidate for item in remaining])
        winner = by_id[selected.experiment_id]
        ordered.append(winner)
        remaining = [item for item in remaining if item.experiment_id != winner.experiment_id]
    return tuple(ordered)


def default_scientific_experiments() -> tuple[ScientificExperiment, ...]:
    raw = (
        ("EXP-CFBE-FIT-001", ("BUBBLES","CFBE"), "Prospective real matched missions reduce owner minutes and interventions without verified-output regression.", "owner_minutes_and_interventions", ("verified_output_ratio_not_lower","no_new_owner_technical_decision"), .95,.25,1.0,.05,1.0),
        ("EXP-CFBE-FIT-002", ("BUBBLES","FORMATION_OMEGA","OMEGA_ONE"), "The three orchestration surfaces contain materially distinct primitives; redundant primitives can be aliased without mission-closure regression.", "unique_primitive_and_behavior_delta", ("semantic_terminal_equivalence","no_authority_inheritance"), .90,.45,.85,.05,.95),
        ("EXP-CFBE-FIT-003", ("JARVIS","REALITY_GUARD","PROOFOS"), "Independent assurance surfaces are complementary rather than duplicate; each should catch a distinct falsification class.", "distinct_failure_detection_gain", ("independence_preserved","false_positive_rate_bounded"), .88,.45,.80,.05,.92),
        ("EXP-CFBE-FIT-004", ("KDV",), "Canonical KDV lookup reduces retrieval work and context load without reducing source accuracy versus broad state rehydration.", "verified_retrieval_per_work_unit", ("same_source_accuracy","no_private_data_expansion"), .82,.35,.85,.03,.90),
        ("EXP-CFBE-FIT-005", ("SENTINEL","CFBE"), "Freshness/reconciliation controls reduce stale-current duration and false-current claims after source movement.", "projection_convergence_seconds", ("history_append_only","no_maturity_inheritance"), .78,.32,.80,.03,.88),
        ("EXP-CFBE-FIT-006", ("FAILURE_WIN_AUTOFIX",), "Failure-Win/AutoFIX reduces unchanged-route retries and time-to-recovery under bounded fault injection.", "recovery_work_units", ("same_terminal_outcome","no_hidden_retry"), .86,.40,.90,.05,.90),
        ("EXP-CFBE-FIT-007", ("BUBBLES",), "Context and payload governors reduce admitted context/work units without losing decision-critical evidence.", "context_units_per_verified_outcome", ("evidence_recall_not_lower","secret_redaction_preserved"), .90,.42,.82,.04,.92),
        ("EXP-CFBE-FIT-008", ("OMEGA_ONE",), "Adaptive scheduling beats a simple deterministic scheduler on fixed DAGs without fairness or recovery regression.", "completion_time_and_retry_work", ("same_task_set","fairness_not_lower","source_reanchor_required_first"), .82,.46,1.0,.05,.80),
        ("EXP-CFBE-FIT-009", ("SOVARA",), "Capability-bound authority rejects unauthorized effects more precisely than broad-role routing in an effect-free simulation.", "unsafe_route_rejection_precision", ("zero_provider_effect","authorized_read_only_routes_preserved"), .76,.31,.75,.03,.82),
        ("EXP-CFBE-FIT-010", ("CFBE",), "Information-gain experiment ordering reduces cost-to-decision versus FIFO experiment ordering.", "information_gain_per_cost", ("same_candidate_pool","same_stopping_rule"), .84,.36,.80,.03,.91),
        ("EXP-CFBE-FIT-011", ("CFBE_WAVE2","CFBE_WAVE1"), "Wave 2 produces fewer semantic duplicates and higher actionable-mechanism yield than feature-list harvesting.", "unique_actionable_primitives_per_candidate", ("blind_holdout_set","same_public_source_corpus"), .90,.32,1.15,.04,.82),
        ("EXP-CFBE-FIT-012", ("COHERENCE_CONTROLLER",), "Repeated level-based reconciliation keeps current projections within the declared TTL across independent source advances.", "current_projection_lag", ("no_background_execution_claim","no_history_overwrite"), .80,.38,.70,.02,.84),
    )
    return tuple(
        ScientificExperiment(
            experiment_id=eid, targets=targets, hypothesis=hyp, primary_metric=metric,
            guardrails=guards, prior_uncertainty=prior,
            expected_posterior_uncertainty=posterior, cost=cost, risk=risk,
            decision_relevance=relevance,
        ).validate()
        for eid, targets, hyp, metric, guards, prior, posterior, cost, risk, relevance in raw
    )


def compile_fitness_court(
    *, source_main_sha: str, system_observations: Sequence[Mapping[str, Any]], owner_value_pair_count: int
) -> FitnessCourtReceipt:
    if len(source_main_sha) != 40 or any(ch not in "0123456789abcdef" for ch in source_main_sha.lower()):
        raise ValueError("FITNESS_SOURCE_MAIN_SHA_INVALID")
    if owner_value_pair_count < 0:
        raise ValueError("FITNESS_OWNER_VALUE_PAIR_COUNT_INVALID")
    systems = tuple(SystemFitnessObservation.from_mapping(item) for item in system_observations)
    if not systems:
        raise ValueError("FITNESS_SYSTEM_OBSERVATIONS_REQUIRED")
    if len({item.system_id for item in systems}) != len(systems):
        raise ValueError("FITNESS_SYSTEM_IDS_UNIQUE_REQUIRED")

    actions = tuple(derive_system_actions(item) for item in systems)
    ecology = _structural_ecology(systems)
    cluster_counts: dict[str, int] = {}
    for item in systems:
        cluster_counts[item.semantic_cluster] = cluster_counts.get(item.semantic_cluster, 0) + 1
    overlap = tuple(sorted(k for k, v in cluster_counts.items() if v >= 3))

    experiments = default_scientific_experiments()
    ranked = rank_experiments(experiments)
    next_experiment = ranked[0]
    # Preregister the highest-value hypothesis through the Wave-2 hypothesis control.
    generate_hypothesis(
        capability_id="FEDERATION_OWNER_VALUE",
        outcome_metric="owner_minutes_and_interventions",
        expected_direction="DECREASE",
        minimum_effect=0.10,
        guardrail_metrics=("verified_output_ratio", "correction_count"),
        disqualifiers=("quality_regression", "higher_owner_burden"),
    )

    payload = {
        "schema": SCHEMA,
        "source_main_sha": source_main_sha,
        "system_count": len(systems),
        "owner_value_pair_count": owner_value_pair_count,
        "owner_value_pair_deficit": max(0, MIN_OWNER_VALUE_PAIRS - owner_value_pair_count),
        "actions": [
            {"system_id": a.system_id, "actions": [x.value for x in a.actions], "reasons": list(a.reasons)}
            for a in actions
        ],
        "overlap_clusters": overlap,
        "ranked_experiment_ids": [item.experiment_id for item in ranked],
        "next_experiment_id": next_experiment.experiment_id,
        "structural_ecology_actions": list(ecology.actions),
        "new_top_level_system_required": False,
        "provider_effect_authorized": False,
        "stable_promotion_authorized": False,
        "truth_boundary": (
            "absence of owner-value pairs means value is unproven, not zero",
            "structural overlap is only a trigger for an equivalence court, not a merge decision",
            "provider expansion cannot substitute for measured owner value",
            "independent assurance roles must remain independent",
            "all experiments are A1/internal and no-effect until separately authorized",
        ),
    }
    return FitnessCourtReceipt(
        schema=SCHEMA,
        source_main_sha=source_main_sha,
        system_count=len(systems),
        owner_value_pair_count=owner_value_pair_count,
        owner_value_pair_deficit=payload["owner_value_pair_deficit"],
        actions=actions,
        overlap_clusters=overlap,
        ranked_experiment_ids=tuple(payload["ranked_experiment_ids"]),
        next_experiment_id=next_experiment.experiment_id,
        structural_ecology_actions=tuple(ecology.actions),
        new_top_level_system_required=False,
        provider_effect_authorized=False,
        stable_promotion_authorized=False,
        truth_boundary=payload["truth_boundary"],
        receipt_sha256=canonical_hash(payload),
    )


__all__ = [
    "FitnessAction","FitnessCourtReceipt","ScientificExperiment","SystemActionReceipt",
    "SystemFitnessObservation","compile_fitness_court","default_scientific_experiments",
    "derive_system_actions","rank_experiments",
]
