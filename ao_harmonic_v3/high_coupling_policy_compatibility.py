from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

C4_POLICY_COMPATIBILITY_VERSION = "1.0.0"


@dataclass(frozen=True)
class C4AuthorityBoundary:
    superior_logic_target: str
    caseforge_target: str
    evidence_truth_owner: str
    provider_effect_owner: str
    independent_assurance_owner: str
    authority_transferred: bool = False
    maturity_inherited: bool = False
    external_effect: bool = False


class C4HighCouplingPolicyContract:
    """Read-only C4 compatibility model for Superior Logic × CASEFORGE.

    This object describes target authority and source lineage only. It never moves
    source, rewires either runtime, promotes maturity, calls a provider or creates
    an external effect.
    """

    CONTRACT_FILE = "ao_harmonic_forest_first_c4_high_coupling_policy_contract_v1.json"

    def __init__(self, *, governance_dir: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[1]
        path = (governance_dir or (root / "governance")) / self.CONTRACT_FILE
        self.contract: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    @property
    def required_scenarios(self) -> tuple[str, ...]:
        return tuple(self.contract["required_scenarios"])

    @property
    def source_bindings(self) -> dict[str, dict[str, Any]]:
        return {key: dict(value) for key, value in self.contract["source_bindings"].items()}

    def authority_boundary(self) -> C4AuthorityBoundary:
        target = self.contract["target_relationship"]
        authority = self.contract["authority_map"]
        return C4AuthorityBoundary(
            superior_logic_target=target["Superior Logic Doctrine"]["target_role"],
            caseforge_target=target["CASEFORGE-Ω"]["target_role"],
            evidence_truth_owner=authority["evidence_truth_and_release_integrity"],
            provider_effect_owner=authority["provider_or_external_effect"],
            independent_assurance_owner=authority["independent_assurance"],
        )

    def source_truth_boundary(self) -> dict[str, bool]:
        return {key: bool(value) for key, value in self.contract["truth_boundary"].items()}

    def forbidden(self, transition: str) -> bool:
        return transition in set(self.contract["forbidden_transitions"])

    def rollback_contract(self) -> dict[str, Any]:
        return dict(self.contract["rollback"])


__all__ = [
    "C4AuthorityBoundary",
    "C4HighCouplingPolicyContract",
    "C4_POLICY_COMPATIBILITY_VERSION",
]
