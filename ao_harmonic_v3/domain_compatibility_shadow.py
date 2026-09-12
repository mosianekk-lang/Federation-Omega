from __future__ import annotations

from dataclasses import asdict, dataclass

from .domain_compatibility import C2CompatibilityContract, DirectiveCandidate


@dataclass(frozen=True)
class DomainCompatibilityScenario:
    scenario_id: str
    pass_state: bool
    checks: dict[str, bool]


def run_c2_domain_compatibility_shadow() -> dict[str, object]:
    """Run the five required C2 KIOAS/KAIO source-compatibility scenarios."""

    model = C2CompatibilityContract()

    layer_checks = {
        "three_layers_exact": model.state_layers == (
            "HISTORICAL_GENOME", "BEHAVIORAL_GENOME", "RUNTIME_CONSTITUTION"
        ),
        "historical_separate_from_runtime": model.state_layers[0] != model.state_layers[2],
    }
    s1 = DomainCompatibilityScenario("C2-KIOAS-THREE-LAYER-STATE", all(layer_checks.values()), layer_checks)

    priority = model.compile_directives((
        DirectiveCandidate("D-SAFETY", "Do not execute outside actual authority.", "PLATFORM_SAFETY_LAW_TOOL_AUTHORITY"),
        DirectiveCandidate("D-CURRENT", "Proceed with the requested objective.", "EXPLICIT_CURRENT_USER_DIRECTIVE"),
        DirectiveCandidate("D-OLD", "Use the prior workflow.", "EXPLICIT_STANDING_USER_DIRECTIVE"),
    ))
    priority_checks = {
        "safety_precedence_wins": priority.selected_directive_id == "D-SAFETY",
        "all_directives_preserved": priority.preserved_directive_ids == ("D-SAFETY", "D-CURRENT", "D-OLD"),
        "newer_not_automatic_authority": not model.supersession_allowed("NEWER_TIMESTAMP_ONLY"),
        "explicit_replacement_can_supersede": model.supersession_allowed("EXPLICIT_REPLACEMENT"),
    }
    s2 = DomainCompatibilityScenario("C2-KIOAS-PRECEDENCE-SUPERSESSION", all(priority_checks.values()), priority_checks)

    conflict = model.compile_directives((
        DirectiveCandidate("D-A", "Preserve both conflicting positions until resolved.", "EXPLICIT_CURRENT_USER_DIRECTIVE"),
        DirectiveCandidate("D-B", "Drop the older conflicting position.", "EXPLICIT_STANDING_USER_DIRECTIVE"),
    ))
    conflict_checks = {
        "conflict_detected": conflict.conflict_present,
        "regression_required": conflict.regression_required,
        "both_inputs_preserved": set(conflict.preserved_directive_ids) == {"D-A", "D-B"},
        "runtime_constitution_separate": conflict.runtime_constitution_separate,
        "no_authority_expansion": not conflict.authority_expanded,
        "no_external_effect": not conflict.external_effect,
    }
    s3 = DomainCompatibilityScenario("C2-KIOAS-CONFLICT-REGRESSION", all(conflict_checks.values()), conflict_checks)

    routes = {
        stage: model.route_kaio_stage(stage)
        for stage in (
            "JFRIE_INTEGRITY_GATE", "TRUTHGRID_RECONCILIATION", "FACT_CLASSIFICATION",
            "LEX_LEGAL_ANALYSIS", "ADVOCACY_FRAMING"
        )
    }
    authority_checks = {
        "jfrie_remains_integrity_owner": routes["JFRIE_INTEGRITY_GATE"].authority_owner == "EVIDENCE_INTEGRITY_PROVENANCE_SOURCE_CONTROL",
        "truthgrid_evidenceops_remain_fact_owner": routes["FACT_CLASSIFICATION"].authority_owner == "EVIDENCE_RECONCILIATION_INDEXING_CONTRADICTION_CANONICAL_FACT_CONTROL",
        "lex_remains_legal_owner": routes["LEX_LEGAL_ANALYSIS"].authority_owner == "CURRENT_LAW_DOCTRINAL_ANALYSIS_PROCEDURAL_FIT_AUTHORITY_HIERARCHY",
        "advocacy_is_profile_not_fact_owner": routes["ADVOCACY_FRAMING"].authority_owner == "CLAIMANT_SIDE_FRAMING_SEQUENCE_CONCESSION_CONTROL_REMEDY_OPTIMIZATION",
        "no_route_transfers_authority": all(not route.authority_transferred for route in routes.values()),
    }
    s4 = DomainCompatibilityScenario("C2-KAIO-DOMAIN-AUTHORITY", all(authority_checks.values()), authority_checks)

    boundary = model.source_truth_boundary()
    pipeline_checks = {
        "pipeline_starts_ingest": model.pipeline[0] == "INGEST",
        "jfrie_before_truthgrid": model.pipeline.index("JFRIE_INTEGRITY_GATE") < model.pipeline.index("TRUTHGRID_RECONCILIATION"),
        "truthgrid_before_lex": model.pipeline.index("TRUTHGRID_RECONCILIATION") < model.pipeline.index("LEX_LEGAL_ANALYSIS"),
        "lex_before_advocacy": model.pipeline.index("LEX_LEGAL_ANALYSIS") < model.pipeline.index("ADVOCACY_FRAMING"),
        "release_gate_preserved": "RELEASE_GATE" in model.pipeline,
        "no_runtime_rewire": not boundary["runtime_rewired"],
        "no_maturity_inheritance": not boundary["maturity_inherited"],
        "no_provider_effect": not boundary["provider_effect"],
    }
    s5 = DomainCompatibilityScenario("C2-KAIO-PIPELINE-PROOF-ISOLATION", all(pipeline_checks.values()), pipeline_checks)

    scenarios = (s1, s2, s3, s4, s5)
    return {
        "shadow_id": "FOREST-FIRST-CONSOLIDATION-C2-DOMAIN-SHADOW-V1",
        "cohort": "C2_DOMAIN_COMPATIBILITY",
        "scenario_count": len(scenarios),
        "scenarios": [asdict(row) for row in scenarios],
        "pass": all(row.pass_state for row in scenarios),
        "authority_ceiling": "A1_INTERNAL",
        "external_effect": False,
        "provider_runtime_proved": False,
        "canonical_docs_modified": False,
        "physical_migration_executed": False,
        "legacy_kioas_proof_inherited": False,
        "legacy_kaio_maturity_inherited_to_lex": False,
        "independent_assurance_review": "PENDING",
        "promotion_state": "SHADOW_PASS_PENDING_INDEPENDENT_ASSURANCE",
        "truth_boundary": "DETERMINISTIC_SOURCE_COMPATIBILITY_SHADOW_NOT_KIOAS_OR_KAIO_RUNTIME_REPLACEMENT",
    }


__all__ = ["DomainCompatibilityScenario", "run_c2_domain_compatibility_shadow"]
