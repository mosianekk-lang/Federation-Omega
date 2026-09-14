from __future__ import annotations

from dataclasses import dataclass

FORMATION_ENGINE_COMPATIBILITY_VERSION = "1.0.0"

REQUIRED_PUBLIC_API = (
    "AAAError",
    "AAACycleReport",
    "AutonomicMissionFabric",
    "CapabilityCentrality",
    "ChangeCapsule",
    "ClosureLock",
    "ConstitutionKernel",
    "CounterfactualPlanner",
    "EvidenceWeightedCouncil",
    "FederatedCognitiveInstitution",
    "FormationOmega",
    "FractalDelegationGuard",
    "InstitutionalImmuneSystem",
    "InstitutionalMemory",
    "MissionConvergenceEngine",
    "MissionDeduplicator",
    "MissionGenesisEngine",
    "MissionSpec",
    "MissionSwarmPlanner",
    "MonotonicClosureGate",
    "MultiTimescalePlanner",
    "PolicyEvolutionLab",
    "PortfolioAllocator",
    "ProofDirectedScheduler",
    "ProofState",
    "RecursiveImprovementGate",
    "ReleaseGate",
    "RobustScenarioPlanner",
    "SourceConvergenceClass",
    "StrategicGenomeLibrary",
    "StrategicObjectiveEcology",
    "SurfaceReadback",
    "classify_convergence",
    "choose_operational_route",
    "resolve_current_truth",
)

BEHAVIOR_AXES = (
    "PUBLIC_API_FREEZE",
    "MISSION_CONVERGENCE",
    "PROOF_CLOSURE",
    "AUTONOMIC_AUTHORITY",
    "INDEPENDENT_WITNESS",
    "MONOTONIC_CLOSURE",
    "SOURCE_CONVERGENCE",
    "RECONCILIATION",
    "STRATEGIC_ECOLOGY",
    "AUTHORITY_IDENTITY",
)


@dataclass(frozen=True)
class FormationEngineDisposition:
    legacy_identity: str = "FORMATION-OMEGA Unified Powerhouse"
    canonical_identity: str = "Formation"
    target_authority_layer: str = "MISSION_EXECUTION"
    target_role: str = "Formation planning/route/build compiler and mission-execution engine"
    keep_as_engine: bool = True
    sovereign_cognitive_authority: bool = False
    proof_inherited: bool = False
    authority_inherited: bool = False
    maturity_inherited: bool = False
    external_effect: bool = False
    physical_migration_executed: bool = False
    system_retirement_allowed: bool = False


def formation_engine_disposition() -> FormationEngineDisposition:
    return FormationEngineDisposition()


def public_api_status(exported_names: object, module: object) -> dict[str, object]:
    exported = set(exported_names)
    missing_exports = tuple(sorted(set(REQUIRED_PUBLIC_API) - exported))
    missing_attributes = tuple(
        sorted(name for name in REQUIRED_PUBLIC_API if not hasattr(module, name))
    )
    return {
        "required_count": len(REQUIRED_PUBLIC_API),
        "missing_exports": missing_exports,
        "missing_attributes": missing_attributes,
        "public_api_preserved": not missing_exports and not missing_attributes,
        "authority_expanded": False,
        "external_effect": False,
    }


__all__ = [
    "BEHAVIOR_AXES",
    "FORMATION_ENGINE_COMPATIBILITY_VERSION",
    "FormationEngineDisposition",
    "REQUIRED_PUBLIC_API",
    "formation_engine_disposition",
    "public_api_status",
]
