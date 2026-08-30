from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from evidenceops.caseforge.blind_runner import BlindIsolationError, ModelBinding, assert_blind_payload
from evidenceops.caseforge.replication import IndependentReplicationGate, ReplicationRun
from evidenceops.caseforge.scientia import EpistemicState, Hypothesis, ScientificObservation, ScientiaKernel
from superior_logic.runtime import DONE_PREDICATES, SuperiorLogicRuntime

from .architecture_consolidation import ArchitectureConsolidationRegistry
from .high_coupling_policy_compatibility import C4HighCouplingPolicyContract


@dataclass(frozen=True)
class C4Scenario:
    scenario_id: str
    pass_state: bool
    checks: dict[str, bool]


def _raised(fn, expected: type[BaseException]) -> bool:
    try:
        fn()
    except expected:
        return True
    return False


def _source(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def run_c4_high_coupling_policy_shadow() -> dict[str, object]:
    """Run the ten required C4 Superior Logic × CASEFORGE compatibility scenarios.

    The shadow is portable and A1-internal. It exercises deterministic source/runtime
    contracts only and deliberately avoids repository workflow reads, provider calls,
    source moves, authority transfer and maturity inheritance.
    """

    root = Path(__file__).resolve().parents[1]
    contract = C4HighCouplingPolicyContract()
    registry = ArchitectureConsolidationRegistry()

    wrapper = _source(root, "tools/superior_logic_maturation_shadow.py")
    cli = _source(root, "evidenceops/caseforge/maturation_shadow_cli.py")
    maturation = _source(root, "evidenceops/caseforge/maturation_shadow_runtime.py")
    scientia_source = _source(root, "evidenceops/caseforge/scientia.py")

    s1_checks = {
        "superior_wrapper_is_compatibility_entrypoint": "Compatibility entrypoint" in wrapper,
        "wrapper_delegates_to_caseforge_cli": "evidenceops.caseforge.maturation_shadow_cli" in wrapper,
        "caseforge_cli_imports_maturation_runtime": "from .maturation_shadow_runtime import" in cli,
        "maturation_runtime_is_a1_internal": 'RUNTIME_AUTHORITY = "A1_INTERNAL"' in maturation,
        "maturation_runtime_declares_no_external_effect": "external_effect: bool = False" in maturation,
    }
    s1 = C4Scenario("C4-WRAPPER-HOST-COMPATIBILITY", all(s1_checks.values()), s1_checks)

    runtime = SuperiorLogicRuntime(":memory:")
    try:
        complete = {name: True for name in DONE_PREDICATES}
        incomplete = dict(complete)
        incomplete["independent_observation_verified"] = False
        complete_done, complete_missing = runtime.derive_done(complete)
        incomplete_done, incomplete_missing = runtime.derive_done(incomplete)
    finally:
        runtime.close()
    s2_checks = {
        "complete_predicates_can_reach_done": complete_done and not complete_missing,
        "missing_independent_observation_blocks_done": not incomplete_done,
        "missing_predicate_is_reported": "independent_observation_verified" in incomplete_missing,
    }
    s2 = C4Scenario("C4-POLICY-COMPLETION-BOUNDARY", all(s2_checks.values()), s2_checks)

    scientia = ScientiaKernel()
    observations = (
        ScientificObservation("O1", "Observed source behavior", EpistemicState.VERIFIED_FACT, ("SRC-1",)),
    )
    hypotheses = (
        Hypothesis("H1", "Policy split preserves behavior", ("C4 remains green",), ("canonical regression fails",)),
        Hypothesis("H2", "Policy split introduces drift", ("a regression should fail",), ("all independent checks remain green",)),
    )
    design = scientia.validate_case_design(observations=observations, hypotheses=hypotheses)
    invalid_hypotheses = (
        hypotheses[0],
        Hypothesis("H3", "Unfalsifiable candidate", ("something happens",), ()),
    )
    s3_checks = {
        "competing_hypotheses_required_and_pass": design["status"] == "SCIENTIFIC_DESIGN_VALID" and design["hypotheses"] == 2,
        "design_remains_a1": design["authority_ceiling"] == "A1_INTERNAL" and design["external_effect"] is False,
        "missing_falsifier_fails_closed": _raised(
            lambda: scientia.validate_case_design(observations=observations, hypotheses=invalid_hypotheses),
            ValueError,
        ),
    }
    s3 = C4Scenario("C4-SCIENTIFIC-FALSIFICATION", all(s3_checks.values()), s3_checks)

    safe_blind_hash = assert_blind_payload({"case_id": "C4-BLIND", "facts": ["public synthetic fact"]})
    s4_checks = {
        "safe_blind_pack_hashes": len(safe_blind_hash) == 64,
        "answer_key_leak_is_rejected": _raised(
            lambda: assert_blind_payload({"case_id": "C4-BLIND", "answer_key": "hidden"}),
            BlindIsolationError,
        ),
    }
    s4 = C4Scenario("C4-BLIND-EVALUATION-SEPARATION", all(s4_checks.values()), s4_checks)

    unreadback = ModelBinding(
        provider="fixture-provider",
        model="fixture-model",
        version="fixture-v1",
        configuration={"temperature": 0},
        execution_state="PROVIDER_VERIFIED",
        provider_readback_ref="",
    )
    readback = ModelBinding(
        provider="fixture-provider",
        model="fixture-model",
        version="fixture-v1",
        configuration={"temperature": 0},
        execution_state="PROVIDER_VERIFIED",
        provider_readback_ref="provider:readback:C4",
    )
    readback_ok = True
    try:
        readback.validate()
    except BlindIsolationError:
        readback_ok = False
    s5_checks = {
        "provider_verified_without_readback_fails": _raised(unreadback.validate, BlindIsolationError),
        "provider_verified_with_readback_passes": readback_ok,
    }
    s5 = C4Scenario("C4-PROVIDER-READBACK-SEPARATION", all(s5_checks.values()), s5_checks)

    common = {
        "case_id": "C4-REP",
        "blind_input_sha256": "a" * 64,
        "tested_output_sha256": "b" * 64,
        "model": "fixture-model",
        "model_version_ref": "fixture-v1",
        "configuration_sha256": "c" * 64,
        "provider_readback_ref": "provider:verified",
        "provider_verified": True,
    }
    primary = ReplicationRun(run_id="R1", provider="provider-A", execution_route_id="route-A", **common)
    independent = ReplicationRun(run_id="R2", provider="provider-B", execution_route_id="route-A", **common)
    non_independent = ReplicationRun(run_id="R3", provider="provider-A", execution_route_id="route-A", **common)
    gate = IndependentReplicationGate()
    positive = gate.evaluate(primary, independent)
    negative = gate.evaluate(primary, non_independent)
    s6_checks = {
        "cross_provider_replication_is_independent": positive.independent and "PROVIDER" in positive.independence_dimensions,
        "same_provider_same_model_same_route_is_not_independent": not negative.independent,
        "replication_does_not_infer_truth_from_output_agreement": "MATERIAL_INDEPENDENCE_NOT_PROVEN" in negative.reason_codes,
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
        "independent_assurance_review": "PENDING",
        "promotion_state": "SHADOW_PASS_PENDING_PROVIDER_HOSTED_ADMISSION_AND_INDEPENDENT_ASSURANCE",
        "truth_boundary": "DETERMINISTIC_CONSUMER_AWARE_SOURCE_COMPATIBILITY_NOT_RUNTIME_MIGRATION_OR_PROVIDER_EFFECT",
    }


__all__ = ["C4Scenario", "run_c4_high_coupling_policy_shadow"]
