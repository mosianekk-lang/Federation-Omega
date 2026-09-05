"""Final-response emission permit for ChatGov.

This module strengthens PRE_FINAL_RESPONSE with a time-of-check/time-of-use
binding. A host that routes through ChatGov may only emit the exact candidate
response that passed the pre-final gate for the exact mission snapshot.

It does not modify native ChatGPT or any provider host that bypasses this
middleware. It is provider-neutral and effect-free.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Mapping

from .pre_final import FinalizationDecision, MissionClosureState


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FinalResponsePermit:
    permit_id: str
    mission_id: str
    decision_id: str
    candidate_sha256: str
    mission_sha256: str
    policy_version: str
    terminal_mode: str


@dataclass(frozen=True)
class PermitValidation:
    valid: bool
    reasons: tuple[str, ...]


class FinalResponsePermitAuthority:
    """Mint and validate fail-closed emission permits.

    The permit binds the final response body, mission snapshot and pre-final
    decision. Any material mutation after approval invalidates the permit and
    requires a fresh PRE_FINAL_RESPONSE evaluation.
    """

    version = "1.0.0"

    def issue(
        self,
        *,
        decision: FinalizationDecision,
        mission: MissionClosureState,
        candidate_response: str,
    ) -> FinalResponsePermit:
        if not decision.allow_final:
            raise ValueError("FINAL_RESPONSE_PERMIT_REQUIRES_ALLOW_DECISION")
        candidate_sha = _canonical_hash(candidate_response)
        mission_sha = _canonical_hash(asdict(mission))
        material = {
            "version": self.version,
            "mission_id": mission.mission_id,
            "decision_id": decision.decision_id,
            "candidate_sha256": candidate_sha,
            "mission_sha256": mission_sha,
            "terminal_mode": decision.mode,
        }
        return FinalResponsePermit(
            permit_id="frp_" + _canonical_hash(material)[:24],
            mission_id=mission.mission_id,
            decision_id=decision.decision_id,
            candidate_sha256=candidate_sha,
            mission_sha256=mission_sha,
            policy_version=self.version,
            terminal_mode=decision.mode,
        )

    def validate(
        self,
        *,
        permit: FinalResponsePermit | Mapping[str, Any],
        decision: FinalizationDecision,
        mission: MissionClosureState,
        candidate_response: str,
    ) -> PermitValidation:
        if not isinstance(permit, FinalResponsePermit):
            permit = FinalResponsePermit(**dict(permit))

        reasons: list[str] = []
        if not decision.allow_final:
            reasons.append("PRE_FINAL_DECISION_NO_LONGER_ALLOWS_FINAL")
        if permit.policy_version != self.version:
            reasons.append("PERMIT_POLICY_VERSION_MISMATCH")
        if permit.mission_id != mission.mission_id:
            reasons.append("PERMIT_MISSION_MISMATCH")
        if permit.decision_id != decision.decision_id:
            reasons.append("PERMIT_DECISION_MISMATCH")
        if permit.candidate_sha256 != _canonical_hash(candidate_response):
            reasons.append("CANDIDATE_CHANGED_AFTER_PREFINAL_APPROVAL")
        if permit.mission_sha256 != _canonical_hash(asdict(mission)):
            reasons.append("MISSION_STATE_CHANGED_AFTER_PREFINAL_APPROVAL")
        if permit.terminal_mode != decision.mode:
            reasons.append("TERMINAL_MODE_CHANGED_AFTER_PREFINAL_APPROVAL")

        return PermitValidation(valid=not reasons, reasons=tuple(reasons))

    @staticmethod
    def telemetry_attributes(
        *, permit: FinalResponsePermit, validation: PermitValidation
    ) -> dict[str, Any]:
        """Return OpenTelemetry-friendly decision attributes.

        This is a schema adapter only; it does not claim an external collector
        or OpenTelemetry exporter is configured.
        """

        return {
            "chatgov.emission.permit_id": permit.permit_id,
            "chatgov.emission.mission_id": permit.mission_id,
            "chatgov.emission.decision_id": permit.decision_id,
            "chatgov.emission.policy_version": permit.policy_version,
            "chatgov.emission.terminal_mode": permit.terminal_mode,
            "chatgov.emission.valid": validation.valid,
            "chatgov.emission.failure_reasons": list(validation.reasons),
        }


__all__ = [
    "FinalResponsePermit",
    "FinalResponsePermitAuthority",
    "PermitValidation",
]
