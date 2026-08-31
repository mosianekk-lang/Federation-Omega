from __future__ import annotations

import json
from pathlib import Path

import pytest

from federation.bubbles_autopilot_policy import (
    CFBECapabilityCandidate,
    HIGH_CONSEQUENCE,
    NO_EFFECT,
    REVERSIBLE_EXTERNAL,
    REVERSIBLE_INTERNAL,
    AutopilotStep,
    cfbe_rank,
    decide_autopilot,
)


def test_cfbe_rank_uses_canonical_formula() -> None:
    candidate = CFBECapabilityCandidate("C1", 5, 5, 5, 5, 1)
    assert cfbe_rank(candidate) == 625.0


def test_cfbe_rank_rejects_zero_effort() -> None:
    with pytest.raises(ValueError, match="CFBE_EXPECTED_EFFORT_POSITIVE_REQUIRED"):
        cfbe_rank(CFBECapabilityCandidate("C1", 5, 5, 5, 5, 0))


@pytest.mark.parametrize("effect_class", [NO_EFFECT, REVERSIBLE_INTERNAL])
def test_safe_work_continues_without_owner(effect_class: str) -> None:
    decision = decide_autopilot(AutopilotStep("safe", effect_class))
    assert decision.state == "CONTINUE_AUTONOMOUSLY"
    assert decision.continue_without_owner is True
    assert decision.owner_interrupt_required is False


def test_blocked_lane_with_alternate_reroutes_without_owner() -> None:
    decision = decide_autopilot(
        AutopilotStep(
            "blocked",
            REVERSIBLE_INTERNAL,
            blocked=True,
            alternate_route_available=True,
        )
    )
    assert decision.state == "ISOLATE_BLOCKED_LANE_AND_REROUTE"
    assert decision.continue_without_owner is True
    assert decision.owner_interrupt_required is False


def test_blocked_lane_without_route_escalates() -> None:
    decision = decide_autopilot(
        AutopilotStep("blocked", REVERSIBLE_INTERNAL, blocked=True)
    )
    assert decision.state == "ESCALATE_OWNER_NO_EXECUTABLE_ROUTE"
    assert decision.owner_interrupt_required is True


def test_reversible_external_requires_authority_and_readback() -> None:
    decision = decide_autopilot(
        AutopilotStep(
            "external",
            REVERSIBLE_EXTERNAL,
            authority_proven=True,
            provider_readback_available=True,
            proof_refs=("provider:receipt",),
        )
    )
    assert decision.state == "CONTINUE_EXTERNAL_WITH_READBACK"
    assert decision.continue_without_owner is True
    assert decision.proof_refs == ("provider:receipt",)


@pytest.mark.parametrize(
    "authority,readback",
    [(False, False), (False, True), (True, False)],
)
def test_reversible_external_missing_gate_escalates(
    authority: bool, readback: bool
) -> None:
    decision = decide_autopilot(
        AutopilotStep(
            "external",
            REVERSIBLE_EXTERNAL,
            authority_proven=authority,
            provider_readback_available=readback,
        )
    )
    assert decision.state == "ESCALATE_OWNER_EXTERNAL_GATE"
    assert decision.owner_interrupt_required is True


def test_high_consequence_always_escalates() -> None:
    decision = decide_autopilot(
        AutopilotStep(
            "danger",
            HIGH_CONSEQUENCE,
            authority_proven=True,
            provider_readback_available=True,
        )
    )
    assert decision.state == "ESCALATE_OWNER_HIGH_CONSEQUENCE"
    assert decision.continue_without_owner is False


def test_irreducible_owner_choice_escalates() -> None:
    decision = decide_autopilot(
        AutopilotStep(
            "creative-choice",
            NO_EFFECT,
            owner_choice_required=True,
        )
    )
    assert decision.state == "ESCALATE_OWNER_IRREDUCIBLE_CHOICE"


def test_alternate_route_requires_blocked_step() -> None:
    with pytest.raises(
        ValueError, match="AUTOPILOT_ALTERNATE_ROUTE_REQUIRES_BLOCKED_STEP"
    ):
        decide_autopilot(
            AutopilotStep(
                "bad",
                REVERSIBLE_INTERNAL,
                alternate_route_available=True,
            )
        )


def test_benchmark_files_have_exactly_150_unique_capabilities() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = [
        root / "benchmarking/cfbe_omega/bubbles_digital_twin_high_performance_50_v1.json",
        root / "benchmarking/cfbe_omega/bubbles_digital_twin_ai_autopilot_50_v1.json",
        root / "benchmarking/cfbe_omega/bubbles_digital_twin_agi_oriented_50_v1.json",
    ]
    all_rows = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["count"] == 50
        assert len(payload["capabilities"]) == 50
        all_rows.extend(payload["capabilities"])
    ids = [row["id"] for row in all_rows]
    names = [row["capability"] for row in all_rows]
    assert len(all_rows) == 150
    assert len(ids) == len(set(ids))
    assert len(names) == len(set(names))
