from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_CROSSWALK = ROOT / "claim_proof_crosswalk.json"


@dataclass(frozen=True)
class ClaimDecision:
    allowed: bool
    project_id: str
    evidence_state: str
    requested_state: str
    strongest_safe_claim: str
    reason: str


class ClaimGuard:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.order = tuple(str(item) for item in payload["maturity_order"])
        if len(self.order) != len(set(self.order)):
            raise ValueError("maturity_order must contain unique states")
        self.rank = {state: index for index, state in enumerate(self.order)}
        self.projects = {str(item["project_id"]): item for item in payload["projects"]}
        if len(self.projects) != len(payload["projects"]):
            raise ValueError("project IDs must be unique")
        for project in self.projects.values():
            state = str(project["evidence_state"])
            if state not in self.rank:
                raise ValueError(f"unknown evidence state: {state}")
            if bool(project.get("provider_verified")) and self.rank[state] < self.rank["PROVIDER_VERIFIED"]:
                raise ValueError("provider_verified cannot be true below PROVIDER_VERIFIED")

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CROSSWALK) -> "ClaimGuard":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def project(self, project_id: str) -> dict[str, Any]:
        try:
            return dict(self.projects[project_id])
        except KeyError as exc:
            raise KeyError(f"unknown project: {project_id}") from exc

    def decide(self, project_id: str, requested_state: str) -> ClaimDecision:
        project = self.project(project_id)
        evidence_state = str(project["evidence_state"])
        if requested_state not in self.rank:
            return ClaimDecision(
                False,
                project_id,
                evidence_state,
                requested_state,
                str(project["strongest_safe_claim"]),
                "UNKNOWN_REQUESTED_MATURITY_STATE",
            )
        allowed = self.rank[requested_state] <= self.rank[evidence_state]
        return ClaimDecision(
            allowed,
            project_id,
            evidence_state,
            requested_state,
            str(project["strongest_safe_claim"]),
            "WITHIN_VERIFIED_SCOPE" if allowed else "REQUEST_EXCEEDS_VERIFIED_SCOPE",
        )

    def validate_text(self, project_id: str, claim: str) -> tuple[bool, tuple[str, ...]]:
        project = self.project(project_id)
        normalized = claim.casefold()
        hits = tuple(
            forbidden
            for forbidden in project.get("forbidden_stronger_claims", [])
            if str(forbidden).casefold() in normalized
        )
        return (not hits, hits)

    def public_record(self, project_id: str) -> dict[str, Any]:
        project = self.project(project_id)
        return {
            "project_id": project_id,
            "evidence_state": project["evidence_state"],
            "verified_proofs": list(project.get("verified_proofs", [])),
            "strongest_safe_claim": project["strongest_safe_claim"],
            "next_proof": project["next_proof"],
            "provider_verified": bool(project.get("provider_verified")),
            "truth_boundary": self.payload["truth_boundary"],
        }
