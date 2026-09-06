"""FUSE Mission Outcome / Value Court v1.

Mission completion is a distinct proof level from action admission or effect success.
The court aggregates terminal action closures, outcome-contract evidence, required proof
artifacts and declared value observations. It never infers owner value from source,
transport ACKs, partial actions, or rollback-only recovery.

Provider-neutral and effect-free.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping, Sequence

from federation.execution_readback_closure_v1 import ClosureState, ExecutionClosureReceipt
from federation.mission_ir import MissionIR

SCHEMA = "FUSE-MISSION-OUTCOME-VALUE-COURT-V1"
VERSION = "1.0.0"


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


class MissionOutcomeState(str, Enum):
    HELD = "MISSION_HELD"
    EFFECTS_VERIFIED = "MISSION_EFFECTS_VERIFIED"
    BEHAVIOUR_VERIFIED = "MISSION_BEHAVIOUR_VERIFIED"
    VALUE_OBSERVED = "MISSION_VALUE_OBSERVED"


@dataclass(frozen=True, slots=True)
class RequiredAction:
    action_id: str
    require_behaviour: bool = False

    def validate(self) -> "RequiredAction":
        if not self.action_id.strip():
            raise ValueError("MISSION_REQUIRED_ACTION_ID_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class OutcomeEvidence:
    evidence_id: str
    mission_id: str
    outcome_contract: str
    source_ref: str
    semantic_match: bool
    fresh: bool = True

    def validate(self) -> "OutcomeEvidence":
        if not all((self.evidence_id.strip(), self.mission_id.strip(), self.outcome_contract.strip(), self.source_ref.strip())):
            raise ValueError("MISSION_OUTCOME_EVIDENCE_IDENTITY_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class ValueObservation:
    metric: str
    source_ref: str
    observed_value: str
    meets_target: bool
    fresh: bool = True

    def validate(self) -> "ValueObservation":
        if not all((self.metric.strip(), self.source_ref.strip(), self.observed_value.strip())):
            raise ValueError("MISSION_VALUE_OBSERVATION_IDENTITY_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class MissionOutcomeReceipt:
    mission_id: str
    mission_digest: str
    state: MissionOutcomeState
    verified_actions: tuple[str, ...]
    behaviour_actions: tuple[str, ...]
    missing_actions: tuple[str, ...]
    missing_proofs: tuple[str, ...]
    missing_value_metrics: tuple[str, ...]
    reasons: tuple[str, ...]
    receipt_digest: str

    @property
    def complete(self) -> bool:
        return self.state in {MissionOutcomeState.BEHAVIOUR_VERIFIED, MissionOutcomeState.VALUE_OBSERVED}

    @property
    def value_observed(self) -> bool:
        return self.state is MissionOutcomeState.VALUE_OBSERVED


class MissionOutcomeValueCourt:
    """Fail closed from verified actions to mission-level outcome and value proof."""

    def decide(
        self,
        *,
        mission: MissionIR,
        required_actions: Sequence[RequiredAction],
        closures: Sequence[ExecutionClosureReceipt],
        outcome_evidence: OutcomeEvidence | None,
        proof_evidence: Mapping[str, str] | None = None,
        value_observations: Sequence[ValueObservation] = (),
    ) -> MissionOutcomeReceipt:
        mission.validate()
        proof_evidence = dict(proof_evidence or {})
        required: dict[str, RequiredAction] = {}
        for item in required_actions:
            item.validate()
            if item.action_id in required:
                raise ValueError("DUPLICATE_MISSION_REQUIRED_ACTION")
            required[item.action_id] = item

        closure_by_action: dict[str, ExecutionClosureReceipt] = {}
        for closure in closures:
            if closure.mission_id != mission.mission_id:
                continue
            prior = closure_by_action.get(closure.action_id)
            rank = {
                ClosureState.BEHAVIOUR_VERIFIED: 4,
                ClosureState.EFFECT_VERIFIED: 3,
                ClosureState.ROLLED_BACK_VERIFIED: 2,
            }.get(closure.state, 0)
            prior_rank = 0 if prior is None else {
                ClosureState.BEHAVIOUR_VERIFIED: 4,
                ClosureState.EFFECT_VERIFIED: 3,
                ClosureState.ROLLED_BACK_VERIFIED: 2,
            }.get(prior.state, 0)
            if rank > prior_rank:
                closure_by_action[closure.action_id] = closure

        verified: list[str] = []
        behavioural: list[str] = []
        missing: list[str] = []
        reasons: list[str] = []
        for action_id, requirement in required.items():
            closure = closure_by_action.get(action_id)
            if closure is None:
                missing.append(action_id); continue
            if closure.state in {ClosureState.EFFECT_VERIFIED, ClosureState.BEHAVIOUR_VERIFIED}:
                verified.append(action_id)
            else:
                missing.append(action_id)
                if closure.state is ClosureState.ROLLED_BACK_VERIFIED:
                    reasons.append(f"{action_id}:ROLLBACK_RECOVERY_IS_NOT_MISSION_SUCCESS")
                continue
            if closure.state is ClosureState.BEHAVIOUR_VERIFIED:
                behavioural.append(action_id)
            elif requirement.require_behaviour:
                missing.append(action_id)
                reasons.append(f"{action_id}:BEHAVIOUR_PROOF_REQUIRED")

        missing = sorted(set(missing))
        missing_proofs = sorted(p for p in mission.proof_requirements if not str(proof_evidence.get(p, "")).strip())

        if outcome_evidence is None:
            reasons.append("OUTCOME_CONTRACT_EVIDENCE_REQUIRED")
        else:
            outcome_evidence.validate()
            if outcome_evidence.mission_id != mission.mission_id:
                reasons.append("OUTCOME_EVIDENCE_MISSION_MISMATCH")
            if outcome_evidence.outcome_contract != mission.outcome_contract:
                reasons.append("OUTCOME_CONTRACT_MISMATCH")
            if not outcome_evidence.fresh:
                reasons.append("OUTCOME_EVIDENCE_NOT_FRESH")
            if not outcome_evidence.semantic_match:
                reasons.append("OUTCOME_CONTRACT_NOT_SATISFIED")

        observations: dict[str, ValueObservation] = {}
        for item in value_observations:
            item.validate()
            if item.metric in observations:
                raise ValueError("DUPLICATE_VALUE_METRIC_OBSERVATION")
            observations[item.metric] = item
        missing_values: list[str] = []
        failed_values: list[str] = []
        for metric in mission.value_metrics:
            item = observations.get(metric)
            if item is None or not item.fresh:
                missing_values.append(metric)
            elif not item.meets_target:
                failed_values.append(metric)

        blocking = bool(missing or missing_proofs or reasons or missing_values or failed_values)
        if blocking:
            if failed_values:
                reasons.extend(f"VALUE_TARGET_NOT_MET:{m}" for m in failed_values)
            return self._receipt(mission, MissionOutcomeState.HELD, verified, behavioural, missing, missing_proofs, missing_values, reasons)

        all_behaviour = all(required[a].require_behaviour is False or a in behavioural for a in required)
        if mission.value_metrics:
            state = MissionOutcomeState.VALUE_OBSERVED
        elif all_behaviour and behavioural:
            state = MissionOutcomeState.BEHAVIOUR_VERIFIED
        else:
            state = MissionOutcomeState.EFFECTS_VERIFIED
        return self._receipt(mission, state, verified, behavioural, (), (), (), ())

    def _receipt(self, mission, state, verified, behavioural, missing, missing_proofs, missing_values, reasons):
        material = {
            "schema": SCHEMA, "version": VERSION, "mission": mission.digest(),
            "state": state.value, "verified": sorted(verified), "behaviour": sorted(behavioural),
            "missing": sorted(missing), "missing_proofs": sorted(missing_proofs),
            "missing_values": sorted(missing_values), "reasons": sorted(reasons),
        }
        return MissionOutcomeReceipt(
            mission_id=mission.mission_id, mission_digest=mission.digest(), state=state,
            verified_actions=tuple(sorted(verified)), behaviour_actions=tuple(sorted(behavioural)),
            missing_actions=tuple(sorted(missing)), missing_proofs=tuple(sorted(missing_proofs)),
            missing_value_metrics=tuple(sorted(missing_values)), reasons=tuple(sorted(reasons)),
            receipt_digest=_digest(material),
        )


__all__ = [
    "SCHEMA", "VERSION", "MissionOutcomeState", "RequiredAction", "OutcomeEvidence",
    "ValueObservation", "MissionOutcomeReceipt", "MissionOutcomeValueCourt",
]
