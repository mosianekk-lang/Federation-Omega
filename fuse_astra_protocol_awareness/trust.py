from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Tuple


class MessageClass(str, Enum):
    CONTROL = "control"
    DATA = "data"
    EVENT = "event"
    TOOL_RESULT = "tool_result"
    HUMAN_INPUT = "human_input"
    AGENT_MESSAGE = "agent_message"


class TrustDecision(str, Enum):
    ALLOW = "allow"
    QUARANTINE = "quarantine"
    DENY = "deny"


@dataclass(frozen=True)
class PeerIdentity:
    peer_id: str
    issuer: str
    authenticated: bool
    workload_identity: str | None = None
    attested: bool = False


@dataclass(frozen=True)
class InboundMessage:
    message_id: str
    message_class: MessageClass
    peer: PeerIdentity
    requested_effect: str = "read"
    claimed_authority: Tuple[str, ...] = ()
    advertised_capabilities: Tuple[str, ...] = ()
    signature_valid: bool = True
    age_ms: int = 0
    content_origin: str = "unknown"


@dataclass(frozen=True)
class CommunicationTrustPolicy:
    trusted_issuers: Tuple[str, ...] = ()
    allowed_effects: Tuple[str, ...] = ("read",)
    authorized_control_peers: Tuple[str, ...] = ()
    require_signature: bool = True
    require_attestation_for_effects: Tuple[str, ...] = ()
    max_message_age_ms: int = 300_000
    data_can_never_escalate_to_control: bool = True


@dataclass(frozen=True)
class TrustResult:
    decision: TrustDecision
    reasons: Tuple[str, ...]


class ProtocolSemanticFirewall:
    """Separates communication authenticity, authority and content semantics.

    Advertising a capability never grants authority. Data/tool results cannot
    become control instructions merely because their payload contains imperative
    language. The firewall is deterministic and model-independent.
    """

    _NON_CONTROL = {
        MessageClass.DATA,
        MessageClass.EVENT,
        MessageClass.TOOL_RESULT,
        MessageClass.AGENT_MESSAGE,
    }

    def evaluate(self, message: InboundMessage, policy: CommunicationTrustPolicy) -> TrustResult:
        reasons = []

        if not message.peer.authenticated:
            return TrustResult(TrustDecision.DENY, ("peer is unauthenticated",))

        if policy.trusted_issuers and message.peer.issuer not in policy.trusted_issuers:
            return TrustResult(TrustDecision.DENY, ("identity issuer is not trusted",))

        if policy.require_signature and not message.signature_valid:
            return TrustResult(TrustDecision.DENY, ("message signature invalid",))

        if message.age_ms < 0 or message.age_ms > policy.max_message_age_ms:
            return TrustResult(TrustDecision.DENY, ("message freshness window exceeded",))

        if message.requested_effect not in policy.allowed_effects:
            return TrustResult(TrustDecision.DENY, ("requested effect is outside policy",))

        if (
            policy.data_can_never_escalate_to_control
            and message.message_class in self._NON_CONTROL
            and message.claimed_authority
        ):
            return TrustResult(
                TrustDecision.QUARANTINE,
                ("non-control content attempted to claim control authority",),
            )

        if message.message_class is MessageClass.CONTROL:
            if message.peer.peer_id not in policy.authorized_control_peers:
                return TrustResult(TrustDecision.DENY, ("peer is not authorized for control channel",))
            reasons.append("authorized control peer")

        if message.requested_effect in policy.require_attestation_for_effects and not message.peer.attested:
            return TrustResult(TrustDecision.DENY, ("requested effect requires attested peer",))

        # Capabilities are descriptive only. They are intentionally not used as
        # authority inputs; execution authority comes from policy/control state.
        if message.advertised_capabilities:
            reasons.append("capabilities treated as descriptive, not authoritative")

        reasons.append("authentication, freshness, effect and channel policy satisfied")
        return TrustResult(TrustDecision.ALLOW, tuple(reasons))


def authority_intersection(claimed: Tuple[str, ...], granted: Tuple[str, ...]) -> FrozenSet[str]:
    """Return only explicitly granted authority; never union advertised claims."""
    return frozenset(set(claimed).intersection(granted))
