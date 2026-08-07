from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteGene:
    fingerprint: str
    classification: str
    smallest_safe_repair: str
    regression_rule: str


class FailureToRouteGeneCompiler:
    """Turns repeated operational failure fingerprints into deterministic repair genes."""

    RULES = (
        ("range exceeds grid", "PROVIDER_GRID_BOUNDARY", "BOUND_REQUEST_TO_PROVIDER_GRID", "Never request spreadsheet rows beyond provider-reported grid bounds."),
        ("could not resolve host", "NATIVE_NETWORK_UNAVAILABLE", "USE_AUTHENTICATED_CONNECTOR_ROUTE", "Circuit-break native network retry and use an already-authorised connector."),
        ("default-deny admission", "WORKFLOW_DEFAULT_DENY", "PRESERVE_EXECUTION_PLANE_SEPARATION", "Do not add an unallowlisted public workflow; use the private execution plane."),
        ("fork collab can only be enabled", "SAME_REPO_PR_METADATA_CONTRACT", "OMIT_FORK_ONLY_PR_FIELD", "Do not send maintainer_can_modify when updating same-repository pull requests."),
    )

    def compile(self, message: str) -> RouteGene:
        normalized = message.lower()
        for needle, classification, repair, regression in self.RULES:
            if needle in normalized:
                return RouteGene(needle.upper().replace(" ", "_"), classification, repair, regression)
        return RouteGene("UNKNOWN_FAILURE", "UNCLASSIFIED", "PRESERVE_EVIDENCE_AND_FORM_NEW_ROUTE", "Do not repeat an unchanged failing route without new information.")
