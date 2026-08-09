from __future__ import annotations

from dataclasses import dataclass

from .models import EvidenceItem, EvidenceState


@dataclass(frozen=True)
class ImmuneFinding:
    code: str
    severity: str
    message: str


class CognitiveImmuneSystem:
    """Detect common epistemic contamination patterns before promotion."""

    def scan_evidence(self, items: tuple[EvidenceItem, ...]) -> tuple[ImmuneFinding, ...]:
        findings: list[ImmuneFinding] = []

        by_lineage: dict[str, list[EvidenceItem]] = {}
        for item in items:
            by_lineage.setdefault(item.independent_lineage, []).append(item)

        for lineage, members in by_lineage.items():
            if len(members) > 1:
                findings.append(
                    ImmuneFinding(
                        code="DERIVATIVE_CORROBORATION",
                        severity="HIGH",
                        message=(
                            f"{len(members)} evidence items share lineage '{lineage}'; "
                            "they may not be counted as independent corroboration."
                        ),
                    )
                )

        for item in items:
            if item.state in {EvidenceState.INFERENCE, EvidenceState.UNVERIFIED} and item.reliability >= 0.9:
                findings.append(
                    ImmuneFinding(
                        code="CERTAINTY_INFLATION",
                        severity="HIGH",
                        message=f"{item.id} has high reliability metadata despite state={item.state.value}.",
                    )
                )
            if not item.source_identity.strip():
                findings.append(
                    ImmuneFinding(
                        code="MISSING_SOURCE_IDENTITY",
                        severity="CRITICAL",
                        message=f"{item.id} has no source identity.",
                    )
                )

        return tuple(findings)

    def promotion_allowed(self, items: tuple[EvidenceItem, ...]) -> bool:
        critical = {"MISSING_SOURCE_IDENTITY"}
        return not any(f.code in critical for f in self.scan_evidence(items))
