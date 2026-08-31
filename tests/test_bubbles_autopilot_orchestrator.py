from __future__ import annotations

from bubbles.adaptive_organisation import MissionManifest, WorkCandidate
from federation.bubbles_autopilot_orchestrator import (
    AutopilotWorkEnvelope,
    BubblesAutopilotOrchestrator,
)
from federation.bubbles_autopilot_policy import (
    HIGH_CONSEQUENCE,
    NO_EFFECT,
    REVERSIBLE_EXTERNAL,
    REVERSIBLE_INTERNAL,
)


def _candidate(
    work_id: str,
    *,
    proof_gap: str,
    disciplines: tuple[str, ...],
    value: float,
) -> WorkCandidate:
    return WorkCandidate(
        work_id=work_id,
        objective=f"objective {work_id}",
        proof_gap=proof_gap,
        action_type="EXTEND_EXISTING",
        target="bubbles",
        required_disciplines=disciplines,
        value=value,
        proof_gain=value,
        career_or_product_leverage=1.0,
        unblock_impact=1.0,
        cost=1.0,
        risk=1.0,
        dependency_load=1.0,
        executable=True,
    )


def _manifest() -> MissionManifest:
    return MissionManifest(mission_id="mission-autopilot", objective="finish safely")


def test_external_gate_does_not_freeze_lower_ranked_safe_work() -> None:
    external = _candidate(
        "external",
        proof_gap="provider_readback",
        disciplines=("provider", "readback"),
        value=10.0,
    )
    safe = _candidate(
        "safe",
        proof_gap="research",
        disciplines=("research",),
        value=5.0,
    )
    decision = BubblesAutopilotOrchestrator().choose_safe_next(
        (
            AutopilotWorkEnvelope(
                external,
                REVERSIBLE_EXTERNAL,
                authority_proven=False,
                provider_readback_available=False,
            ),
            AutopilotWorkEnvelope(safe, NO_EFFECT),
        ),
        manifest=_manifest(),
    )
    assert decision.state == "SAFE_WORK_SELECTED"
    assert decision.selected_work_id == "safe"
    assert decision.continue_without_owner is True
    assert decision.owner_interrupt_required is False
    assert decision.held_lanes[0].work_id == "external"
    assert decision.held_lanes[0].state == "ESCALATE_OWNER_EXTERNAL_GATE"
    assert "Scout" in decision.squad_members


def test_high_consequence_lane_is_held_while_safe_internal_work_continues() -> None:
    dangerous = _candidate(
        "dangerous",
        proof_gap="provider_execution",
        disciplines=("provider", "security"),
        value=10.0,
    )
    internal = _candidate(
        "internal",
        proof_gap="tests",
        disciplines=("testing",),
        value=4.0,
    )
    decision = BubblesAutopilotOrchestrator().choose_safe_next(
        (
            AutopilotWorkEnvelope(dangerous, HIGH_CONSEQUENCE),
            AutopilotWorkEnvelope(internal, REVERSIBLE_INTERNAL),
        ),
        manifest=_manifest(),
    )
    assert decision.selected_work_id == "internal"
    assert decision.owner_interrupt_required is False
    assert decision.held_lanes[0].state == "ESCALATE_OWNER_HIGH_CONSEQUENCE"


def test_blocked_lane_with_alternate_isolated_then_next_safe_lane_runs() -> None:
    blocked = _candidate(
        "blocked",
        proof_gap="integration",
        disciplines=("integration",),
        value=10.0,
    )
    safe = _candidate(
        "safe",
        proof_gap="tests",
        disciplines=("testing",),
        value=3.0,
    )
    decision = BubblesAutopilotOrchestrator().choose_safe_next(
        (
            AutopilotWorkEnvelope(
                blocked,
                REVERSIBLE_INTERNAL,
                blocked=True,
                alternate_route_available=True,
            ),
            AutopilotWorkEnvelope(safe, NO_EFFECT),
        ),
        manifest=_manifest(),
    )
    assert decision.selected_work_id == "safe"
    assert decision.held_lanes[0].state == "ISOLATE_BLOCKED_LANE_AND_REROUTE"
    assert decision.owner_interrupt_required is False


def test_owner_gate_surfaces_only_when_no_safe_lane_remains() -> None:
    external = _candidate(
        "external",
        proof_gap="provider_readback",
        disciplines=("provider", "readback"),
        value=10.0,
    )
    decision = BubblesAutopilotOrchestrator().choose_safe_next(
        (
            AutopilotWorkEnvelope(
                external,
                REVERSIBLE_EXTERNAL,
                authority_proven=False,
                provider_readback_available=False,
            ),
        ),
        manifest=_manifest(),
    )
    assert decision.state == "OWNER_GATE_REQUIRED"
    assert decision.selected_work_id == ""
    assert decision.owner_interrupt_required is True


def test_proven_external_route_can_be_selected_with_specialist_squad() -> None:
    external = _candidate(
        "external",
        proof_gap="provider_readback",
        disciplines=("provider", "readback"),
        value=10.0,
    )
    decision = BubblesAutopilotOrchestrator().choose_safe_next(
        (
            AutopilotWorkEnvelope(
                external,
                REVERSIBLE_EXTERNAL,
                authority_proven=True,
                provider_readback_available=True,
                proof_refs=("provider:authority", "provider:readback"),
            ),
        ),
        manifest=_manifest(),
    )
    assert decision.state == "SAFE_WORK_SELECTED"
    assert decision.selected_work_id == "external"
    assert decision.autopilot_state == "CONTINUE_EXTERNAL_WITH_READBACK"
    assert "Bubbles" in decision.squad_members
    assert "Sparks" in decision.squad_members
    assert "Ledger" in decision.squad_members


def test_duplicate_candidate_is_not_reselected() -> None:
    candidate = _candidate(
        "dup",
        proof_gap="research",
        disciplines=("research",),
        value=5.0,
    )
    manifest = _manifest()
    manifest.completed_fingerprints.append(candidate.fingerprint)
    decision = BubblesAutopilotOrchestrator().choose_safe_next(
        (AutopilotWorkEnvelope(candidate, NO_EFFECT),),
        manifest=manifest,
    )
    assert decision.state == "NO_EXECUTABLE_WORK"
    assert decision.owner_interrupt_required is False


def test_work_ids_must_be_unique() -> None:
    candidate = _candidate(
        "same",
        proof_gap="research",
        disciplines=("research",),
        value=2.0,
    )
    try:
        BubblesAutopilotOrchestrator().choose_safe_next(
            (
                AutopilotWorkEnvelope(candidate, NO_EFFECT),
                AutopilotWorkEnvelope(candidate, NO_EFFECT),
            ),
            manifest=_manifest(),
        )
    except ValueError as exc:
        assert str(exc) == "AUTOPILOT_WORK_IDS_MUST_BE_UNIQUE"
    else:
        raise AssertionError("duplicate work IDs must fail closed")
