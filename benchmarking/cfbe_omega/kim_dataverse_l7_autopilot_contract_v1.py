from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AutopilotContract:
    internal_reversible_maintenance: bool = True
    internal_recovery: bool = True
    exact_head_restack: bool = True
    regression_repair: bool = True
    evidence_collection: bool = True
    mission_resume: bool = True
    iam_wif_mutation: bool = False
    provider_authority_expansion: bool = False
    financial_transaction: bool = False
    external_publish_send: bool = False
    destructive_external_mutation: bool = False
    owner_intent_change: bool = False


def default_autopilot_contract() -> AutopilotContract:
    return AutopilotContract()
