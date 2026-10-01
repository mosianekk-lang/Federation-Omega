"""FUSE No-False-Finality guard v1.

Owner-facing presentation is a safety-critical projection of mission truth.
A progress checkpoint must never be rendered like a completed mission, and
packet exhaustion must never be treated as terminal acceptance by itself.

This module is intentionally small and provider-neutral. It creates no runtime,
authority, scheduler, memory root, or proof plane.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class FalseFinalityError(RuntimeError):
    """Raised when outward presentation would overstate mission finality."""


class MissionPresentationState(StrEnum):
    ACTIVE_BUILD = "ACTIVE_BUILD"
    ACTIVE_RESUME_REQUIRED = "ACTIVE_RESUME_REQUIRED"
    OWNER_DECISION_REQUIRED = "OWNER_DECISION_REQUIRED"
    TERMINAL_VERIFIED = "TERMINAL_VERIFIED"


SUCCESS_TERMINAL_STATES = frozenset({
    "COMPLETE_VERIFIED",
    "PRODUCTION_VERIFIED",
    "COMMERCIAL_READY_VERIFIED",
})

NON_SUCCESS_TERMINAL_STATES = frozenset({
    "OBJECTIVE_EXHAUSTED",
    "IRREDUCIBLE_OWNER_DECISION",
    "IRREDUCIBLE_EXTERNAL_BOUNDARY",
    "SAFETY_OR_AUTHORITY_BOUNDARY",
})


@dataclass(frozen=True, slots=True)
class TerminalAcceptance:
    """Explicit terminal-court output for non-commercial missions."""

    verified: bool
    state: str
    proof_ref: str = ""
    gaps: tuple[str, ...] = ()

    def validate_for_target(self, target_state: str) -> "TerminalAcceptance":
        if not self.verified:
            return self
        if self.state != target_state:
            raise FalseFinalityError(
                f"TERMINAL_ACCEPTANCE_TARGET_MISMATCH:{self.state}!={target_state}"
            )
        if self.state not in SUCCESS_TERMINAL_STATES:
            raise FalseFinalityError(
                f"TERMINAL_ACCEPTANCE_STATE_NOT_SUCCESS:{self.state}"
            )
        if not self.proof_ref.strip():
            raise FalseFinalityError("TERMINAL_ACCEPTANCE_PROOF_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class FinalityPresentationDecision:
    state: MissionPresentationState
    terminal_reached: bool
    completion_style_allowed: bool
    mission_must_continue: bool
    banner: str
    terminal_line: str
    next_line: str


class FinalityPresentationGuard:
    """Fail closed when mission presentation outruns terminal evidence."""

    def classify(
        self,
        *,
        output_class: str,
        terminal_state: str = "",
        terminal_proof_ref: str = "",
        next_ready_packets: Iterable[str] = (),
        maturity_gaps: Iterable[str] = (),
        recompile_required: bool = False,
    ) -> FinalityPresentationDecision:
        output_class = str(output_class)
        terminal_state = str(terminal_state or "")
        terminal_proof_ref = str(terminal_proof_ref or "").strip()
        ready = tuple(str(x) for x in next_ready_packets if str(x))
        gaps = tuple(str(x) for x in maturity_gaps if str(x))

        if output_class == "TERMINAL_REPORT":
            if terminal_state not in SUCCESS_TERMINAL_STATES:
                raise FalseFinalityError(
                    f"TERMINAL_REPORT_REQUIRES_SUCCESS_STATE:{terminal_state or 'NONE'}"
                )
            if not terminal_proof_ref:
                raise FalseFinalityError("TERMINAL_REPORT_REQUIRES_PROOF_REF")
            return FinalityPresentationDecision(
                MissionPresentationState.TERMINAL_VERIFIED,
                True,
                True,
                False,
                f"STATE: {terminal_state}",
                "TERMINAL: VERIFIED",
                "NEXT: no automatic continuation; terminal predicate is proven",
            )

        if terminal_state in SUCCESS_TERMINAL_STATES:
            raise FalseFinalityError(
                "SUCCESS_TERMINAL_STATE_CANNOT_BE_RENDERED_AS_NON_TERMINAL_OUTPUT"
            )

        if output_class == "OWNER_DECISION":
            return FinalityPresentationDecision(
                MissionPresentationState.OWNER_DECISION_REQUIRED,
                False,
                False,
                True,
                "STATE: OWNER_DECISION_REQUIRED",
                "TERMINAL: NOT REACHED",
                "NEXT: resume immediately after the genuinely owner-reserved decision",
            )

        if output_class == "RESUME_CAPSULE":
            return FinalityPresentationDecision(
                MissionPresentationState.ACTIVE_RESUME_REQUIRED,
                False,
                False,
                True,
                "STATE: ACTIVE_RESUME_REQUIRED",
                "TERMINAL: NOT REACHED",
                "NEXT: consume the verified checkpoint and continue the mission",
            )

        if output_class != "PROGRESS_UPDATE":
            raise FalseFinalityError(f"UNKNOWN_OUTPUT_CLASS:{output_class}")

        next_hint = ""
        if ready:
            next_hint = "NEXT: execute " + ", ".join(ready[:4])
        elif gaps:
            next_hint = "NEXT: close " + ", ".join(gaps[:4])
        elif recompile_required:
            next_hint = "NEXT: recompile unresolved terminal predicates and continue"
        else:
            next_hint = "NEXT: continue the highest-value unresolved mission predicate"

        return FinalityPresentationDecision(
            MissionPresentationState.ACTIVE_BUILD,
            False,
            False,
            True,
            "STATE: ACTIVE_BUILD",
            "TERMINAL: NOT REACHED",
            next_hint,
        )


__all__ = [
    "FalseFinalityError",
    "FinalityPresentationDecision",
    "FinalityPresentationGuard",
    "MissionPresentationState",
    "NON_SUCCESS_TERMINAL_STATES",
    "SUCCESS_TERMINAL_STATES",
    "TerminalAcceptance",
]
