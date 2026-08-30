from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path

from .architecture_consolidation import ArchitectureConsolidationRegistry
from .high_coupling_policy_compatibility import C4HighCouplingPolicyContract


@dataclass(frozen=True)
class C4Scenario:
    scenario_id: str
    pass_state: bool
    checks: dict[str, bool]


def _source(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _assigned_tuple(source: str, name: str) -> tuple[str, ...]:
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            value = ast.literal_eval(node.value)
            return tuple(str(item) for item in value)
    raise ValueError(f"assignment not found: {name}")


def run_c4_high_coupling_policy_shadow() -> dict[str, object]:
    """Run ten portable C4 source/interface compatibility scenarios.

    This portable AO-HARMONIC shadow deliberately does not import the broad
    CASEFORGE package or Superior Logic runtime. Those real behavioral contracts
    are executed by the repository-shell Phoenix court. Keeping the portable
    layer source/interface-only prevents repository/provider-control coupling
    from leaking into the independently runnable Phoenix Core projection.
    """

    root = Path(__file__).resolve().parents[1]
    contract = C4HighCouplingPolicyContract()
    registry = ArchitectureConsolidationRegistry()

    superior_runtime = _source(root, "superior_logic/runtime.py")
    wrapper = _source(root, "tools/superior_logic_maturation_shadow.py")
    cli = _source(root, "evidenceops/caseforge/maturation_shadow_cli.py")
    maturation = _source(root, "evidenceops/caseforge/maturation_shadow_runtime.py")
    scientia_source = _source(root, "evidenceops/caseforge/scientia.py")
    blind_source = _source(root, "evidenceops/caseforge/blind_runner.py")
    replication_source = _source(root, "evidenceops/caseforge/replication.py")

    s1_checks = {
        "superior_wrapper_is_compatibility_entrypoint": "Compatibility entrypoint" in wrapper,
        "wrapper_delegates_to_caseforge_cli": "evidenceops.caseforge.maturation_shadow_cli" in wrapper,
        "caseforge_cli_imports_maturation_runtime": "from .maturation_shadow_runtime import" in cli,
        "maturation_runtime_is_a1_internal": 'RUNTIME_AUTHORITY = "A1_INTERNAL"' in maturation,
        "maturation_runtime_declares_no_external_effect": "external_effect: bool = False" in maturation,
    }
    s1 = C4Scenario("C4-WRAPPER-HOST-COMPATIBILITY", all(s1_checks.values()), s1_checks)

    done_predicates = _assigned_tuple(superior_runtime, "DONE_PREDICATES")
    expected_done = {
        "operation_occurred",
        "target_resolved",
        "semantic_success",
        "payload_present",
        "result_stored",
        "source_readback_verified",
        "integrity_verified",
        "independent_observation_verified",
        "delivery_confirmed",
        "audit_complete",
        "no_invalidating_contradiction",
    }
    s2_checks = {
        "done_predicates_exactly_preserved": set(done_predicates) == expected_done and len(done_predicates) == 11,
        "derive_done_fails_closed_on_missing_predicate": "predicates.get(name, False)" in superior_runtime,
        "derive_done_returns_missing_contract": "return (not missing, missing)" in superior_runtime,
        "independent_observation_is_mandatory": "independent_observation_verified" in done_predicates,
    }
    s2 = C4Scenario("C4-POLICY-COMPLETION-BOUNDARY", all(s2_checks.values()), s2_checks)

    s3_checks = {
        "competing_hypotheses_required": "len(hypotheses) < 2" in scientia_source,
        "testable_prediction_required": "has no testable prediction" in scientia_source,
        "falsifier_required": "has no falsifier" in scientia_source,
        "scientia_remains_a1": '"authority_ceiling": "A1_INTERNAL"' in scientia_source,
        "scientia_remains_no_effect": '"external_effect": False' in scientia_source,
    }
    s3 = C4Scenario("C4-SCIENTIFIC-FALSIFICATION", all(s3_checks.values()), s3_checks)

    s4_checks = {
        "answer_key_is_reserved_control": '"answer_key"' in blind_source,
        "hidden_control_leak_fails_closed": "hidden control leakage detected at:" in blind_source,
        "blind_payload_has_explicit_guard": "def assert_blind_payload" in blind_source,
        "tested_agent_receives_control_free_context": "tested agent receives no scorer object" in blind_source,
    }
    s4 = C4Scenario("C4-BLIND-EVALUATION-SEPARATION", all(s4_checks.values()), s4_checks)

    s5_checks = {
        "provider_verified_state_is_explicit": '"PROVIDER_VERIFIED"' in blind_source,
        "provider_verified_requires_readback": "provider-verified execution requires provider readback" in blind_source,
        "readback_reference_is_model_binding_state": "provider_readback_ref" in blind_source,
    }
    s5 = C4Scenario("C4-PROVIDER-READBACK-SEPARATION", all(s5_checks.values()), s5_checks)

    s6_checks = {
        "cross_provider_is_independence_dimension": 'dimensions.append("PROVIDER")' in replication_source,
        "same_provider_requires_model_and_route": '{"MODEL_VERSION", "EXECUTION_ROUTE"}.issubset(dimensions)' in replication_source,
        "non_independence_fails_closed": 'reasons.append("MATERIAL_INDEPENDENCE_NOT_PROVEN")' in replication_source,
        "agreement_not_treated_as_truth": "agreement/correctness remains the" in replication_source,
        "replication_remains_no_effect": "replication run must remain A1_INTERNAL/no-external-effect" in replication_source,
    }
    s6 = C4Scenario("C4-INDEPENDENT-REPLICATION", all(s6_checks.values()), s6_checks)

    authority = contract.authority_boundary()
    s7_checks = {
        "superior_logic_target_is_policy_library": authority.superior_logic_target == "FOREST_FIRST_REASONING_POLICY_AND_INVARIANT_LIBRARY",
        "caseforge_target_is_validation_lab": authority.caseforge_target == "EVIDENCEOPS_SCIENTIFIC_VALIDATION_LABORATORY",
        "evidence_truth_stays_outside_both": authority.evidence_truth_owner == "EVIDENCEOPS_TRUTHGRID_JFRIE",
        "provider_effect_stays_external": authority.provider_effect_owner == "SOVARA_OR_OWNER_RESERVED_EFFECT_AUTHORITY",
        "caseforge_scientia_refuses_law_or_evidence_ownership": "does not decide law or mutate verified evidence" in scientia_source,
        "no_authority_transfer": not authority.authority_transferred,
    }
    s7 = C4Scenario("C4-AUTHORITY-NON-TAKEOVER", all(s7_checks.values()), s7_checks)

    independent_systems = set(registry.independent_systems())
    relationship = contract.contract["target_relationship"]
    s8_checks = {
        "superior_logic_runtime_source_remains_present": (root / "superior_logic/runtime.py").exists(),
        "caseforge_runtime_source_remains_present": (root / "evidenceops/caseforge/maturation_shadow_runtime.py").exists(),
        "standalone_superior_runtime_preserved_during_c4": relationship["Superior Logic Doctrine"]["standalone_runtime_preserved_during_c4"] is True,
        "independent_assurance_preserved": independent_systems == {"Sentinel Ω", "CFBE-Ω", "JARVIS", "Reality Guard"},
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

    truth = contract.source_truth_boundary()
    rollback = contract.rollback_contract()
    bindings = contract.source_bindings
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
    expected = contract.required_scenarios
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
        "truth_boundary": "PORTABLE_SOURCE_INTERFACE_COMPATIBILITY_PLUS_SEPARATE_REPOSITORY_BEHAVIORAL_COURT_NOT_RUNTIME_MIGRATION_OR_PROVIDER_EFFECT",
    }


__all__ = ["C4Scenario", "run_c4_high_coupling_policy_shadow"]
