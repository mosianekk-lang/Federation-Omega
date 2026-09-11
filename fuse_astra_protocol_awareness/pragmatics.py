from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Tuple


class ParticipantRole(str, Enum):
    OWNER = "owner"
    HUMAN = "human"
    AGENT = "agent"
    TOOL = "tool"
    SERVICE = "service"
    EXTERNAL = "external"


class SpeechAct(str, Enum):
    INFORM = "inform"
    QUERY = "query"
    ANSWER = "answer"
    REQUEST = "request"
    COMMAND = "command"
    PROPOSE = "propose"
    ACCEPT = "accept"
    REJECT = "reject"
    APPROVE = "approve"
    WARN = "warn"
    ACK = "ack"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    EVIDENCE = "evidence"


class CommitmentState(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    APPROVED = "approved"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class SemanticMessage:
    message_id: str
    mission_id: str
    sender_id: str
    sender_role: ParticipantRole
    speech_act: SpeechAct
    topic: str
    reply_to: str | None = None
    commitment_id: str | None = None
    authority_scope: Tuple[str, ...] = ()
    requires_ack: bool = False


@dataclass(frozen=True)
class PragmaticPolicy:
    owner_ids: Tuple[str, ...] = ()
    delegated_commanders: Tuple[str, ...] = ()
    approval_roles: Tuple[ParticipantRole, ...] = (ParticipantRole.OWNER,)
    tools_may_command: bool = False
    agents_may_self_approve: bool = False


@dataclass(frozen=True)
class PragmaticDecision:
    allowed: bool
    normalized_act: SpeechAct
    reasons: Tuple[str, ...]


class PragmaticFirewall:
    """Model-independent speech-act and commitment guard.

    Content meaning and sender authority are evaluated separately. A message can
    be linguistically imperative while still being normalized to INFORM when the
    sender lacks command authority.
    """

    def evaluate(self, message: SemanticMessage, policy: PragmaticPolicy) -> PragmaticDecision:
        if message.speech_act is SpeechAct.COMMAND:
            if message.sender_role is ParticipantRole.TOOL and not policy.tools_may_command:
                return PragmaticDecision(True, SpeechAct.INFORM, ("tool command normalized to data/information",))
            if message.sender_id in policy.owner_ids or message.sender_id in policy.delegated_commanders:
                return PragmaticDecision(True, SpeechAct.COMMAND, ("sender has explicit command authority",))
            return PragmaticDecision(False, SpeechAct.REQUEST, ("sender lacks command authority",))

        if message.speech_act is SpeechAct.APPROVE:
            if message.sender_role not in policy.approval_roles:
                return PragmaticDecision(False, SpeechAct.INFORM, ("sender role cannot approve",))
            if message.sender_role is ParticipantRole.AGENT and not policy.agents_may_self_approve:
                return PragmaticDecision(False, SpeechAct.PROPOSE, ("agent self-approval forbidden",))
            return PragmaticDecision(True, SpeechAct.APPROVE, ("approval role permitted",))

        if message.speech_act in {SpeechAct.EVIDENCE, SpeechAct.INFORM, SpeechAct.ANSWER}:
            return PragmaticDecision(True, message.speech_act, ("informational/evidentiary act carries no execution authority by itself",))

        return PragmaticDecision(True, message.speech_act, ("speech act permitted by default communication policy",))


class CommitmentLedger:
    def __init__(self) -> None:
        self._states: Dict[str, CommitmentState] = {}

    def create(self, commitment_id: str) -> None:
        if commitment_id in self._states:
            raise ValueError("commitment already exists")
        self._states[commitment_id] = CommitmentState.PROPOSED

    def transition(self, commitment_id: str, new_state: CommitmentState) -> None:
        current = self._states[commitment_id]
        allowed = {
            CommitmentState.PROPOSED: {CommitmentState.ACCEPTED, CommitmentState.REJECTED, CommitmentState.CANCELLED},
            CommitmentState.ACCEPTED: {CommitmentState.APPROVED, CommitmentState.CANCELLED},
            CommitmentState.APPROVED: {CommitmentState.COMPLETED, CommitmentState.CANCELLED},
            CommitmentState.REJECTED: set(),
            CommitmentState.COMPLETED: set(),
            CommitmentState.CANCELLED: set(),
        }
        if new_state not in allowed[current]:
            raise ValueError(f"illegal commitment transition: {current.value} -> {new_state.value}")
        self._states[commitment_id] = new_state

    def state(self, commitment_id: str) -> CommitmentState:
        return self._states[commitment_id]
