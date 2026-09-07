import pytest
from federation.fuse_mbmpc_pilf_closure_bridge_v1 import (
    LStage, PStage, LearningEvidence, MissionEvolutionClosureBridge, MissionProductionContract
)


def contract(**kw):
    base = dict(
        mission_id="MISSION-1",
        required_p_stage=PStage.P15_PRODUCTION_PROMOTED,
        required_terminal_predicates=("TP-1", "TP-2"),
    )
    base.update(kw)
    return MissionProductionContract(**base)


def test_source_admitted_is_not_production():
    r = MissionEvolutionClosureBridge().evaluate(
        contract=contract(), current_p_stage=PStage.P9_SOURCE_ADMITTED,
        satisfied_terminal_predicates=("TP-1", "TP-2"),
    )
    assert not r.done_allowed
    assert r.next_action == "ADVANCE_PRODUCTION_STAGE"


def test_terminal_debt_blocks_complete_even_at_required_stage():
    r = MissionEvolutionClosureBridge().evaluate(
        contract=contract(), current_p_stage=PStage.P15_PRODUCTION_PROMOTED,
        satisfied_terminal_predicates=("TP-1",),
    )
    assert not r.done_allowed
    assert r.terminal_debt == ("TP-2",)


def test_continuous_learning_requires_adoption_stage():
    c = contract(continuous_learning_required=True)
    e = LearningEvidence("L1", LStage.L7_SOURCE_OR_CONTROL_ADMITTED, ("ref",), propagated=True)
    r = MissionEvolutionClosureBridge().evaluate(
        contract=c, current_p_stage=PStage.P15_PRODUCTION_PROMOTED,
        satisfied_terminal_predicates=("TP-1", "TP-2"), learning_evidence=(e,)
    )
    assert not r.done_allowed
    assert "PROPAGATION_NOT_ADOPTION" in r.learning_debt


def test_receiver_adoption_can_satisfy_default_learning_floor():
    c = contract(continuous_learning_required=True)
    e = LearningEvidence("L1", LStage.L9_BEHAVIOUR_ADOPTED, ("ref",), receiver_id="receiver")
    r = MissionEvolutionClosureBridge().evaluate(
        contract=c, current_p_stage=PStage.P15_PRODUCTION_PROMOTED,
        satisfied_terminal_predicates=("TP-1", "TP-2"), learning_evidence=(e,)
    )
    assert r.done_allowed


def test_owner_correction_requires_prevention_binding():
    e = LearningEvidence(
        "OWNER-1", LStage.L4_GENERALIZED_RULE, ("ref",), owner_correction=True,
        machine_detectable=True, prevention_bound=False,
    )
    r = MissionEvolutionClosureBridge().evaluate(
        contract=contract(), current_p_stage=PStage.P15_PRODUCTION_PROMOTED,
        satisfied_terminal_predicates=("TP-1", "TP-2"), learning_evidence=(e,)
    )
    assert not r.done_allowed
    assert any(x.startswith("OWNER_CORRECTION_PREVENTION_REQUIRED") for x in r.learning_debt)


def test_owner_correction_prevention_closes_that_debt():
    e = LearningEvidence(
        "OWNER-1", LStage.L4_GENERALIZED_RULE, ("ref",), owner_correction=True,
        machine_detectable=True, prevention_bound=True,
    )
    r = MissionEvolutionClosureBridge().evaluate(
        contract=contract(), current_p_stage=PStage.P15_PRODUCTION_PROMOTED,
        satisfied_terminal_predicates=("TP-1", "TP-2"), learning_evidence=(e,)
    )
    assert r.done_allowed


def test_failure_without_fingerprint_fails_closed():
    e = LearningEvidence("F1", LStage.L1_EVIDENCE_BOUND, ("ref",), failure_event=True)
    with pytest.raises(ValueError, match="FAILURE_WITHOUT_FINGERPRINT"):
        MissionEvolutionClosureBridge().evaluate(
            contract=contract(), current_p_stage=PStage.P15_PRODUCTION_PROMOTED,
            satisfied_terminal_predicates=("TP-1", "TP-2"), learning_evidence=(e,)
        )


def test_recurring_failure_requires_prevention():
    e = LearningEvidence(
        "F1", LStage.L3_FALSIFIED_OR_VALIDATED, ("ref",), failure_event=True,
        fingerprint="same", recurrence_count=2,
    )
    r = MissionEvolutionClosureBridge().evaluate(
        contract=contract(), current_p_stage=PStage.P15_PRODUCTION_PROMOTED,
        satisfied_terminal_predicates=("TP-1", "TP-2"), learning_evidence=(e,)
    )
    assert any(x.startswith("RECURRING_FAILURE_PREVENTION_REQUIRED") for x in r.learning_debt)


def test_semantic_dedup_keeps_strongest_learning():
    a = LearningEvidence("A", LStage.L1_EVIDENCE_BOUND, ("r1",), fingerprint="fp", generalized_rule="rule")
    b = LearningEvidence("B", LStage.L4_GENERALIZED_RULE, ("r1", "r2"), fingerprint="fp", generalized_rule="rule")
    r = MissionEvolutionClosureBridge().evaluate(
        contract=contract(), current_p_stage=PStage.P15_PRODUCTION_PROMOTED,
        satisfied_terminal_predicates=("TP-1", "TP-2"), learning_evidence=(a,b)
    )
    assert r.deduplicated_learning_count == 1


def test_learning_l10_requires_value_flag():
    e = LearningEvidence("L", LStage.L10_VALUE_VERIFIED, ("ref",), receiver_id="r", value_verified=False)
    with pytest.raises(ValueError, match="VALUE_FLAG_REQUIRED_AT_L10_PLUS"):
        MissionEvolutionClosureBridge().evaluate(
            contract=contract(), current_p_stage=PStage.P15_PRODUCTION_PROMOTED,
            satisfied_terminal_predicates=("TP-1", "TP-2"), learning_evidence=(e,)
        )


def test_continuous_learning_contract_cannot_set_weak_floor():
    c = contract(continuous_learning_required=True, required_learning_stage=LStage.L4_GENERALIZED_RULE)
    with pytest.raises(ValueError, match="CONTINUOUS_LEARNING_REQUIRES_RECEIVER_BOUND_OR_STRONGER"):
        MissionEvolutionClosureBridge().evaluate(
            contract=c, current_p_stage=PStage.P15_PRODUCTION_PROMOTED,
            satisfied_terminal_predicates=("TP-1", "TP-2")
        )


def test_receipt_digest_is_deterministic():
    bridge = MissionEvolutionClosureBridge()
    kwargs = dict(
        contract=contract(), current_p_stage=PStage.P15_PRODUCTION_PROMOTED,
        satisfied_terminal_predicates=("TP-1", "TP-2")
    )
    assert bridge.evaluate(**kwargs).receipt_digest == bridge.evaluate(**kwargs).receipt_digest
