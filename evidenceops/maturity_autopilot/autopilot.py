from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .model import CapabilityEvidence, MaturityLevel


@dataclass(frozen=True)
class MaturityAction:
    capability_id: str
    derived_level: MaturityLevel
    claimed_level: MaturityLevel
    gate_id: str | None
    action: str
    priority: float
    blocked_external: bool
    blocker: str | None
    downgrade_required: bool


class MaturityAutopilot:
    """Evidence-derived portfolio maturity controller.

    It may recommend and execute only bounded A1/internal work. Provider,
    destructive, consequential, filing, financial or publication actions remain
    outside this class and require their own authority and target-specific proof.
    """

    def assess(self, capability: CapabilityEvidence) -> MaturityAction:
        derived = capability.derived_level()
        missing = capability.next_missing_gate()
        drift = capability.claimed_level > derived

        if capability.retired:
            return MaturityAction(
                capability.capability_id,
                derived,
                capability.claimed_level,
                None,
                "preserve retirement and migration proof; do not reactivate implicitly",
                0.0,
                False,
                None,
                drift,
            )

        if drift:
            action = f"downgrade maturity claim to {derived.name} and close missing proof before promotion"
            priority = 1000.0 + float(capability.claimed_level - derived) * 50.0
        elif capability.blocked_external:
            action = "preserve exact external blocker, safe fallback and next provider-native proof route"
            priority = 700.0
        elif missing is None:
            action = "maintain M11 recertification; watch proof expiry, drift and regression"
            priority = 100.0
        else:
            action = f"close gate {missing.gate_id}: obtain {missing.proof_type}"
            priority = 500.0 + (11.0 - float(derived)) * 10.0

        return MaturityAction(
            capability.capability_id,
            derived,
            capability.claimed_level,
            missing.gate_id if missing else None,
            action,
            priority,
            capability.blocked_external,
            capability.blocker,
            drift,
        )

    def rank(self, capabilities: Iterable[CapabilityEvidence]) -> list[MaturityAction]:
        actions = [self.assess(capability) for capability in capabilities]
        return sorted(actions, key=lambda a: (-a.priority, a.capability_id))

    def portfolio_state(self, capabilities: Iterable[CapabilityEvidence]) -> dict[str, object]:
        items = list(capabilities)
        actions = self.rank(items)
        counts = {level.name: 0 for level in MaturityLevel}
        for capability in items:
            counts[capability.derived_level().name] += 1
        return {
            "schema": "EVIDENCEOPS_MATURITY_AUTOPILOT_STATE_V1",
            "capability_count": len(items),
            "derived_maturity_counts": counts,
            "drift_count": sum(1 for action in actions if action.downgrade_required),
            "external_blocker_count": sum(1 for action in actions if action.blocked_external),
            "next_actions": [
                {
                    "capability_id": action.capability_id,
                    "derived_level": action.derived_level.name,
                    "claimed_level": action.claimed_level.name,
                    "gate_id": action.gate_id,
                    "action": action.action,
                    "priority": action.priority,
                    "blocked_external": action.blocked_external,
                    "blocker": action.blocker,
                    "downgrade_required": action.downgrade_required,
                }
                for action in actions
            ],
        }
