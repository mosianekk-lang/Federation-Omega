from datetime import datetime, timezone

import pytest

from kaio_fluid.abstraction import ProblemAbstractionEngine
from kaio_fluid.causal import CausalClaim, CausalTimeLockGuard, TimedFact
from kaio_fluid.lineage import LineageGraph, LineageNode
from kaio_fluid.models import ProblemContext
from kaio_fluid.promotion import PromotionGovernor, PromotionReceipt


def test_lineage_traces_sources_and_propagates_change():
    graph = LineageGraph()
    graph.add_node(LineageNode("E1", "EVIDENCE", "VERIFIED"))
    graph.add_node(LineageNode("P1", "PROPOSITION", "SUPPORTED"))
    graph.add_node(LineageNode("D1", "DECISION", "INTERNAL"))
    graph.link("E1", "P1")
    graph.link("P1", "D1")
    assert graph.source_roots("D1") == ("E1",)
    assert graph.affected_descendants("E1") == ("D1", "P1")


def test_lineage_rejects_cycle():
    graph = LineageGraph()
    graph.add_node(LineageNode("A", "PROPOSITION", "SUPPORTED"))
    graph.add_node(LineageNode("B", "PROPOSITION", "SUPPORTED"))
    graph.link("A", "B")
    with pytest.raises(ValueError):
        graph.link("B", "A")


def test_abstraction_is_deduplicated_and_explicit():
    ctx = ProblemContext(
        objective="resolve decision",
        stakes=0.7,
        uncertainty=0.6,
        novelty=0.5,
        irreversibility=0.3,
        constraints=("missing record", "missing record"),
        assumptions=("record is necessary",),
    )
    model = ProblemAbstractionEngine().abstract(
        ctx,
        actors=("A", "A", "B"),
        dependencies=("D1",),
        unknowns=("U1",),
    )
    assert model.actors == ("A", "B")
    assert model.constraints == ("missing record",)


def test_time_lock_blocks_hindsight_and_missing_mechanism():
    guard = CausalTimeLockGuard()
    cause = TimedFact(
        id="C",
        known_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        event_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        proof_state="VERIFIED",
    )
    outcome = TimedFact(
        id="O",
        known_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
        event_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        proof_state="VERIFIED",
    )
    decision = datetime(2026, 1, 10, tzinfo=timezone.utc)
    assert guard.hindsight_violation(cause, decision)
    assert not guard.causal_claim_allowed(
        CausalClaim("C", "O", None), cause=cause, outcome=outcome
    )


def test_promotion_governor_blocks_state_jump_and_unproven_runtime():
    governor = PromotionGovernor()
    ok, failures = governor.validate(
        PromotionReceipt(
            capability_id="KAIO-FI",
            from_state="DESIGN_ONLY",
            to_state="OPERATIONAL_VERIFIED",
            deterministic_tests=True,
            rollback_proven=False,
            target_readback=False,
            health_check=False,
            persistence_check=False,
            provider_receipt=False,
        )
    )
    assert not ok
    assert "STATE_JUMP_NOT_ALLOWED" in failures


def test_promotion_governor_accepts_one_step_deterministic_promotion():
    ok, failures = PromotionGovernor().validate(
        PromotionReceipt(
            capability_id="KAIO-FI",
            from_state="DESIGN_ONLY",
            to_state="DETERMINISTIC_TESTED",
            deterministic_tests=True,
            rollback_proven=False,
            target_readback=False,
            health_check=False,
            persistence_check=False,
        )
    )
    assert ok
    assert failures == ()
