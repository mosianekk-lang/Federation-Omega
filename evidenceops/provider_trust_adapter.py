from __future__ import annotations

"""EvidenceOps adapter for Federation Provider Trust.

Provider trust proves availability of a provider runtime only. It never proves
that evidence is authentic, a legal proposition is correct, a source is
admissible, or an evidentiary maturity transition should be promoted.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from federation_consolidation.provider_trust_policy import provider_trust_use_decision


OPENAI_CAPABILITY_ALIAS = "OPENAI_PRIMARY_RUNTIME"


@dataclass(frozen=True)
class EvidenceOpsProviderTrustDecision:
    capability_alias: str
    state: str
    provider_runtime_ready: bool
    may_invoke_provider: bool
    may_promote_evidence: bool
    may_promote_legal_claim: bool
    owner_action_required: bool
    system_action_available: bool
    next_action: str
    credential_rotation_recommended: bool
    trust_receipt_sha256: str
    consequential_authority_granted: bool


class EvidenceOpsProviderTrustAdapter:
    """Map provider trust into EvidenceOps without trust or evidence inflation."""

    capability_alias = OPENAI_CAPABILITY_ALIAS

    def assess(self, resolution: Mapping[str, Any]) -> EvidenceOpsProviderTrustDecision:
        trust = provider_trust_use_decision(
            resolution,
            expected_capability_alias=self.capability_alias,
        )
        return EvidenceOpsProviderTrustDecision(
            capability_alias=trust.capability_alias,
            state=trust.state,
            provider_runtime_ready=trust.provider_runtime_ready,
            may_invoke_provider=trust.provider_runtime_ready,
            may_promote_evidence=False,
            may_promote_legal_claim=False,
            owner_action_required=trust.owner_action_required,
            system_action_available=trust.system_action_available,
            next_action=trust.next_action,
            credential_rotation_recommended=trust.credential_rotation_recommended,
            trust_receipt_sha256=trust.trust_receipt_sha256,
            consequential_authority_granted=False,
        )

    def proof_component(self, resolution: Mapping[str, Any]) -> dict[str, Any]:
        """Return an additive runtime-capability proof component, never final evidence proof."""

        decision = self.assess(resolution)
        return {
            "verified": decision.provider_runtime_ready,
            "capability_alias": decision.capability_alias,
            "provider_trust_state": decision.state,
            "trust_receipt_sha256": decision.trust_receipt_sha256,
            "semantic_scope": "PROVIDER_RUNTIME_CAPABILITY_ONLY",
            "may_promote_evidence": False,
            "may_promote_legal_claim": False,
            "consequential_authority_granted": False,
        }


__all__ = [
    "EvidenceOpsProviderTrustAdapter",
    "EvidenceOpsProviderTrustDecision",
    "OPENAI_CAPABILITY_ALIAS",
]
