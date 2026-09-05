from __future__ import annotations

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_completion_matrix_v1 import CompletionGate, GateClass
from benchmarking.cfbe_omega.kim_dataverse_level7_plus_current_source_signals_v1 import current_source_signals


def current_level7_plus_gates() -> tuple[CompletionGate, ...]:
    signals = current_source_signals()
    return (
        CompletionGate("level5-source", GateClass.SOURCE, all(signals[key] for key in (
            "objective_ecology", "resource_economy", "owner_interruption_firewall", "autonomy_debt", "dynamic_topology", "digital_twin"
        )), 5),
        CompletionGate("level6-source", GateClass.SOURCE, all(signals[key] for key in (
            "measured_gap_evolution", "historical_replay", "adversarial_qualification", "architectural_entropy_controller", "causal_learning", "no_self_authority_promotion"
        )), 6),
        CompletionGate("persistent-no-chat", GateClass.OBSERVED, signals["persistent_no_chat_continuity"], 7),
        CompletionGate("irreducible-owner-only", GateClass.VALUE, signals["irreducible_owner_interruptions_only"], 7),
        CompletionGate("verified-value-retention", GateClass.VALUE, signals["verified_value_retention"], 7),
        CompletionGate("lane-local-failure-isolation", GateClass.OBSERVED, signals["lane_local_failure_isolation"], 7),
        CompletionGate("google-wif-authority", GateClass.OWNER, False, 7, authority_required=True),
    )
