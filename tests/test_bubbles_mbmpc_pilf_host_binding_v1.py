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
from federation.of50_ace_v1 import (
    Authority,
    ExecutionProof,
    FormationDecision,
    HORIZON_IDS,
    HorizonCell,
    OF50ACEKernel,
    OF50CycleRequest,
    ProofTier,
    ReuseBuildDecision,
    RouteCandidate,
    SwarmManifest,
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
    runtime.of50 = OF50ACEKernel()
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


def _of50_request(*, mission_id=MISSION_ID, complete=True):
    swarm = SwarmManifest(
        mission_id=mission_id,
        host_algorithm_id="BUBBLES-AUTONOMIC-FEDERATION-RUNTIME-V1",
        objective="verify mission finality",
        authority_ceiling=Authority.A1_INTERNAL.value,
        horizons=tuple(HorizonCell(item, "ASSESSED", f"proof:{item}") for item in HORIZON_IDS),
        semantic_readback_contract="action-specific readback required",
    )
    formation = FormationDecision(
        mission_id=mission_id,
        foundry_cycle_ref="formation:host-finality",
        route_candidates=(
            RouteCandidate("R1", "BUBBLES_RUNTIME", 1.0, "missing host receipt", "reuse incumbent Bubbles finality"),
            RouteCandidate("R2", "ALTERNATE_RUNTIME", 0.5, "duplicate finality plane", "reject duplicate runtime"),
        ),
        selected_route_id="R1",
        reuse_vs_build=ReuseBuildDecision.REUSE,
        selected_capability_hypothesis="incumbent Bubbles finality is sufficient",
        implementation_required=False,
    )
    return OF50CycleRequest(
        mission_id=mission_id,
        objective="verify mission finality",
        authority_ceiling=Authority.A1_INTERNAL.value,
        owner_protection_decision="CONTINUE_AUTOMATICALLY",
        owner_protection_violations=(),
        aarek_receipt_ref="aarek:host-finality",
        swarm_manifest=swarm,
        formation_decision=formation,
        alpha_omega_packet=None,
        execution_proof=ExecutionProof(
            True,
            ProofTier.SEMANTIC_READBACK,
            "exec:bubbles-finality",
            "semantic:bubbles-finality",
        ),
        objective_satisfied=complete,
        required_outcomes=("FINALITY",),
        proven_outcomes=("FINALITY",) if complete else (),
        oh50_rescan_ref="oh50:rescan",
        mission_recompiled=True,
        completion_requested=True,
    )


def test_owner_value_finalization_no_longer_equals_mission_finality():
    runtime = _runtime()
    result = runtime.finalize_owner_value(_mission(), spine_receipt=object())
    assert result["owner_value_finalized"] is True
    assert result["mission_value_finalized"] is False
    assert result["state"] == "OWNER_VALUE_FINALIZED_PENDING_PRODUCTION_LEARNING_CLOSURE"


def test_host_finality_requires_of50_and_mbmpc_pilf_closure_and_external_stage_evidence():
    runtime = _runtime()
    result = runtime.finalize_mission_completion(
        _mission(),
        spine_receipt=object(),
        production_contract=_contract(),
        current_p_stage=PStage.P16_VALUE_OBSERVED,
        satisfied_terminal_predicates=("TP-FINAL",),
        production_stage_evidence_refs=("provider:production-stage:P16",),
        of50_request=_of50_request(),
    )
    assert result["state"] == "MISSION_COMPLETION_VERIFIED"
    assert result["mission_value_finalized"] is True
    assert result["production_stage_evidence_refs"] == ["provider:production-stage:P16"]
    assert result["of50_receipt"]["completion_verified"] is True
    assert result["truth_boundary"]["of50_current_canonical_completion_required"] is True
    assert result["truth_boundary"]["of50_and_mbmpc_pilf_finality_are_conjunctive"] is True
    assert result["truth_boundary"]["production_stage_evidence_consumed_not_self_certified"] is True


def test_host_finality_fails_closed_without_of50_receipt():
    runtime = _runtime()
    result = runtime.finalize_mission_completion(
        _mission(),
        spine_receipt=object(),
        production_contract=_contract(),
        current_p_stage=PStage.P16_VALUE_OBSERVED,
        satisfied_terminal_predicates=("TP-FINAL",),
        production_stage_evidence_refs=("provider:production-stage:P16",),
    )
    assert result["state"] == "OF50_GATED"
    assert result["mission_value_finalized"] is False
    assert "OF50_CURRENT_CANONICAL_RECEIPT_REQUIRED" in result["reasons"]


def test_host_finality_rejects_of50_mission_identity_mismatch():
    runtime = _runtime()
    result = runtime.finalize_mission_completion(
        _mission(),
        spine_receipt=object(),
        production_contract=_contract(),
        current_p_stage=PStage.P16_VALUE_OBSERVED,
        satisfied_terminal_predicates=("TP-FINAL",),
        production_stage_evidence_refs=("provider:production-stage:P16",),
        of50_request=_of50_request(mission_id="OTHER-MISSION"),
    )
    assert result["state"] == "OF50_GATED"
    assert "OF50_MISSION_ID_MISMATCH" in result["reasons"]


def test_host_finality_rejects_incomplete_of50_completion_receipt():
    runtime = _runtime()
    result = runtime.finalize_mission_completion(
        _mission(),
        spine_receipt=object(),
        production_contract=_contract(),
        current_p_stage=PStage.P16_VALUE_OBSERVED,
        satisfied_terminal_predicates=("TP-FINAL",),
        production_stage_evidence_refs=("provider:production-stage:P16",),
        of50_request=_of50_request(complete=False),
    )
    assert result["state"] == "OF50_GATED"
    assert result["mission_value_finalized"] is False
    assert "OF50_CURRENT_CANONICAL_COMPLETION_NOT_VERIFIED" in result["reasons"]
    assert result["of50_receipt"]["completion_verified"] is False


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
        of50_request=_of50_request(),
        learning_evidence=(propagated,),
    )
    assert result["state"] == "PRODUCTION_LEARNING_GATED"
    assert result["mission_value_finalized"] is False
    assert result["of50_receipt"]["completion_verified"] is True
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
