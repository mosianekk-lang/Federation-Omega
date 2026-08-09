from __future__ import annotations

from dataclasses import dataclass


class AttributionFirewallError(ValueError):
    pass


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    theory: str
    required_atoms: tuple[str, ...]
    proved_atoms: tuple[str, ...] = ()
    adverse_evidence_searched: bool = False
    counterfactual_tested: bool = False
    search_exhausted: bool = False

    @property
    def unresolved_atoms(self) -> tuple[str, ...]:
        proved = set(self.proved_atoms)
        return tuple(atom for atom in self.required_atoms if atom not in proved)

    @property
    def ready(self) -> bool:
        return not self.unresolved_atoms and self.adverse_evidence_searched and self.counterfactual_tested and self.search_exhausted


def validate_personal_attribution(*, observed_subject: str, asserted_personal_actor: str | None, assignment_source_ids: tuple[str, ...] = (), actor_identity_source_ids: tuple[str, ...] = ()) -> None:
    if asserted_personal_actor is None:
        return
    lower = observed_subject.lower()
    system_like = any(token in lower for token in ("account", "device", "credential", "system", "workflow"))
    if system_like and not actor_identity_source_ids:
        raise AttributionFirewallError("PERSONAL_ACTOR_REQUIRES_SEPARATE_IDENTITY_EVIDENCE")
    organisational = any(token in lower for token in ("department", "unit", "strategy", "objective", "service"))
    if organisational and not assignment_source_ids:
        raise AttributionFirewallError("PERSONAL_DUTY_REQUIRES_ASSIGNMENT_SOURCE")
