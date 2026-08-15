from __future__ import annotations

"""ChatGov interlock for reusable Federation provider trust.

The interlock runs before an owner prompt about provider credentials or provider
availability. It suppresses unnecessary owner interruption when the next step is
system-actionable, preserves owner-only billing/credential bootstrap boundaries,
and never grants consequential authority.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from federation_consolidation.provider_trust_policy import provider_trust_use_decision

from .state import DurableState


OPENAI_CAPABILITY_ALIAS = "OPENAI_PRIMARY_RUNTIME"


@dataclass(frozen=True)
class ProviderDependencyReconcileResult:
    capability_alias: str
    state: str
    provider_runtime_ready: bool
    should_prompt_owner: bool
    system_action_available: bool
    next_action: str
    credential_rotation_recommended: bool
    consequential_authority_granted: bool
    checkpoint_id: str
    proof_bearing: bool


class ChatGovProviderTrustInterlock:
    """Route provider dependencies using verified provider-trust receipts."""

    capability_alias = OPENAI_CAPABILITY_ALIAS

    def __init__(self, state: DurableState) -> None:
        self.state = state

    def reconcile(
        self,
        mission_id: str,
        resolution: Mapping[str, Any],
        *,
        trigger: str,
    ) -> ProviderDependencyReconcileResult:
        trust = provider_trust_use_decision(
            resolution,
            expected_capability_alias=self.capability_alias,
        )
        proof_bearing = trust.provider_runtime_ready
        checkpoint_id = self.state.checkpoint(
            mission_id,
            {
                "event": "PROVIDER_TRUST_RECONCILED",
                "trigger": trigger,
                "capability_alias": trust.capability_alias,
                "state": trust.state,
                "provider_runtime_ready": trust.provider_runtime_ready,
                "system_action_available": trust.system_action_available,
                "owner_action_required": trust.owner_action_required,
                "should_prompt_owner": trust.owner_action_required,
                "next_action": trust.next_action,
                "credential_rotation_recommended": trust.credential_rotation_recommended,
                "trust_receipt_sha256": trust.trust_receipt_sha256,
                "consequential_authority_granted": False,
            },
            proof_bearing=proof_bearing,
        )
        return ProviderDependencyReconcileResult(
            capability_alias=trust.capability_alias,
            state=trust.state,
            provider_runtime_ready=trust.provider_runtime_ready,
            should_prompt_owner=trust.owner_action_required,
            system_action_available=trust.system_action_available,
            next_action=trust.next_action,
            credential_rotation_recommended=trust.credential_rotation_recommended,
            consequential_authority_granted=False,
            checkpoint_id=checkpoint_id,
            proof_bearing=proof_bearing,
        )

    def before_user_prompt(
        self,
        mission_id: str,
        resolution: Mapping[str, Any],
    ) -> ProviderDependencyReconcileResult:
        """Mandatory PRE_USER_PROMPT provider-dependency reconciliation point."""
        return self.reconcile(
            mission_id,
            resolution,
            trigger="PRE_USER_PROMPT",
        )


__all__ = [
    "ChatGovProviderTrustInterlock",
    "OPENAI_CAPABILITY_ALIAS",
    "ProviderDependencyReconcileResult",
]
