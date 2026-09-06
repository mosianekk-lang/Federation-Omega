"""FUSE Autonomic Mission Spine host-binding court v1.

Validates that a live host is consuming an authentic, internally consistent
AutonomicMissionSpine receipt before provider dispatch, proof finalization, or
owner-value evaluation. This module does not execute providers or mint authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json

from federation.autonomic_mission_spine_v1 import (
    AutonomicMissionSpine,
    SpineRunReceipt,
    SpineStage,
)
from federation.cfbe_chat_hyperperformance_v1 import EffectClass
from federation.mission_ir import MissionIR
from federation.mission_outcome_value_court_v1 import MissionOutcomeState

SCHEMA = "FUSE-SPINE-HOST-BINDING-V1"
VERSION = "1.0.1"


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


class HostBindingLevel(str, Enum):
    ACTION_DISPATCH = "ACTION_DISPATCH"
    PROOF_FINALIZATION = "PROOF_FINALIZATION"
    VALUE_EVALUATION = "VALUE_EVALUATION"
    VALUE_FINALIZATION = "VALUE_FINALIZATION"


@dataclass(frozen=True, slots=True)
class SpineHostBindingReceipt:
    mission_id: str
    level: HostBindingLevel
    state: str
    action_id: str
    spine_run_digest: str
    qualifying_snapshot_digest: str
    reasons: tuple[str, ...]
    receipt_digest: str

    @property
    def admitted(self) -> bool:
        return self.state == "HOST_BINDING_ADMITTED"


class SpineHostBindingCourt:
    """Fail closed when host execution/finality is not backed by the spine."""

    @staticmethod
    def _expected_run_digest(mission: MissionIR, run: SpineRunReceipt) -> str:
        material = {
            "schema": "FUSE-AUTONOMIC-MISSION-SPINE-V1",
            "version": "1.0.0",
            "mission": mission.digest(),
            "snapshots": [x.snapshot_digest for x in run.snapshots],
            "admission": run.mission_admission.receipt_digest if run.mission_admission else "",
            "topology": run.topology.receipt_digest if run.topology else "",
            "actions": [x.receipt_digest for x in run.action_admissions],
            "closures": [x.receipt_digest for x in run.closures],
            "outcome": run.outcome.receipt_digest if run.outcome else "",
        }
        return _digest(material)

    def _base_reasons(self, mission: MissionIR, run: SpineRunReceipt) -> list[str]:
        reasons: list[str] = []
        if run.mission_id != mission.mission_id:
            reasons.append("SPINE_MISSION_ID_MISMATCH")
        if not run.snapshots:
            reasons.append("SPINE_SNAPSHOT_CHAIN_REQUIRED")
            return reasons
        if any(x.mission_id != mission.mission_id or x.mission_digest != mission.digest() for x in run.snapshots):
            reasons.append("SPINE_MISSION_DIGEST_MISMATCH")
        if not AutonomicMissionSpine.verify_chain(run.snapshots):
            reasons.append("SPINE_SNAPSHOT_CHAIN_INVALID")
        if run.receipt_digest != self._expected_run_digest(mission, run):
            reasons.append("SPINE_RUN_DIGEST_INVALID")
        return reasons

    @staticmethod
    def _snapshot(run: SpineRunReceipt, stage: SpineStage):
        return next((x for x in run.snapshots if x.stage is stage), None)

    def admit_action(
        self,
        mission: MissionIR,
        run: SpineRunReceipt,
        *,
        action_id: str,
        expected_effect_class: EffectClass,
        expected_target_scope: str,
        expected_provider: str = "",
    ) -> SpineHostBindingReceipt:
        mission.validate()
        reasons = self._base_reasons(mission, run)
        stage = self._snapshot(run, SpineStage.ACTIONS_ADMITTED)
        if stage is None:
            reasons.append("SPINE_ACTIONS_ADMITTED_STAGE_REQUIRED")
        action = next((x for x in run.action_admissions if x.action_id == action_id), None)
        if action is None:
            reasons.append("SPINE_EXACT_ACTION_ADMISSION_REQUIRED")
        else:
            if not action.admitted:
                reasons.append("SPINE_ACTION_NOT_ADMITTED")
            if action.effect_class is not expected_effect_class:
                reasons.append("SPINE_ACTION_EFFECT_CLASS_MISMATCH")
            if not action.target_scope:
                reasons.append("SPINE_ACTION_TARGET_NOT_BOUND")
            elif action.target_scope != expected_target_scope:
                reasons.append("SPINE_ACTION_TARGET_MISMATCH")
            if expected_provider:
                if not action.provider:
                    reasons.append("SPINE_ACTION_PROVIDER_NOT_BOUND")
                elif action.provider != expected_provider:
                    reasons.append("SPINE_ACTION_PROVIDER_MISMATCH")
        return self._receipt(
            mission, HostBindingLevel.ACTION_DISPATCH, action_id, run,
            stage.snapshot_digest if stage else "", reasons,
        )

    def admit_proof_finalization(self, mission: MissionIR, run: SpineRunReceipt) -> SpineHostBindingReceipt:
        mission.validate()
        reasons = self._base_reasons(mission, run)
        stage = self._snapshot(run, SpineStage.EXECUTION_CLOSED)
        if stage is None:
            reasons.append("SPINE_EXECUTION_CLOSED_STAGE_REQUIRED")
        if not run.closures:
            reasons.append("SPINE_EXECUTION_CLOSURES_REQUIRED")
        elif any(not item.effect_verified for item in run.closures):
            reasons.append("SPINE_ALL_EFFECTS_NOT_VERIFIED")
        return self._receipt(
            mission, HostBindingLevel.PROOF_FINALIZATION, "", run,
            stage.snapshot_digest if stage else "", reasons,
        )

    def admit_value_evaluation(self, mission: MissionIR, run: SpineRunReceipt) -> SpineHostBindingReceipt:
        mission.validate()
        reasons = self._base_reasons(mission, run)
        stage = self._snapshot(run, SpineStage.OUTCOME_PROVEN)
        value_stage = self._snapshot(run, SpineStage.VALUE_OBSERVED)
        if stage is None and value_stage is None:
            reasons.append("SPINE_OUTCOME_PROVEN_STAGE_REQUIRED")
        if run.outcome is None:
            reasons.append("SPINE_OUTCOME_RECEIPT_REQUIRED")
        elif run.outcome.state is MissionOutcomeState.HELD:
            reasons.append("SPINE_OUTCOME_HELD")
        qualifying = value_stage or stage
        return self._receipt(
            mission, HostBindingLevel.VALUE_EVALUATION, "", run,
            qualifying.snapshot_digest if qualifying else "", reasons,
        )

    def admit_value_finalization(self, mission: MissionIR, run: SpineRunReceipt) -> SpineHostBindingReceipt:
        mission.validate()
        reasons = self._base_reasons(mission, run)
        stage = self._snapshot(run, SpineStage.VALUE_OBSERVED)
        if stage is None:
            reasons.append("SPINE_VALUE_OBSERVED_STAGE_REQUIRED")
        if run.outcome is None or not run.outcome.value_observed:
            reasons.append("SPINE_VALUE_OBSERVATION_REQUIRED")
        return self._receipt(
            mission, HostBindingLevel.VALUE_FINALIZATION, "", run,
            stage.snapshot_digest if stage else "", reasons,
        )

    @staticmethod
    def _receipt(
        mission: MissionIR,
        level: HostBindingLevel,
        action_id: str,
        run: SpineRunReceipt,
        snapshot_digest: str,
        reasons: list[str],
    ) -> SpineHostBindingReceipt:
        state = "HOST_BINDING_ADMITTED" if not reasons else "HOST_BINDING_HELD"
        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "mission_id": mission.mission_id,
            "level": level.value,
            "state": state,
            "action_id": action_id,
            "spine_run_digest": run.receipt_digest,
            "snapshot": snapshot_digest,
            "reasons": tuple(reasons),
        }
        return SpineHostBindingReceipt(
            mission_id=mission.mission_id,
            level=level,
            state=state,
            action_id=action_id,
            spine_run_digest=run.receipt_digest,
            qualifying_snapshot_digest=snapshot_digest,
            reasons=tuple(reasons),
            receipt_digest=_digest(material),
        )


__all__ = [
    "SCHEMA", "VERSION", "HostBindingLevel", "SpineHostBindingReceipt", "SpineHostBindingCourt",
]
