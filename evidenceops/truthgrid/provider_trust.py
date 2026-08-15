from __future__ import annotations

"""TruthGrid adapter for the reusable OpenAI provider-trust capability.

A provider-trust receipt may establish that an AI/provider stage is available.
It does not authorize a TruthGrid mutation. All writes remain subject to the
existing TruthGridGuard plus independent provider readback.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from federation_consolidation.provider_trust_policy import provider_trust_use_decision
from federation_consolidation.provider_trust_resolver import ProviderTrustError

from .guards import MutationIntent, TruthGridViolation
from .writer_adapter import TruthGridWriterAdapter, WriterReceipt


OPENAI_CAPABILITY_ALIAS = "OPENAI_PRIMARY_RUNTIME"


@dataclass(frozen=True)
class TruthGridProviderStageDecision:
    capability_alias: str
    state: str
    provider_runtime_ready: bool
    may_prepare_ai_output: bool
    mutation_authority_granted: bool
    owner_action_required: bool
    system_action_available: bool
    next_action: str
    trust_receipt_sha256: str


@dataclass(frozen=True)
class ProviderBoundWriterReceipt:
    provider_trust_receipt_sha256: str
    writer_receipt: WriterReceipt
    mutation_authority_source: str = "TRUTHGRID_GUARD_PLUS_TARGET_READBACK"


class TruthGridProviderTrustAdapter:
    capability_alias = OPENAI_CAPABILITY_ALIAS

    def assess(self, resolution: Mapping[str, Any]) -> TruthGridProviderStageDecision:
        try:
            trust = provider_trust_use_decision(
                resolution,
                expected_capability_alias=self.capability_alias,
            )
        except ProviderTrustError as exc:
            raise TruthGridViolation("PROVIDER_TRUST_INVALID") from exc
        return TruthGridProviderStageDecision(
            capability_alias=trust.capability_alias,
            state=trust.state,
            provider_runtime_ready=trust.provider_runtime_ready,
            may_prepare_ai_output=trust.provider_runtime_ready,
            mutation_authority_granted=False,
            owner_action_required=trust.owner_action_required,
            system_action_available=trust.system_action_available,
            next_action=trust.next_action,
            trust_receipt_sha256=trust.trust_receipt_sha256,
        )

    def execute_ai_assisted_mutation(
        self,
        *,
        resolution: Mapping[str, Any],
        writer_adapter: TruthGridWriterAdapter,
        intent: MutationIntent,
    ) -> ProviderBoundWriterReceipt:
        """Require provider readiness, then defer mutation authority to TruthGrid."""

        decision = self.assess(resolution)
        if not decision.provider_runtime_ready:
            raise TruthGridViolation("OPENAI_PROVIDER_TRUST_NOT_READY:" + decision.state)
        writer_receipt = writer_adapter.execute(intent)
        return ProviderBoundWriterReceipt(
            provider_trust_receipt_sha256=decision.trust_receipt_sha256,
            writer_receipt=writer_receipt,
        )


__all__ = [
    "OPENAI_CAPABILITY_ALIAS",
    "ProviderBoundWriterReceipt",
    "TruthGridProviderStageDecision",
    "TruthGridProviderTrustAdapter",
]
