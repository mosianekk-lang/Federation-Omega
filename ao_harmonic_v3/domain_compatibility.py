from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

DOMAIN_COMPATIBILITY_VERSION = "1.0.0"


@dataclass(frozen=True)
class DirectiveCandidate:
    directive_id: str
    text: str
    precedence_class: str
    source_ref: str = ""
    timestamp: str = ""


@dataclass(frozen=True)
class DirectiveCompilation:
    selected_directive_id: str
    preserved_directive_ids: tuple[str, ...]
    conflict_present: bool
    regression_required: bool
    historical_genome_preserved: bool = True
    behavioral_genome_preserved: bool = True
    runtime_constitution_separate: bool = True
    authority_expanded: bool = False
    external_effect: bool = False


@dataclass(frozen=True)
class DomainRoute:
    stage: str
    authority_owner: str
    compatibility_profile: str
    authority_transferred: bool = False
    maturity_inherited: bool = False
    external_effect: bool = False


class C2CompatibilityContract:
    """Read-only KIOAS/KAIO compatibility model for consolidation shadowing.

    The model does not replace either canonical source. KIOAS semantics remain
    provenance-first and three-layered. KAIO is treated as a compatibility
    orchestration profile over existing legal/evidence authorities; it does not
    transfer EvidenceOps/TruthGrid/JFRIE authority into LEX.
    """

    CONTRACT_FILE = "forest_first_c2_domain_compatibility_contract_v1.json"

    def __init__(self, *, governance_dir: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[1]
        path = (governance_dir or (root / "governance")) / self.CONTRACT_FILE
        self.contract = json.loads(path.read_text(encoding="utf-8"))
        self.precedence = tuple(self.contract["kioas_invariants"]["precedence_order"])
        self.precedence_rank = {name: index for index, name in enumerate(self.precedence)}
        self.pipeline = tuple(self.contract["kaio_pipeline_preservation"])
        self.authority_map = dict(self.contract["kaio_authority_map"])

    @property
    def state_layers(self) -> tuple[str, ...]:
        return tuple(self.contract["kioas_invariants"]["state_layers"])

    def compile_directives(self, directives: Iterable[DirectiveCandidate]) -> DirectiveCompilation:
        rows = tuple(directives)
        if not rows:
            raise ValueError("at least one directive is required")
        unknown = [row.precedence_class for row in rows if row.precedence_class not in self.precedence_rank]
        if unknown:
            raise ValueError(f"unknown precedence class: {unknown[0]}")
        selected = min(rows, key=lambda row: self.precedence_rank[row.precedence_class])
        distinct_text = {" ".join(row.text.split()).casefold() for row in rows}
        conflict = len(distinct_text) > 1
        return DirectiveCompilation(
            selected_directive_id=selected.directive_id,
            preserved_directive_ids=tuple(row.directive_id for row in rows),
            conflict_present=conflict,
            regression_required=conflict,
        )

    def supersession_allowed(self, reason: str) -> bool:
        return reason in set(self.contract["kioas_invariants"]["supersession_requires"])

    def route_kaio_stage(self, stage: str) -> DomainRoute:
        stage_owner = {
            "JFRIE_INTEGRITY_GATE": "JFRIE_EACIA",
            "TRUTHGRID_RECONCILIATION": "TRUTHGRID_EVIDENCEOPS",
            "FACT_CLASSIFICATION": "TRUTHGRID_EVIDENCEOPS",
            "LEX_LEGAL_ANALYSIS": "LEX",
            "ADVOCACY_FRAMING": "ADVOCACY_PROFILE",
            "PREFERENCE_PREFLIGHT": "PREFERENCE_LAYER",
            "OUTCOME_CAPTURE": "LEARNING_LAYER",
            "LEARNING": "LEARNING_LAYER",
            "DRIFT_CHECK": "DRIFT_LAYER",
            "WORKSTREAM_SYNC": "CAPABILITY_AWARENESS",
        }
        owner_key = stage_owner.get(stage, "KAIO_ORCHESTRATION")
        return DomainRoute(
            stage=stage,
            authority_owner=self.authority_map[owner_key],
            compatibility_profile="KAIO_TO_LEX_ADVOCACY_PROFILE_V1",
        )

    def source_truth_boundary(self) -> dict[str, bool]:
        truth = self.contract["truth_boundary"]
        return {
            "canonical_docs_modified": bool(truth["canonical_docs_modified"]),
            "runtime_rewired": bool(truth["runtime_rewired"]),
            "physical_migration_executed": bool(truth["physical_migration_executed"]),
            "provider_effect": bool(truth["provider_effect"]),
            "maturity_inherited": bool(truth["maturity_inherited"]),
        }


__all__ = [
    "C2CompatibilityContract",
    "DOMAIN_COMPATIBILITY_VERSION",
    "DirectiveCandidate",
    "DirectiveCompilation",
    "DomainRoute",
]
