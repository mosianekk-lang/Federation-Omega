from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class SourceScorecard:
    architecture_score: float
    control_plane_score: float
    empirical_score: float
    provider_score: float
    value_score: float
    level7_claim_allowed: bool


def score_source_programme(signals: Mapping[str, bool]) -> SourceScorecard:
    architecture_keys = (
        "objective_ecology",
        "resource_economy",
        "unified_autonomic_loops",
        "digital_twin",
        "dynamic_reorganization",
        "architectural_entropy_controller",
        "constitutional_amendment_court",
        "capability_market",
    )
    control_keys = (
        "owner_interruption_firewall",
        "autonomy_debt",
        "causal_learning",
        "information_value_budgeting",
        "negative_knowledge_diffusion",
        "no_self_authority_promotion",
    )
    empirical_keys = (
        "persistent_no_chat_continuity",
        "observed_maintenance_self_resolution",
        "observed_recovery_self_resolution",
        "observed_owner_interrupt_reduction",
    )
    provider_keys = ("provider_native_readback", "provider_wait_wake", "cross_machine_handoff")
    value_keys = ("prospective_owner_value", "sustained_value")

    def pct(keys: tuple[str, ...]) -> float:
        return round(sum(bool(signals.get(key, False)) for key in keys) / len(keys) * 100.0, 2)

    architecture = pct(architecture_keys)
    controls = pct(control_keys)
    empirical = pct(empirical_keys)
    provider = pct(provider_keys)
    value = pct(value_keys)
    claim = all(score == 100.0 for score in (architecture, controls, empirical, provider, value))
    return SourceScorecard(architecture, controls, empirical, provider, value, claim)
