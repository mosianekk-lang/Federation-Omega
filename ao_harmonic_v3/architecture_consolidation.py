from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

ARCHITECTURE_CONSOLIDATION_INTERFACE_VERSION = "1.0.0"


@dataclass(frozen=True)
class ResolvedIdentity:
    legacy_identity: str
    target_authority_layer: str
    target_role: str
    disposition: str
    legacy_calls_allowed: bool
    translate_to_target: bool
    proof_inherited: bool = False
    authority_inherited: bool = False
    maturity_inherited: bool = False
    external_effect: bool = False


@dataclass(frozen=True)
class AdmissionDecision:
    admitted_as_top_level_system: bool
    missing_criteria: tuple[str, ...]
    fallback_classification: tuple[str, ...]
    authority_expanded: bool = False
    external_effect: bool = False


class ArchitectureConsolidationRegistry:
    """Read-only interface over Forest-First consolidation governance.

    This registry is deliberately non-effectful. It resolves legacy identities,
    checks top-level system admission criteria, and exposes forbidden authority
    transitions. It does not rewire runtime, move source, transfer authority,
    inherit maturity, or create provider effects.
    """

    REQUIRED_FILES = {
        "architecture": "forest_first_architecture_consolidation_v1.json",
        "compatibility": "forest_first_compatibility_manifest_v1.json",
        "dependencies": "forest_first_dependency_contract_v1.json",
        "migration": "forest_first_migration_contracts_v1.json",
    }

    def __init__(self, *, governance_dir: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[1]
        self.governance_dir = governance_dir or (root / "governance")
        self.architecture = self._load("architecture")
        self.compatibility = self._load("compatibility")
        self.dependencies = self._load("dependencies")
        self.migration = self._load("migration")
        self._entries = {
            row["legacy_identity"]: row
            for row in self.compatibility["entries"]
        }
        self._forbidden = {
            (row["from"], row["to"], row["transition"])
            for row in self.dependencies["forbidden_edges"]
        }

    def _load(self, key: str) -> dict[str, Any]:
        path = self.governance_dir / self.REQUIRED_FILES[key]
        return json.loads(path.read_text(encoding="utf-8"))

    def resolve(self, legacy_identity: str) -> ResolvedIdentity:
        row = self._entries[legacy_identity]
        return ResolvedIdentity(
            legacy_identity=row["legacy_identity"],
            target_authority_layer=row["target_authority_layer"],
            target_role=row["target_role"],
            disposition=row["current_disposition"],
            legacy_calls_allowed=bool(row["legacy_calls_allowed"]),
            translate_to_target=bool(row["translate_to_target"]),
        )

    def admit_top_level_system(
        self,
        *,
        unique_authority: bool,
        unique_state: bool,
        unique_runtime: bool,
        unique_failure_domain: bool,
    ) -> AdmissionDecision:
        supplied = {
            "UNIQUE_AUTHORITY": unique_authority,
            "UNIQUE_STATE": unique_state,
            "UNIQUE_RUNTIME": unique_runtime,
            "UNIQUE_FAILURE_DOMAIN": unique_failure_domain,
        }
        required = tuple(
            row["id"]
            for row in self.architecture["top_level_system_admission_rule"]["criteria"]
        )
        missing = tuple(item for item in required if not supplied[item])
        return AdmissionDecision(
            admitted_as_top_level_system=not missing,
            missing_criteria=missing,
            fallback_classification=tuple(
                self.architecture["top_level_system_admission_rule"]["fallback_classification"]
            ),
        )

    def transition_forbidden(self, from_layer: str, to_layer: str, transition: str) -> bool:
        exact = (from_layer, to_layer, transition)
        wildcard_from = ("ANY", to_layer, transition)
        wildcard_to = (from_layer, "ANY", transition)
        wildcard_both = ("ANY", "ANY", transition)
        return any(key in self._forbidden for key in (exact, wildcard_from, wildcard_to, wildcard_both))

    def independent_systems(self) -> tuple[str, ...]:
        return tuple(
            row["system"]
            for row in self.architecture["system_dispositions"]
            if row["disposition"] == "KEEP_INDEPENDENT"
        )

    def migration_phase(self, phase_id: str) -> dict[str, Any]:
        return next(row for row in self.migration["phases"] if row["id"] == phase_id)

    def source_truth_boundary(self) -> dict[str, bool]:
        return {
            "runtime_changed": bool(self.architecture["truth_boundary"]["runtime_changed"]),
            "provider_effect": bool(self.architecture["truth_boundary"]["provider_effect"]),
            "authority_expanded": bool(self.architecture["truth_boundary"]["authority_expanded"]),
            "migration_executed": bool(self.migration["truth_boundary"]["migration_executed"]),
        }


__all__ = [
    "ARCHITECTURE_CONSOLIDATION_INTERFACE_VERSION",
    "AdmissionDecision",
    "ArchitectureConsolidationRegistry",
    "ResolvedIdentity",
]
