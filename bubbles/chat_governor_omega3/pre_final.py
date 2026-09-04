"""Deterministic PRE_FINAL_RESPONSE gate for ChatGov.

This module closes an enforcement-placement gap: existing ACME mission-completion,
RealityGuard claim-integrity, Human-First Outcome-First, and ChatBridge completion
witness rules are useful only when the response emitter actually consults them.

The gate is provider-neutral and effect-free. It does not modify native ChatGPT or
provider serving infrastructure. Hosts that route through this middleware can use
``ChatGovPreFinalInterlock.before_final_response`` as a Stop/termination hook.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Any, Iterable, Mapping, Optional

from .state import DurableState


MATERIAL_MATURITY_RE = re.compile(
    r"\b(implemented|operational|live|deployed|fixed|resolved|complete|completed|"
    r"connected|integrated|verified|active|universal|universally|fully|production)\b",
    re.IGNORECASE,
)


class TerminalState(str, Enum):
    ACTIVE = "ACTIVE"
    VERIFIED_COMPLETE = "VERIFIED_COMPLETE"
    OWNER_DECISION_REQUIRED = "OWNER_DECISION_REQUIRED"
    BLOCKED_IRREDUCIBLY = "BLOCKED_IRREDUCIBLY"
    LEGAL_OR_SAFETY_PROHIBITION = "LEGAL_OR_SAFETY_PROHIBITION"
    ACTIVE_TURN_BOUNDARY = "ACTIVE_TURN_BOUNDARY"


@dataclass(frozen=True)
class GapState:
    """One material unfinished gap and whether the system can still act on it."""

    gap_id: str
    summary: str
    material: bool = True
    route_known: bool = False
    safe: bool = False
    authorized: bool = False
    available: bool = False
    recovery_exhausted: bool = False
    owner_only: bool = False

    @property
    def actionable(self) -> bool:
        return bool(
            self.material
            and self.route_known
            and self.safe
            and self.authorized
            and self.available
            and not self.recovery_exhausted
            and not self.owner_only
        )


@dataclass(frozen=True)
class ClaimScanSnapshot:
    """Normalized adapter for an existing RealityGuard/claim-proof scan.

    ChatGov does not duplicate RealityGuard. It consumes the verdict and proven
    lifecycle boundary that RealityGuard or an equivalent admitted claim guard
    already established.
    """

    subject: str
    verdict: str
    claimed_state: str
    proven_state: str
    state_gap: int = 0
    safe_statement: str = ""
    evidence_refs: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ClaimScanSnapshot":
        return cls(
            subject=str(raw.get("subject", raw.get("claim", "unspecified"))),
            verdict=str(raw.get("verdict", "")),
            claimed_state=str(raw.get("claimed_state", "")),
            proven_state=str(raw.get("proven_state", "")),
            state_gap=int(raw.get("state_gap", 0) or 0),
            safe_statement=str(raw.get("safe_statement", "")),
            evidence_refs=tuple(
                map(
                    str,
                    raw.get("evidence_refs", raw.get("evidence_used", ())) or (),
                )
            ),
        )

    @property
    def blocks_final(self) -> bool:
        return self.verdict in {"BLOCK_FALSE_REALITY", "BLOCK_COMPLETION"} or self.state_gap > 0

    @property
    def requires_rewrite(self) -> bool:
        return self.verdict == "REWRITE_REQUIRED"


@dataclass(frozen=True)
class ControlBinding:
    """Coverage contract for a mandatory rule and its enforcement points."""

    control_id: str
    mandatory: bool
    required_points: tuple[str, ...]
    bound_points: tuple[str, ...]
    regression_test_passed: bool = False

    @property
    def missing_points(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.required_points) - set(self.bound_points)))

    @property
    def healthy(self) -> bool:
        return (not self.mandatory) or (
            not self.missing_points and self.regression_test_passed
        )


@dataclass(frozen=True)
class MissionClosureState:
    mission_id: str
    objective: str
    terminal_state: TerminalState = TerminalState.ACTIVE
    objective_satisfied: bool = False
    gaps: tuple[GapState, ...] = ()
    owner_decision_request: str = ""
    irreducible_blocker: str = ""
    exhaustion_evidence_ref: str = ""
    resumable_checkpoint_ref: str = ""
    currently_executable_work: bool = False
    outcome_first_continue_recovery: bool = False


@dataclass(frozen=True)
class FinalizationDecision:
    decision_id: str
    allow_final: bool
    continue_work: bool
    rewrite_required: bool
    human_required: bool
    mode: str
    reasons: tuple[str, ...] = field(default_factory=tuple)
    safe_statements: tuple[str, ...] = field(default_factory=tuple)
    missing_control_bindings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PreFinalReconcileResult:
    decision: FinalizationDecision
    checkpoint_id: str
    final_response_allowed: bool
    auto_continue_required: bool


def _stable_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    return sha256(payload.encode("utf-8")).hexdigest()


class PreFinalGate:
    """Fail-closed mission-closure and claim-integrity Stop gate."""

    version = "1.0.0"
    enforcement_point = "PRE_FINAL_RESPONSE"

    def evaluate(
        self,
        *,
        mission: MissionClosureState,
        candidate_response: str = "",
        claim_scans: Iterable[ClaimScanSnapshot | Mapping[str, Any]] = (),
        controls: Iterable[ControlBinding] = (),
    ) -> FinalizationDecision:
        scans = tuple(
            item
            if isinstance(item, ClaimScanSnapshot)
            else ClaimScanSnapshot.from_mapping(item)
            for item in claim_scans
        )
        controls = tuple(controls)
        reasons: list[str] = []
        safe_statements: list[str] = []
        missing_controls: list[str] = []
        rewrite_required = False

        if MATERIAL_MATURITY_RE.search(candidate_response or "") and not scans:
            reasons.append("MATERIAL_MATURITY_CLAIM_SCAN_REQUIRED")
            rewrite_required = True

        for scan in scans:
            if scan.blocks_final:
                reasons.append(f"CLAIM_PROOF_GATE_BLOCK:{scan.subject}")
                rewrite_required = True
                if scan.safe_statement:
                    safe_statements.append(scan.safe_statement)
            elif scan.requires_rewrite:
                reasons.append(f"CLAIM_REWRITE_REQUIRED:{scan.subject}")
                rewrite_required = True
                if scan.safe_statement:
                    safe_statements.append(scan.safe_statement)

        for control in controls:
            if control.healthy:
                continue
            if control.missing_points:
                missing_controls.append(
                    f"{control.control_id}:{','.join(control.missing_points)}"
                )
            else:
                missing_controls.append(f"{control.control_id}:REGRESSION_UNPROVEN")
        if missing_controls:
            reasons.append("MANDATORY_CONTROL_ORPHANED_OR_UNTESTED")

        actionable = sorted(gap.gap_id for gap in mission.gaps if gap.actionable)
        if actionable:
            reasons.append("KNOWN_ACTIONABLE_GAP_REMAINS:" + ",".join(actionable))

        if mission.outcome_first_continue_recovery:
            reasons.append("RECOVERABLE_ISSUE_REQUIRES_CONTINUED_RECOVERY")

        if reasons:
            return self._decision(
                mission=mission,
                allow_final=False,
                continue_work=True,
                rewrite_required=rewrite_required,
                human_required=False,
                mode="BLOCK_FINAL_CONTINUE_WORK",
                reasons=reasons,
                safe_statements=safe_statements,
                missing_controls=missing_controls,
            )

        terminal = mission.terminal_state
        if terminal is TerminalState.VERIFIED_COMPLETE:
            if not mission.objective_satisfied:
                return self._block(
                    mission, "VERIFIED_COMPLETE_WITHOUT_OBJECTIVE_SATISFACTION"
                )
            return self._allow(mission, "ALLOW_VERIFIED_COMPLETE")

        if terminal is TerminalState.OWNER_DECISION_REQUIRED:
            if not mission.owner_decision_request.strip():
                return self._block(mission, "OWNER_DECISION_REQUEST_NOT_PRECISE")
            return self._allow(
                mission,
                "ALLOW_PRECISE_OWNER_DECISION",
                human_required=True,
                reasons=("GENUINE_OWNER_DECISION_REQUIRED",),
            )

        if terminal is TerminalState.BLOCKED_IRREDUCIBLY:
            if not mission.irreducible_blocker.strip() or not mission.exhaustion_evidence_ref.strip():
                return self._block(mission, "IRREDUCIBLE_BLOCK_NOT_PROVEN")
            return self._allow(
                mission,
                "ALLOW_PROVEN_IRREDUCIBLE_BLOCKER",
                reasons=("OBJECTIVE_LEVEL_EXHAUSTION_PROVED",),
            )

        if terminal is TerminalState.LEGAL_OR_SAFETY_PROHIBITION:
            if not mission.irreducible_blocker.strip():
                return self._block(mission, "LEGAL_OR_SAFETY_PROHIBITION_NOT_SPECIFIED")
            return self._allow(
                mission,
                "ALLOW_LEGAL_OR_SAFETY_PROHIBITION",
                reasons=("LEGAL_OR_SAFETY_PROHIBITION",),
            )

        if terminal is TerminalState.ACTIVE_TURN_BOUNDARY:
            if mission.currently_executable_work:
                return self._block(mission, "ACTIVE_TURN_BOUNDARY_HAS_EXECUTABLE_WORK")
            if not mission.resumable_checkpoint_ref.strip():
                return self._block(
                    mission, "ACTIVE_TURN_BOUNDARY_WITHOUT_RESUMABLE_CHECKPOINT"
                )
            return self._allow(
                mission,
                "ALLOW_RESUMABLE_ACTIVE_TURN_BOUNDARY",
                reasons=("HOST_TURN_BOUNDARY_WITH_RESUMABLE_STATE",),
            )

        return self._block(mission, "MISSION_ACTIVE_NO_VALID_TERMINAL_STATE")

    def _decision(
        self,
        *,
        mission: MissionClosureState,
        allow_final: bool,
        continue_work: bool,
        rewrite_required: bool,
        human_required: bool,
        mode: str,
        reasons: Iterable[str] = (),
        safe_statements: Iterable[str] = (),
        missing_controls: Iterable[str] = (),
    ) -> FinalizationDecision:
        reasons = tuple(reasons)
        safe_statements = tuple(safe_statements)
        missing_controls = tuple(missing_controls)
        material = {
            "version": self.version,
            "mission_id": mission.mission_id,
            "mode": mode,
            "allow_final": allow_final,
            "continue_work": continue_work,
            "rewrite_required": rewrite_required,
            "human_required": human_required,
            "reasons": reasons,
            "safe_statements": safe_statements,
            "missing_controls": missing_controls,
        }
        return FinalizationDecision(
            decision_id="pf_" + _stable_hash(material)[:20],
            allow_final=allow_final,
            continue_work=continue_work,
            rewrite_required=rewrite_required,
            human_required=human_required,
            mode=mode,
            reasons=reasons,
            safe_statements=safe_statements,
            missing_control_bindings=missing_controls,
        )

    def _block(self, mission: MissionClosureState, reason: str) -> FinalizationDecision:
        return self._decision(
            mission=mission,
            allow_final=False,
            continue_work=True,
            rewrite_required=False,
            human_required=False,
            mode="BLOCK_FINAL_CONTINUE_WORK",
            reasons=(reason,),
        )

    def _allow(
        self,
        mission: MissionClosureState,
        mode: str,
        *,
        human_required: bool = False,
        reasons: Iterable[str] = (),
    ) -> FinalizationDecision:
        return self._decision(
            mission=mission,
            allow_final=True,
            continue_work=False,
            rewrite_required=False,
            human_required=human_required,
            mode=mode,
            reasons=reasons,
        )


class ChatGovPreFinalInterlock:
    """Durable policy-enforcement adapter at the final-response boundary."""

    def __init__(
        self,
        state: DurableState,
        gate: Optional[PreFinalGate] = None,
    ) -> None:
        self.state = state
        self.gate = gate or PreFinalGate()

    def before_final_response(
        self,
        *,
        mission: MissionClosureState,
        candidate_response: str = "",
        claim_scans: Iterable[ClaimScanSnapshot | Mapping[str, Any]] = (),
        controls: Iterable[ControlBinding] = (),
    ) -> PreFinalReconcileResult:
        decision = self.gate.evaluate(
            mission=mission,
            candidate_response=candidate_response,
            claim_scans=claim_scans,
            controls=controls,
        )
        actionable_count = sum(1 for gap in mission.gaps if gap.actionable)
        checkpoint_id = self.state.checkpoint(
            mission.mission_id,
            {
                "event": "PRE_FINAL_RESPONSE_DECISION",
                "gate_version": self.gate.version,
                "terminal_state": mission.terminal_state.value,
                "objective_satisfied": mission.objective_satisfied,
                "actionable_gap_count": actionable_count,
                "decision": asdict(decision),
            },
            proof_bearing=bool(
                decision.allow_final
                and mission.terminal_state is TerminalState.VERIFIED_COMPLETE
            ),
        )
        self.state.update_metric(
            "chatgov.prefinal.blocked", 0.0 if decision.allow_final else 1.0
        )
        self.state.update_metric(
            "chatgov.prefinal.actionable_gaps", float(actionable_count)
        )
        self.state.update_metric(
            "chatgov.prefinal.rewrite_required",
            1.0 if decision.rewrite_required else 0.0,
        )
        self.state.update_metric(
            "chatgov.prefinal.owner_decision",
            1.0 if decision.human_required else 0.0,
        )
        return PreFinalReconcileResult(
            decision=decision,
            checkpoint_id=checkpoint_id,
            final_response_allowed=decision.allow_final,
            auto_continue_required=decision.continue_work,
        )


__all__ = [
    "ChatGovPreFinalInterlock",
    "ClaimScanSnapshot",
    "ControlBinding",
    "FinalizationDecision",
    "GapState",
    "MissionClosureState",
    "PreFinalGate",
    "PreFinalReconcileResult",
    "TerminalState",
]
