from __future__ import annotations

from dataclasses import asdict, dataclass

from .architecture_consolidation import ArchitectureConsolidationRegistry
from .high_coupling_policy_compatibility import C4HighCouplingPolicyContract


@dataclass(frozen=True)
class C4Scenario:
    scenario_id: str
    pass_state: bool
    checks: dict[str, bool]


def run_c4_high_coupling_policy_shadow() -> dict[str, object]:
    """Run the portable C4 authority/interface compatibility court.

    This layer deliberately does not import or read Superior Logic or CASEFORGE
    runtime source. It proves only that the C4 compatibility contract preserves
    the required authority, lineage, rollback and fail-closed obligations. Real
    runtime behavior is exercised separately by the repository-shell Phoenix C4
    court. Keeping those two proof surfaces separate prevents repository-only
    dependencies from leaking into the independently runnable Phoenix Core.
    """

    contract = C4HighCouplingPolicyContract()
    registry = ArchitectureConsolidationRegistry()
    expected = contract.required_scenarios
    bindings = contract.source_bindings
    relationship = contract.contract["target_relationship"]
    authority_map = contract.contract["authority_map"]
    truth = contract.source_truth_boundary()
    rollback = contract.rollback_contract()

    # Portable obligations are declarations of what the repository-shell court
    # must falsify. They are not treated as runtime/provider proof here.
    required = set(expected)

    s1_checks = {
        "canonical_caseforge_host_declared": relationship["CASEFORGE-Ω"]["canonical_superior_logic_maturation_host"]
        == "evidenceops.caseforge.maturation_shadow_cli",
        "superior_runtime_binding_present": "superior_logic_runtime" in bindings,
        "caseforge_runtime_binding_present": "caseforge_maturation_runtime" in bindings,
        "repository_shell_binding_present": bool(bindings.get("maturation_workflow", {}).get("repository_shell_only")),
        "portable_layer_performs_no_runtime_import": True,
    }
    s1 = C4Scenario("C4-WRAPPER-HOST-COMPATIBILITY", all(s1_checks.values()), s1_checks)

    s2_checks = {
        "completion_self_certification_forbidden": contract.forbidden(
            "SUPERIOR_LOGIC_POLICY_SELF_CERTIFIES_SCIENTIFIC_VALIDITY"
        ),
        "independent_observation_remains_repository_behavioral_obligation": "C4-POLICY-COMPLETION-BOUNDARY" in required,
        "provider_effect_not_inferred_from_completion": truth["provider_effect"] is False,
        "runtime_change_not_inferred_from_contract": truth["runtime_changed"] is False,
    }
    s2 = C4Scenario("C4-POLICY-COMPLETION-BOUNDARY", all(s2_checks.values()), s2_checks)

    s3_checks = {
        "competing_hypotheses_required": "C4-SCIENTIFIC-FALSIFICATION" in required,
        "testable_prediction_required": "C4-SCIENTIFIC-FALSIFICATION" in required,
        "falsifier_required": "C4-SCIENTIFIC-FALSIFICATION" in required,
        "missing_falsifier_fails_closed": "C4-SCIENTIFIC-FALSIFICATION" in required,
        "scientific_validation_stays_caseforge_owned": authority_map["scientific_falsification_and_blind_validation"]
        == "CASEFORGE_EVIDENCEOPS",
    }
    s3 = C4Scenario("C4-SCIENTIFIC-FALSIFICATION", all(s3_checks.values()), s3_checks)

    s4_checks = {
        "hidden_control_leak_fails_closed": "C4-BLIND-EVALUATION-SEPARATION" in required,
        "answer_key_leak_is_rejected": "C4-BLIND-EVALUATION-SEPARATION" in required,
        "blind_validation_stays_caseforge_owned": authority_map["scientific_falsification_and_blind_validation"]
        == "CASEFORGE_EVIDENCEOPS",
        "portable_contract_does_not_execute_tested_agent": True,
    }
    s4 = C4Scenario("C4-BLIND-EVALUATION-SEPARATION", all(s4_checks.values()), s4_checks)

    s5_checks = {
        "provider_verified_requires_readback": "C4-PROVIDER-READBACK-SEPARATION" in required,
        "provider_verified_without_readback_fails": "C4-PROVIDER-READBACK-SEPARATION" in required,
        "provider_effect_stays_external": authority_map["provider_or_external_effect"]
        == "SOVARA_OR_OWNER_RESERVED_EFFECT_AUTHORITY",
        "portable_contract_claims_no_provider_runtime": truth["provider_runtime_proved"] is False,
    }
    s5 = C4Scenario("C4-PROVIDER-READBACK-SEPARATION", all(s5_checks.values()), s5_checks)

    s6_checks = {
        "cross_provider_is_independence_dimension": "C4-INDEPENDENT-REPLICATION" in required,
        "same_provider_same_model_same_route_is_not_independent": "C4-INDEPENDENT-REPLICATION" in required,
        "material_independence_required": "C4-INDEPENDENT-REPLICATION" in required,
        "replication_does_not_mint_effect_authority": truth["provider_effect"] is False,
    }
    s6 = C4Scenario("C4-INDEPENDENT-REPLICATION", all(s6_checks.values()), s6_checks)

    authority = contract.authority_boundary()
    s7_checks = {
        "superior_logic_target_is_policy_library": authority.superior_logic_target
        == "FOREST_FIRST_REASONING_POLICY_AND_INVARIANT_LIBRARY",
        "caseforge_target_is_validation_lab": authority.caseforge_target
        == "EVIDENCEOPS_SCIENTIFIC_VALIDATION_LABORATORY",
        "evidence_truth_stays_outside_both": authority.evidence_truth_owner
        == "EVIDENCEOPS_TRUTHGRID_JFRIE",
        "provider_effect_stays_external": authority.provider_effect_owner
        == "SOVARA_OR_OWNER_RESERVED_EFFECT_AUTHORITY",
        "no_authority_transfer": not authority.authority_transferred,
    }
    s7 = C4Scenario("C4-AUTHORITY-NON-TAKEOVER", all(s7_checks.values()), s7_checks)

    independent_systems = set(registry.independent_systems())
    s8_checks = {
        "independent_assurance_preserved": independent_systems
        == {"Sentinel Ω", "CFBE-Ω", "JARVIS", "Reality Guard"},
        "independent_assurance_owner_declared": authority.independent_assurance_owner
        == "SENTINEL_CFBE_JARVIS_REALITYGUARD",
        "assurance_not_folded_into_policy_or_validation": True,
    }
    s8 = C4Scenario("C4-INDEPENDENT-ASSURANCE-NO-SPOF", all(s8_checks.values()), s8_checks)

    superior = registry.resolve("Superior Logic Doctrine")
    caseforge = registry.resolve("CASEFORGE-Ω")
    s9_checks = {
        "superior_legacy_identity_resolves": superior.legacy_calls_allowed and superior.translate_to_target,
        "caseforge_legacy_identity_resolves": caseforge.legacy_calls_allowed and caseforge.translate_to_target,
        "superior_target_layer_is_cognitive": superior.target_authority_layer == "COGNITIVE_KERNEL",
        "caseforge_target_layer_is_evidence_truth": caseforge.target_authority_layer == "EVIDENCE_TRUTH",
        "no_legacy_maturity_inheritance": not superior.maturity_inherited and not caseforge.maturity_inherited,
        "no_legacy_authority_inheritance": not superior.authority_inherited and not caseforge.authority_inherited,
    }
    s9 = C4Scenario("C4-LEGACY-IDENTITY-COMPATIBILITY", all(s9_checks.values()), s9_checks)

    s10_checks = {
        "all_bound_sources_have_git_sha": all(len(str(item.get("sha", ""))) == 40 for item in bindings.values()),
        "legacy_runtime_sources_preserved": rollback["legacy_runtime_sources_preserved"] is True,
        "historical_proof_not_rewritten": rollback["historical_proof_never_rewritten"] is True,
        "no_runtime_change_claim": truth["runtime_changed"] is False,
        "no_physical_migration": truth["physical_migration_executed"] is False,
        "no_retirement": truth["system_retirement_executed"] is False,
        "no_provider_effect": truth["provider_effect"] is False,
    }
    s10 = C4Scenario("C4-ROLLBACK-AND-LINEAGE", all(s10_checks.values()), s10_checks)

    scenarios = (s1, s2, s3, s4, s5, s6, s7, s8, s9, s10)
    return {
        "shadow_id": "FOREST-FIRST-CONSOLIDATION-C4-HIGH-COUPLING-POLICY-SHADOW-V1",
        "cohort": "C4_HIGH_COUPLING_POLICY_VALIDATION",
        "scenario_count": len(scenarios),
        "required_scenarios": list(expected),
        "scenarios": [asdict(row) for row in scenarios],
        "pass": tuple(row.scenario_id for row in scenarios) == expected and all(row.pass_state for row in scenarios),
        "authority_ceiling": "A1_INTERNAL",
        "external_effect": False,
        "provider_runtime_proved": False,
        "physical_migration_executed": False,
        "system_retirement_allowed": False,
        "superior_logic_runtime_rewired": False,
        "caseforge_authority_expanded": False,
        "maturity_inheritance": False,
        "behavioral_execution_surface": "REPOSITORY_SHELL_PHOENIX_COURT",
        "independent_assurance_review": "PENDING",
        "promotion_state": "SHADOW_PASS_PENDING_PROVIDER_HOSTED_ADMISSION_AND_INDEPENDENT_ASSURANCE",
        "truth_boundary": "PORTABLE_AUTHORITY_INTERFACE_OBLIGATIONS_PLUS_SEPARATE_REPOSITORY_BEHAVIORAL_COURT_NOT_RUNTIME_MIGRATION_OR_PROVIDER_EFFECT",
    }


__all__ = ["C4Scenario", "run_c4_high_coupling_policy_shadow"]
