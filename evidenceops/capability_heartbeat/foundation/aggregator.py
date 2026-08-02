"""The single on-input pull aggregator; no timer, thread, cron, or push path."""

from __future__ import annotations

from dataclasses import dataclass

from .adapters.common import Observation
from .contracts import Recommendation, digest
from .errors import ContractError
from .policy import FlowDecision, FlowPolicy, FlowState, apply_flow_policy
from .privacy import require_code
from .scoring import select_recommendations


@dataclass(frozen=True, slots=True)
class AggregationResult:
    recommendations: tuple[Recommendation, ...]
    observed_count: int
    eligible_count: int
    input_digest: str
    suppressed_reason: str
    next_flow_state: FlowState

    def __post_init__(self) -> None:
        if not isinstance(self.recommendations, (tuple, list)):
            raise ContractError("AGGREGATION_RECOMMENDATIONS_SEQUENCE_REQUIRED")
        object.__setattr__(self, "recommendations", tuple(self.recommendations))

    @property
    def has_output(self) -> bool:
        return bool(self.recommendations)


@dataclass(frozen=True, slots=True)
class OnInputAggregator:
    policy: FlowPolicy = FlowPolicy()

    def on_input(
        self,
        *,
        observations: tuple[Observation, ...],
        owner_code: str,
        matter_code: str,
        now: str,
        flow_state: FlowState = FlowState(),
    ) -> AggregationResult:
        require_code(owner_code, field="owner_code")
        require_code(matter_code, field="matter_code")
        if not isinstance(observations, tuple):
            raise ContractError("OBSERVATIONS_MUST_BE_IMMUTABLE_TUPLE")
        cross_scope = [
            item for item in observations
            if item.owner_code != owner_code or item.matter_code != matter_code
        ]
        if cross_scope:
            raise ContractError("CROSS_OWNER_OR_MATTER_BLEED")
        candidates = tuple(item.candidate() for item in observations)
        decision: FlowDecision = apply_flow_policy(
            candidates=candidates,
            now=now,
            policy=self.policy,
            state=flow_state,
        )
        recommendations = select_recommendations(decision.candidates)
        input_digest = digest(
            {
                "owner_code": owner_code,
                "matter_code": matter_code,
                "observations": [
                    {
                        "source_code": item.source_code,
                        "capability_hash": item.capability_hash,
                        "semantic_receipt": item.semantic_receipt,
                        "observed_at": item.observed_at,
                    }
                    for item in observations
                ],
                "now": now,
            }
        )
        return AggregationResult(
            recommendations=recommendations,
            observed_count=len(observations),
            eligible_count=len(decision.candidates),
            input_digest=input_digest,
            suppressed_reason=decision.suppressed_reason,
            next_flow_state=decision.next_state,
        )
