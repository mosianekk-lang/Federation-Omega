from types import SimpleNamespace

from bubbles.autonomic_federation_runtime import (
    BubblesAutonomicFederationRuntime,
    WORK_VALUE,
)
from federation.fuse_mbmpc_pilf_closure_bridge_v1 import (
    LStage,
    LearningEvidence,
    MissionEvolutionClosureBridge,
    MissionProductionContract,
    PStage,
)
from formation_omega.mission_convergence import WorkStatus


MISSION_ID = "MISSION-HOST-BINDING-1"


class _BindingCourt:
    def __init__(self, *, admitted=True):
        self.admitted = admitted

    def admit_value_finalization(self, mission, spine_receipt):
        return SimpleNamespace(
            admitted=self.admitted,
            receipt_digest="spine:value-observed",
            reasons=() if self.admitted else ("VALUE_OBSERVED_REQUIRED",),
        )


class _Durable:
    def __init__(self, *, value_status=WorkStatus.VERIFIED):
        self.value_status = value_status
        self.updates = []

    def project(self, mission_id):
        return SimpleNamespace(
            work_items={
                WORK_VALUE: SimpleNamespace(status=self.value_status),
            }
        )

    def update_work_status(self, mission_id, work_id, status, *, result_refs=()):
        self.updates.append((mission_id, work_id, status, tuple(result_refs)))


class _Passport:
    def snapshot(self, mission_id):
        return SimpleNamespace(owner_value_proven=True)


def _runtime(*, admitted=True, value_status=WorkStatus.VERIFIED):
    runtime = object.__new__(BubblesAutonomicFederationRuntime)
    runtime.spine_binding = _BindingCourt(admitted=admitted)
    runtime.production_learning = MissionEvolutionClosureBridge()
    runtime.durable = _Durable(value_status=value_status)
    runtime.passport = _Passport()
    return runtime


def _mission():
    return SimpleNamespace(mission_id=MISSION_ID)


def _contract(**overrides):
    payload = dict(
        mission_id=MISSION_ID,
        required_p_stage=PStage.P16_VALUE_OBSERVED,
        required_terminal_predicates=("TP-FINAL",),
        continuous_learning_required=False,
    )
    payload.update(overrides)
    return MissionProductionContract(**payload)


def test_owner_value_finalization_no_longer_equals_mission_finality():
    runtime = _runtime()
    result = runtime.finalize_owner_value(_mission(), spine_receipt=object())
    assert result["owner_value_finalized"] is True
    assert result["mission_value_finalized"] is False
    assert result["state"] == "OWNER_VALUE_FINALIZED_PENDING_PRODUCTION_LEARNING_CLOSURE"


def test_host_finality_requires_mbmpc_pilf_closure_and_external_stage_evidence():
    runtime = _runtime()
    result = runtime.finalize_mission_completion(
        _mission(),
        spine_receipt=object(),
        production_contract=_contract(),
        current_p_stage=PStage.P16_VALUE_OBSERVED,
        satisfied_terminal_predicates=("TP-FINAL",),
        production_stage_evidence_refs=("provider:production-stage:P16",),
    )
    assert result["state"] == "MISSION_COMPLETION_VERIFIED"
    assert result["mission_value_finalized"] is True
    assert result["production_stage_evidence_refs"] == ["provider:production-stage:P16"]
    assert result["truth_boundary"]["production_stage_evidence_consumed_not_self_certified"] is True


def test_continuous_learning_propagation_without_receiver_adoption_blocks_finality():
    runtime = _runtime()
    propagated = LearningEvidence(
        learning_id="LRN-1",
        stage=LStage.L7_SOURCE_OR_CONTROL_ADMITTED,
        evidence_refs=("control:pilf",),
        propagated=True,
    )
    result = runtime.finalize_mission_completion(
        _mission(),
        spine_receipt=object(),
        production_contract=_contract(
            required_p_stage=PStage.P17_CONTINUOUS_IMPROVEMENT_ACTIVE,
            continuous_learning_required=True,
        ),
        current_p_stage=PStage.P17_CONTINUOUS_IMPROVEMENT_ACTIVE,
        satisfied_terminal_predicates=("TP-FINAL",),
        production_stage_evidence_refs=("provider:production-stage:P17",),
        learning_evidence=(propagated,),
    )
    assert result["state"] == "PRODUCTION_LEARNING_GATED"
    assert result["mission_value_finalized"] is False
    assert "PROPAGATION_NOT_ADOPTION" in result["production_learning_receipt"]["learning_debt"]


def test_host_finality_rejects_missing_production_stage_evidence():
    runtime = _runtime()
    result = runtime.finalize_mission_completion(
        _mission(),
        spine_receipt=object(),
        production_contract=_contract(),
        current_p_stage=PStage.P16_VALUE_OBSERVED,
        satisfied_terminal_predicates=("TP-FINAL",),
        production_stage_evidence_refs=(),
    )
    assert result["state"] == "PRODUCTION_LEARNING_GATED"
    assert "PRODUCTION_STAGE_EVIDENCE_REQUIRED" in result["reasons"]


def test_host_finality_rejects_wrong_mission_contract():
    runtime = _runtime()
    wrong = MissionProductionContract(
        mission_id="OTHER-MISSION",
        required_p_stage=PStage.P16_VALUE_OBSERVED,
        required_terminal_predicates=("TP-FINAL",),
    )
    result = runtime.finalize_mission_completion(
        _mission(),
        spine_receipt=object(),
        production_contract=wrong,
        current_p_stage=PStage.P16_VALUE_OBSERVED,
        satisfied_terminal_predicates=("TP-FINAL",),
        production_stage_evidence_refs=("provider:production-stage:P16",),
    )
    assert result["state"] == "PRODUCTION_LEARNING_GATED"
    assert "MISSION_PRODUCTION_CONTRACT_ID_MISMATCH" in result["reasons"]


def test_host_finality_requires_prior_owner_value_finalization():
    runtime = _runtime(value_status=WorkStatus.READY)
    result = runtime.finalize_mission_completion(
        _mission(),
        spine_receipt=object(),
        production_contract=_contract(),
        current_p_stage=PStage.P16_VALUE_OBSERVED,
        satisfied_terminal_predicates=("TP-FINAL",),
        production_stage_evidence_refs=("provider:production-stage:P16",),
    )
    assert result["state"] == "PRODUCTION_LEARNING_GATED"
    assert "OWNER_VALUE_FINALIZATION_REQUIRED" in result["reasons"]


def test_host_finality_remains_spine_gated():
    runtime = _runtime(admitted=False)
    result = runtime.finalize_mission_completion(
        _mission(),
        spine_receipt=object(),
        production_contract=_contract(),
        current_p_stage=PStage.P16_VALUE_OBSERVED,
        satisfied_terminal_predicates=("TP-FINAL",),
        production_stage_evidence_refs=("provider:production-stage:P16",),
    )
    assert result["state"] == "SPINE_GATED"
    assert result["mission_value_finalized"] is False
