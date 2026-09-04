from __future__ import annotations

from hashlib import sha256
import json

from .models import MissionIR, PolicyDecision


class PolicyEngine:
    """Deterministic in-process PDP; replaceable by an OPA adapter."""

    def __init__(self, max_authority: str = "A2", allow_external_effects: bool = False):
        self.max_authority = max_authority
        self.allow_external_effects = allow_external_effects

    def evaluate(self, mission: MissionIR, *, tool: str | None = None,
                 external_effect: bool = False) -> PolicyDecision:
        mission.validate()
        reasons: list[str] = []
        if int(mission.authority_class[1]) > int(self.max_authority[1]):
            reasons.append("authority_exceeds_runtime")
        if external_effect and not self.allow_external_effects:
            reasons.append("external_effects_disabled")
        if tool and tool not in mission.allowed_tools:
            reasons.append("tool_not_allowed")
        if tool and tool in mission.prohibited_effects:
            reasons.append("effect_explicitly_prohibited")
        if mission.data_class == "secret" and tool == "openrouter":
            reasons.append("secret_data_external_route_denied")
        body = {"mission": mission.fingerprint, "tool": tool, "external_effect": external_effect,
                "reasons": reasons}
        decision_id = sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        return PolicyDecision(not reasons, ";".join(reasons) or "allowed", decision_id)

