from __future__ import annotations

from dataclasses import asdict, dataclass

from ao_harmonic_v3.failure_win_v2 import FailureWinState
from ao_harmonic_v3.recovery_formation_compatibility import RecoveryFormationCompatibility


@dataclass(frozen=True)
class RecoveryFormationScenario:
    scenario_id: str
    pass_state: bool
    checks: dict[str, bool]


def run_c3_recovery_formation_shadow() -> dict[str, object]:
    model = RecoveryFormationCompatibility()

    autofix_portable = model.portable_fingerprint("Ω-AUTOFIX")
    modisa_portable = model.portable_fingerprint("Modisa Continuum")
    autofix_local = model.local_fingerprint("Ω-AUTOFIX")
    modisa_local = model.local_fingerprint("Modisa Continuum")
    fingerprint_checks = {
        "portable_fingerprint_shared": autofix_portable == modisa_portable,
        "receiver_local_fingerprints_distinct": autofix_local != modisa_local,
        "portable_and_local_identity_not_collapsed": autofix_portable != autofix_local,
    }
    s1 = RecoveryFormationScenario(
        "C3-SHARED-PORTABLE-FINGERPRINT",
        all(fingerprint_checks.values()),
        fingerprint_checks,
    )

    autofix = model.evaluate_receiver("Ω-AUTOFIX")
    modisa = model.evaluate_receiver("Modisa Continuum")
    receipt_checks = {
        "normalized_receipts_equivalent": model.normalized_receipt(autofix) == model.normalized_receipt(modisa),
        "alternate_route_selected": autofix.selected_route_ids == (model.ALTERNATE_ROUTE_ID,),
        "proof_graph_remains_incomplete": not autofix.proof_graph.complete,
        "no_false_operational_win": autofix.state != FailureWinState.OPERATIONAL_WIN_VERIFIED,
    }
    s2 = RecoveryFormationScenario(
        "C3-RECOVERY-RECEIPT-EQUIVALENCE",
        all(receipt_checks.values()),
        receipt_checks,
    )

    unchanged = model.evaluate_receiver("Ω-AUTOFIX", materially_different=False)
    retry_checks = {
        "unchanged_route_not_selected": not unchanged.selected_route_ids,
        "repair_cycle_remains_open": unchanged.state == FailureWinState.REPAIR_CYCLE_OPEN,
        "alternate_route_search_required": any(
            action == "SEARCH_DYNAMIC_CAPABILITY_GRAPH_FOR_MATERIALLY_DIFFERENT_ROUTE"
            for action in unchanged.next_actions
        ),
    }
    s3 = RecoveryFormationScenario(
        "C3-UNCHANGED-RETRY-PROHIBITED",
        all(retry_checks.values()),
        retry_checks,
    )

    rerouted = model.evaluate_receiver("Modisa Continuum")
    objective_checks = {
        "failed_incumbent_route_does_not_end_objective": rerouted.state == FailureWinState.ROUTE_SELECTED,
        "materially_different_route_available": rerouted.selected_route_ids == (model.ALTERNATE_ROUTE_ID,),
        "state_not_quarantined_by_single_route_failure": rerouted.state != FailureWinState.QUARANTINED,
        "state_not_operationally_overpromoted": rerouted.state != FailureWinState.OPERATIONAL_WIN_VERIFIED,
    }
    s4 = RecoveryFormationScenario(
        "C3-ROUTE-FAILURE-NOT-OBJECTIVE-FAILURE",
        all(objective_checks.values()),
        objective_checks,
    )

    no_rollback = model.evaluate_receiver("Ω-AUTOFIX", rollback_available=False)
    rollback = model.evaluate_receiver("Ω-AUTOFIX", rollback_available=True)
    boundary = model.source_truth_boundary()
    rollback_checks = {
        "nonrollback_route_not_selected": not no_rollback.selected_route_ids,
        "rollback_route_selected": rollback.selected_route_ids == (model.ALTERNATE_ROUTE_ID,),
        "formation_release_denied_without_rollback": not model.formation_release(semantic_match=True, rollback_ready=False),
        "formation_release_allowed_with_semantic_readback_and_rollback": model.formation_release(semantic_match=True, rollback_ready=True),
        "semantic_mismatch_still_blocks_release": not model.formation_release(semantic_match=False, rollback_ready=True),
        "runtime_not_rewired": not boundary["runtime_rewired"],
        "provider_runtime_not_proved": not boundary["provider_runtime_proved"],
        "no_provider_effect": not boundary["provider_effect"],
    }
    s5 = RecoveryFormationScenario(
        "C3-ROLLBACK-AND-FORMATION-RELEASE",
        all(rollback_checks.values()),
        rollback_checks,
    )

    scenarios = (s1, s2, s3, s4, s5)
    return {
        "shadow_id": "FOREST-FIRST-CONSOLIDATION-C3-RECOVERY-FORMATION-SHADOW-V1",
        "cohort": "C3_RECOVERY_FORMATION",
        "scenario_count": len(scenarios),
        "scenarios": [asdict(row) for row in scenarios],
        "pass": all(row.pass_state for row in scenarios),
        "authority_ceiling": "A1_INTERNAL",
        "external_effect": False,
        "provider_runtime_proved": False,
        "canonical_docs_modified": False,
        "physical_migration_executed": False,
        "system_retirement_allowed": False,
        "failure_win_operational_maturity_inherited": False,
        "independent_assurance_review": "PENDING",
        "promotion_state": "SHADOW_PASS_PENDING_PROVIDER_HOSTED_ADMISSION_AND_INDEPENDENT_ASSURANCE",
        "truth_boundary": "DETERMINISTIC_SOURCE_COMPATIBILITY_SHADOW_COMPOSING_EXISTING_FAILURE_WIN_AND_FORMATION_PRIMITIVES_ONLY",
    }


__all__ = ["RecoveryFormationScenario", "run_c3_recovery_formation_shadow"]
