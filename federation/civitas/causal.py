from __future__ import annotations

"""Proof-bound causal digital twin for Federation Ω.

Correlation, topology, prediction and model consensus are never promoted to
causation. A causal write requires temporal order, a falsifier, mechanism or
intervention evidence, independent replication and no unresolved contradiction.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from .contracts import CivitasError, ProofRef, digest, in_unit_interval, safe_id


class CausalState(str, Enum):
    NONE = "NONE"
    CORRELATED = "CORRELATED"
    HYPOTHESIS = "HYPOTHESIS"
    SUPPORTED = "SUPPORTED"
    REPLICATED = "REPLICATED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class CausalClaim:
    claim_id: str
    cause_id: str
    effect_id: str
    mechanism: str
    falsifier: str
    matter_scope: str = "GLOBAL"
    prior_probability: float = 0.5

    def validate(self) -> "CausalClaim":
        safe_id(self.claim_id, "claim_id")
        safe_id(self.cause_id, "cause_id")
        safe_id(self.effect_id, "effect_id")
        if self.cause_id == self.effect_id:
            raise ValueError("cause and effect must differ")
        if not self.mechanism.strip() or not self.falsifier.strip():
            raise ValueError("mechanism and falsifier required")
        in_unit_interval(self.prior_probability, "prior_probability")
        if not self.matter_scope.strip():
            raise ValueError("matter_scope required")
        return self


@dataclass(frozen=True)
class CausalObservation:
    observation_id: str
    claim_id: str
    proof: ProofRef
    supports_claim: bool = True
    temporal_order: bool = False
    intervention_observed: bool = False
    mechanism_supported: bool = False
    falsifier_tested: bool = False
    effect_size: float = 0.0
    confounders_addressed: tuple[str, ...] = ()

    def validate(self) -> "CausalObservation":
        safe_id(self.observation_id, "observation_id")
        safe_id(self.claim_id, "claim_id")
        self.proof.validate()
        if not -1.0 <= float(self.effect_size) <= 1.0:
            raise ValueError("effect_size must be in [-1,1]")
        return self


@dataclass(frozen=True)
class CausalAssessment:
    claim_id: str
    state: CausalState
    posterior_support: float
    supporting_observations: tuple[str, ...]
    contradicting_observations: tuple[str, ...]
    independent_sources: tuple[str, ...]
    missing_gates: tuple[str, ...]
    causal_write_permitted: bool
    explanation: str
    external_effects: int = 0


@dataclass(frozen=True)
class ExperimentCandidate:
    experiment_id: str
    claim_id: str
    intervention: str
    information_gain: float
    falsifiability: float
    reversibility: float
    proof_gap_reduction: float
    cost: float
    risk: float
    proof_ref: str
    external_effect: bool = False

    def validate(self) -> "ExperimentCandidate":
        safe_id(self.experiment_id, "experiment_id")
        safe_id(self.claim_id, "claim_id")
        if not self.intervention.strip() or not self.proof_ref.strip():
            raise ValueError("intervention and proof_ref required")
        for name in (
            "information_gain", "falsifiability", "reversibility",
            "proof_gap_reduction", "cost", "risk",
        ):
            in_unit_interval(getattr(self, name), name)
        return self

    @property
    def utility(self) -> float:
        self.validate()
        return round(
            0.30 * self.information_gain
            + 0.24 * self.falsifiability
            + 0.18 * self.reversibility
            + 0.18 * self.proof_gap_reduction
            - 0.04 * self.cost
            - 0.06 * self.risk,
            8,
        )


@dataclass(frozen=True)
class ExperimentDecision:
    selected_experiment_id: str
    utility: float
    rejected_ids: tuple[str, ...]
    disposition: str
    causal_promotion: bool = False
    external_effects: int = 0


@dataclass(frozen=True)
class CounterfactualImpact:
    removed_nodes: tuple[str, ...]
    impacted_nodes: tuple[str, ...]
    blast_radius: int
    topology_only: bool = True
    causal_claim: bool = False
    external_effects: int = 0


@dataclass(frozen=True)
class PrecursorSignal:
    signal_id: str
    target_id: str
    warning_class: str
    severity: float
    evidence_refs: tuple[str, ...]
    disposition: str = "PREVENTIVE_REVIEW"
    causal_claim: bool = False
    external_effects: int = 0


class CausalFederationTwin:
    """Evidence-bound causal registry and reversible experiment planner."""

    def __init__(self) -> None:
        self._claims: dict[str, CausalClaim] = {}
        self._observations: dict[str, list[CausalObservation]] = {}
        self._dependencies: dict[str, set[str]] = {}
        self._events: list[Mapping[str, Any]] = []

    @property
    def event_head(self) -> str:
        return self._events[-1]["event_sha256"] if self._events else "GENESIS"

    def _event(self, event_type: str, object_id: str, payload: Mapping[str, Any]) -> str:
        body = {
            "sequence": len(self._events) + 1,
            "event_type": event_type,
            "object_id": object_id,
            "payload": dict(payload),
            "prior": self.event_head,
        }
        event = {**body, "event_sha256": digest(body)}
        self._events.append(event)
        return event["event_sha256"]

    def register_claim(self, claim: CausalClaim) -> str:
        claim.validate()
        existing = self._claims.get(claim.claim_id)
        if existing is not None and existing != claim:
            raise CivitasError("causal claim id collision")
        self._claims[claim.claim_id] = claim
        self._observations.setdefault(claim.claim_id, [])
        return self._event("CLAIM_REGISTERED", claim.claim_id, asdict(claim))

    def observe(self, observation: CausalObservation) -> str:
        observation.validate()
        claim = self._claims.get(observation.claim_id)
        if claim is None:
            raise CivitasError("observation references unknown claim")
        if observation.proof.matter_scope not in {"GLOBAL", claim.matter_scope} and claim.matter_scope != "GLOBAL":
            raise CivitasError("cross-matter causal contamination blocked")
        existing = [item for item in self._observations[claim.claim_id] if item.observation_id == observation.observation_id]
        if existing:
            if existing[0] != observation:
                raise CivitasError("observation id reused with different content")
            return self._event("OBSERVATION_DUPLICATE", observation.observation_id, {"claim_id": claim.claim_id})
        self._observations[claim.claim_id].append(observation)
        return self._event("OBSERVATION_ADDED", observation.observation_id, asdict(observation))

    def add_dependency(self, dependent_id: str, dependency_id: str) -> None:
        safe_id(dependent_id, "dependent_id")
        safe_id(dependency_id, "dependency_id")
        if dependent_id == dependency_id:
            raise ValueError("self dependency blocked")
        self._dependencies.setdefault(dependency_id, set()).add(dependent_id)
        self._event("DEPENDENCY_ADDED", f"{dependent_id}:{dependency_id}", {"dependent": dependent_id, "dependency": dependency_id})

    def assess(self, claim_id: str) -> CausalAssessment:
        safe_id(claim_id, "claim_id")
        claim = self._claims.get(claim_id)
        if claim is None:
            raise CivitasError("unknown causal claim")
        observations = self._observations.get(claim_id, [])
        support = [item for item in observations if item.supports_claim]
        contradict = [item for item in observations if not item.supports_claim]
        strong = [
            item for item in support
            if item.temporal_order
            and item.falsifier_tested
            and (item.intervention_observed or item.mechanism_supported)
        ]
        sources = tuple(sorted({item.proof.independent_source for item in strong}))
        missing: list[str] = []
        if not any(item.temporal_order for item in support):
            missing.append("TEMPORAL_ORDER")
        if not any(item.falsifier_tested for item in support):
            missing.append("FALSIFIER_TEST")
        if not any(item.intervention_observed or item.mechanism_supported for item in support):
            missing.append("INTERVENTION_OR_MECHANISM")
        if len(sources) < 2:
            missing.append("INDEPENDENT_REPLICATION")
        if contradict:
            missing.append("CONTRADICTION_RECONCILIATION")
        weighted_support = sum(item.proof.confidence * (0.5 + 0.5 * abs(item.effect_size)) for item in support)
        weighted_contra = sum(item.proof.confidence * (0.5 + 0.5 * abs(item.effect_size)) for item in contradict)
        posterior = round(
            max(0.0, min(1.0, (claim.prior_probability + weighted_support) / (1.0 + weighted_support + weighted_contra))),
            8,
        )
        if contradict and weighted_contra > weighted_support:
            state = CausalState.REJECTED
        elif len(strong) >= 2 and len(sources) >= 2 and not contradict:
            state = CausalState.REPLICATED
        elif strong and not contradict:
            state = CausalState.SUPPORTED
        elif support:
            state = CausalState.HYPOTHESIS
        elif observations:
            state = CausalState.CORRELATED
        else:
            state = CausalState.NONE
        permitted = state == CausalState.REPLICATED and not missing
        explanation = {
            CausalState.REPLICATED: "independently replicated, falsifier-tested temporal evidence",
            CausalState.SUPPORTED: "causal support exists but independent replication is incomplete",
            CausalState.HYPOTHESIS: "support exists but causal gates are incomplete",
            CausalState.REJECTED: "contradicting evidence outweighs current support",
            CausalState.CORRELATED: "observations exist without sufficient causal structure",
            CausalState.NONE: "no observations",
        }[state]
        result = CausalAssessment(
            claim_id,
            state,
            posterior,
            tuple(item.observation_id for item in support),
            tuple(item.observation_id for item in contradict),
            sources,
            tuple(missing),
            permitted,
            explanation,
        )
        self._event("CLAIM_ASSESSED", claim_id, asdict(result))
        return result

    def design_experiment(self, candidates: Sequence[ExperimentCandidate]) -> ExperimentDecision:
        if not candidates:
            raise ValueError("experiment candidates required")
        safe: list[ExperimentCandidate] = []
        rejected: list[str] = []
        for candidate in candidates:
            candidate.validate()
            if candidate.claim_id not in self._claims:
                raise CivitasError("experiment references unknown causal claim")
            if candidate.external_effect:
                rejected.append(candidate.experiment_id)
            else:
                safe.append(candidate)
        if not safe:
            return ExperimentDecision("", 0.0, tuple(sorted(rejected)), "HOLD_FOR_SEPARATE_EFFECT_ADMISSION")
        winner = max(safe, key=lambda item: (item.utility, item.experiment_id))
        decision = ExperimentDecision(
            winner.experiment_id,
            winner.utility,
            tuple(sorted(rejected)),
            "RUN_REVERSIBLE_INTERNAL_FALSIFIER",
        )
        self._event("EXPERIMENT_SELECTED", winner.experiment_id, asdict(decision))
        return decision

    def counterfactual_impact(self, removed_nodes: Sequence[str]) -> CounterfactualImpact:
        removed = tuple(sorted({safe_id(item, "removed_node") for item in removed_nodes}))
        if not removed:
            raise ValueError("counterfactual requires nodes")
        impacted = set(removed)
        frontier = list(removed)
        while frontier:
            dependency = frontier.pop()
            for dependent in sorted(self._dependencies.get(dependency, ())):
                if dependent not in impacted:
                    impacted.add(dependent)
                    frontier.append(dependent)
        result = CounterfactualImpact(removed, tuple(sorted(impacted.difference(removed))), len(impacted.difference(removed)))
        self._event("COUNTERFACTUAL_SIMULATED", digest(asdict(result))[:20], asdict(result))
        return result

    def precursor_signals(self, target_id: str, observations: Sequence[CausalObservation]) -> tuple[PrecursorSignal, ...]:
        safe_id(target_id, "target_id")
        grouped: dict[str, list[CausalObservation]] = {}
        for item in observations:
            item.validate()
            grouped.setdefault(item.claim_id, []).append(item)
        signals: list[PrecursorSignal] = []
        for claim_id, items in sorted(grouped.items()):
            distinct = {item.proof.independent_source for item in items}
            if len(items) < 2 or len(distinct) < 2:
                continue
            severity = round(min(1.0, sum(item.proof.confidence for item in items) / len(items)), 8)
            refs = tuple(sorted({item.proof.proof_ref for item in items}))
            body = {"target": target_id, "claim": claim_id, "refs": refs}
            signals.append(PrecursorSignal(
                f"PRECURSOR-{digest(body)[:20].upper()}",
                target_id,
                f"REPEATED_PATTERN:{claim_id}",
                severity,
                refs,
            ))
        return tuple(signals)

    def verify_event_chain(self) -> bool:
        prior = "GENESIS"
        for sequence, event in enumerate(self._events, 1):
            body = {
                "sequence": sequence,
                "event_type": event["event_type"],
                "object_id": event["object_id"],
                "payload": event["payload"],
                "prior": prior,
            }
            if event["sequence"] != sequence or event["prior"] != prior or digest(body) != event["event_sha256"]:
                return False
            prior = event["event_sha256"]
        return True


__all__ = [
    "CausalState", "CausalClaim", "CausalObservation", "CausalAssessment",
    "ExperimentCandidate", "ExperimentDecision", "CounterfactualImpact",
    "PrecursorSignal", "CausalFederationTwin",
]
