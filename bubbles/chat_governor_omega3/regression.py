"""Convert observed ChatGov integrity failures into durable replay candidates.

This is a clean current-main restack of the previously isolated CFBE experiment.
It reuses ChatGov DurableState and optionally forwards normalized learning to an
existing ledger callback. It creates no second learning authority and no provider
effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Callable, Mapping, Optional

from .state import DurableState


_FAILURE_TO_TEST = {
    "F19": "test_known_actionable_gap_blocks_premature_termination",
    "F20": "test_source_runtime_conflation_is_blocked_by_claim_snapshot",
    "F21": "test_source_runtime_conflation_is_blocked_by_claim_snapshot",
    "F22": "test_orphaned_mandatory_control_blocks_final_response",
    "F23": "test_outcome_first_recoverable_issue_forces_continued_recovery",
    "F24": "test_material_maturity_words_require_claim_proof_scan",
    "F25": "test_owner_attention_suppresses_recoverable_progress_noise",
    "F26": "test_raw_side_task_payload_cannot_reenter_parent_context",
    "F27": "test_verified_activity_result_replays_without_provider_reexecution",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


@dataclass(frozen=True, slots=True)
class ObservedIntegrityIncident:
    mission_id: str
    failure_code: str
    claim: str
    observed_fruit: str
    desired_outcome: str
    affected_capabilities: tuple[str, ...] = ()
    trace_ref: str = ""
    replay_state: Mapping[str, Any] | None = None

    def validate(self) -> None:
        for field_name in ("mission_id", "failure_code", "claim", "observed_fruit", "desired_outcome"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} is required")
        if self.failure_code not in _FAILURE_TO_TEST:
            raise ValueError(f"unsupported chat-integrity failure code: {self.failure_code}")


@dataclass(frozen=True, slots=True)
class RegressionCandidate:
    fingerprint: str
    mission_id: str
    failure_code: str
    regression_test: str
    trace_ref: str
    replay_state: Mapping[str, Any]
    duplicate: bool
    checkpoint_id: str


LearningSink = Callable[[dict[str, Any], tuple[str, ...]], Any]


class TraceToRegressionBridge:
    version = "1.1.0"

    def __init__(self, state: DurableState, *, learning_sink: Optional[LearningSink] = None) -> None:
        self.state = state
        self.learning_sink = learning_sink

    @staticmethod
    def fingerprint(incident: ObservedIntegrityIncident) -> str:
        incident.validate()
        identity = {
            "failure_code": incident.failure_code,
            "claim": incident.claim,
            "observed_fruit": incident.observed_fruit,
            "desired_outcome": incident.desired_outcome,
            "affected_capabilities": sorted(map(str, incident.affected_capabilities)),
        }
        return sha256(_canonical(identity).encode("utf-8")).hexdigest()

    def capture(self, incident: ObservedIntegrityIncident) -> RegressionCandidate:
        incident.validate()
        fingerprint = self.fingerprint(incident)
        regression_test = _FAILURE_TO_TEST[incident.failure_code]
        key = f"chatgov:integrity-regression:{fingerprint}"
        existing = self.state.get_receipt(key)
        replay_state = dict(incident.replay_state or {})
        payload = {
            "schema": "CHATGOV-INTEGRITY-REGRESSION-CANDIDATE-V1",
            "version": self.version,
            "fingerprint": fingerprint,
            "incident": {
                "mission_id": incident.mission_id,
                "failure_code": incident.failure_code,
                "claim": incident.claim,
                "observed_fruit": incident.observed_fruit,
                "desired_outcome": incident.desired_outcome,
                "affected_capabilities": sorted(set(map(str, incident.affected_capabilities))),
                "trace_ref": incident.trace_ref,
            },
            "regression_test": regression_test,
            "replay_state": replay_state,
            "authority_expansion": False,
            "provider_effect": False,
        }
        self.state.save_receipt(
            key=key,
            mission_id=incident.mission_id,
            action="CAPTURE_CHAT_INTEGRITY_REGRESSION",
            target=incident.failure_code,
            success=True,
            semantic_ok=True,
            payload=payload,
        )
        checkpoint_id = self.state.checkpoint(
            incident.mission_id,
            {"event": "CHAT_INTEGRITY_REGRESSION_CANDIDATE", "candidate": payload, "duplicate": existing is not None},
            proof_bearing=False,
        )
        self.state.update_metric("chatgov.regression.captured", 1.0)
        self.state.update_metric("chatgov.regression.duplicate", 1.0 if existing is not None else 0.0)
        if self.learning_sink is not None:
            self.learning_sink(
                {
                    "failure_code": incident.failure_code,
                    "claim": incident.claim,
                    "observed_fruit": incident.observed_fruit,
                    "desired_outcome": incident.desired_outcome,
                    "affected_capabilities": list(incident.affected_capabilities),
                    "trace_ref": incident.trace_ref,
                    "reuse_decision": "PATCH_EXISTING",
                },
                (regression_test,),
            )
        return RegressionCandidate(
            fingerprint=fingerprint,
            mission_id=incident.mission_id,
            failure_code=incident.failure_code,
            regression_test=regression_test,
            trace_ref=incident.trace_ref,
            replay_state=replay_state,
            duplicate=existing is not None,
            checkpoint_id=checkpoint_id,
        )


__all__ = ["ObservedIntegrityIncident", "RegressionCandidate", "TraceToRegressionBridge"]
