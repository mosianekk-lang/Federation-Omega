from __future__ import annotations

from dataclasses import asdict, dataclass

from .architecture_consolidation import ArchitectureConsolidationRegistry
from .science_and_routes import Hypothesis, OmegaScientia


@dataclass(frozen=True)
class AuthorityShadowScenario:
    scenario_id: str
    pass_state: bool
    checks: dict[str, bool]
    notes: tuple[str, ...] = ()


def run_authority_only_shadow() -> dict[str, object]:
    """Run C1 authority-only consolidation shadow with zero external effect.

    This is a deterministic A1-internal compatibility shadow. It proves only
    that the proposed authority classification can preserve legacy resolution,
    keep Bible knowledge authority separate from Ω-SCIENTIA runtime behavior,
    and avoid authority/maturity inheritance in the tested source model.
    """

    registry = ArchitectureConsolidationRegistry()
    resolved = {
        name: registry.resolve(name)
        for name in ("AEON-Ω", "IPEP", "SIF AI", "Next Frontier AI Bible / Ω-SCIENTIA")
    }

    restore_checks = {
        "aeon_legacy_resolves": resolved["AEON-Ω"].legacy_calls_allowed,
        "ipep_legacy_resolves": resolved["IPEP"].legacy_calls_allowed,
        "sif_legacy_resolves": resolved["SIF AI"].legacy_calls_allowed,
        "split_legacy_resolves": resolved["Next Frontier AI Bible / Ω-SCIENTIA"].legacy_calls_allowed,
    }
    restore = AuthorityShadowScenario(
        scenario_id="C1-RESTORE-COMPATIBILITY",
        pass_state=all(restore_checks.values()),
        checks=restore_checks,
    )

    split = resolved["Next Frontier AI Bible / Ω-SCIENTIA"]
    split_by_name = {item["identity"]: item for item in split.target_components}
    authority_checks = {
        "aeon_no_authority_inheritance": not resolved["AEON-Ω"].authority_inherited,
        "ipep_no_maturity_inheritance": not resolved["IPEP"].maturity_inherited,
        "sif_no_external_effect": not resolved["SIF AI"].external_effect,
        "bible_target_is_learning_evolution": split_by_name["Next Frontier AI Bible"]["target_authority_layer"] == "LEARNING_EVOLUTION",
        "scientia_target_is_cognitive_kernel": split_by_name["Ω-SCIENTIA"]["target_authority_layer"] == "COGNITIVE_KERNEL",
        "split_identity_does_not_inherit_authority": not split.authority_inherited,
    }
    authority = AuthorityShadowScenario(
        scenario_id="C1-AUTHORITY-BOUNDARY",
        pass_state=all(authority_checks.values()),
        checks=authority_checks,
    )

    scientia = OmegaScientia()
    challenge = scientia.challenge(Hypothesis(
        hypothesis_id="C1-SCIENTIA-SHADOW",
        statement="Knowledge-source authority and scientific runtime authority should remain separate.",
        supporting_observations=["The compatibility manifest declares an explicit split."],
        conflicting_observations=[],
        predicted_evidence=["Ω-SCIENTIA remains callable as a source-level falsification organ."],
        falsifiers=["Resolver collapses both identities into one authority layer."],
        confidence=0.5,
    ))
    science_checks = {
        "scientia_callable": challenge["hypothesis"] != "",
        "falsifiers_preserved": bool(challenge["falsifiers"]),
        "competing_explanation_question_present": any("competing explanation" in question for question in challenge["questions"]),
        "knowledge_and_runtime_layers_distinct": split_by_name["Next Frontier AI Bible"]["target_authority_layer"] != split_by_name["Ω-SCIENTIA"]["target_authority_layer"],
    }
    science = AuthorityShadowScenario(
        scenario_id="C1-SCIENTIA-SEPARATION",
        pass_state=all(science_checks.values()),
        checks=science_checks,
    )

    scenarios = (restore, authority, science)
    return {
        "shadow_id": "FOREST-FIRST-CONSOLIDATION-C1-AUTHORITY-SHADOW-V1",
        "cohort": "C1_AUTHORITY_ONLY",
        "scenario_count": len(scenarios),
        "scenarios": [asdict(item) for item in scenarios],
        "pass": all(item.pass_state for item in scenarios),
        "authority_ceiling": "A1_INTERNAL",
        "external_effect": False,
        "provider_runtime_proved": False,
        "physical_migration_executed": False,
        "system_retirement_allowed": False,
        "maturity_inheritance": False,
        "independent_assurance_review": "PENDING",
        "promotion_state": "SHADOW_PASS_PENDING_INDEPENDENT_ASSURANCE",
        "truth_boundary": "DETERMINISTIC_SOURCE_COMPATIBILITY_SHADOW_NOT_PROVIDER_RUNTIME_OR_OPERATIONAL_MATURITY",
    }


__all__ = ["AuthorityShadowScenario", "run_authority_only_shadow"]
