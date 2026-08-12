from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping

from .claim_guard import ClaimGuard
from .demo_journey_guard import DemoJourneyGuard


@dataclass(frozen=True)
class PortfolioEntry:
    project_id: str
    evidence_state: str
    strongest_safe_claim: str
    verified_proofs: tuple[str, ...]
    evidence_pointers: tuple[str, ...]
    demo_state: str
    limitations: tuple[str, ...]
    next_proof: str
    provider_verified: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ShowcasePack:
    def __init__(self, claims: ClaimGuard, demos: DemoJourneyGuard):
        self.claims = claims
        self.demos = demos

    @classmethod
    def load(cls) -> "ShowcasePack":
        return cls(ClaimGuard.load(), DemoJourneyGuard.load())

    def _demo_state(self, project_id: str) -> str:
        by_project = [j for j in self.demos.journeys.values() if j["project_id"] == project_id]
        if not by_project:
            return "NO_DEMO_CONTRACT"
        states = {str(j["execution_state"]) for j in by_project}
        if "DESIGN_VALIDATED_EXECUTION_PENDING" in states:
            return "DESIGN_VALIDATED_EXECUTION_PENDING"
        if "LOCAL_RUNTIME_READY" in states:
            return "LOCAL_RUNTIME_DEMO_READY"
        return sorted(states)[0]

    def entry(self, project_id: str) -> PortfolioEntry:
        project = self.claims.project(project_id)
        return PortfolioEntry(
            project_id=project_id,
            evidence_state=str(project["evidence_state"]),
            strongest_safe_claim=str(project["strongest_safe_claim"]),
            verified_proofs=tuple(str(item) for item in project.get("verified_proofs", [])),
            evidence_pointers=tuple(str(item) for item in project.get("evidence_pointers", [])),
            demo_state=self._demo_state(project_id),
            limitations=tuple(str(item) for item in project.get("forbidden_stronger_claims", [])),
            next_proof=str(project["next_proof"]),
            provider_verified=bool(project.get("provider_verified")),
        )

    def manifest(self) -> dict[str, Any]:
        order = ("CIOS", "ECERTIFY", "CASEFORGE", "IPEP", "ARCHITRON", "K10")
        entries = [self.entry(project_id).to_dict() for project_id in order]
        return {
            "schema": "BUBBLES-SHOWCASE-PORTFOLIO-V1",
            "title": "Kim Kagiso Mosiane — Applied AI Systems Architect Demonstrable Portfolio",
            "entry_count": len(entries),
            "entries": entries,
            "portfolio_state": "INTERNAL_PROOF_PACK_READY_EXTERNAL_PROOFS_PENDING",
            "truth_boundary": (
                "This pack exposes only Ledger-approved claims and evidence pointers. It does not convert "
                "provider-unverified projects into deployed systems, deterministic benchmark results into model "
                "accuracy claims, or design-validated demos into rendered/exported artifacts."
            ),
        }

    def write_manifest(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.manifest(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target

    def validate_public_claim(self, project_id: str, requested_state: str, text: str) -> dict[str, Any]:
        maturity = self.claims.decide(project_id, requested_state)
        safe_text, forbidden_hits = self.claims.validate_text(project_id, text)
        return {
            "allowed": maturity.allowed and safe_text,
            "maturity_allowed": maturity.allowed,
            "text_allowed": safe_text,
            "forbidden_hits": list(forbidden_hits),
            "strongest_safe_claim": maturity.strongest_safe_claim,
            "evidence_state": maturity.evidence_state,
        }
