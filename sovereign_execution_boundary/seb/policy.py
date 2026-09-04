from __future__ import annotations

from hashlib import sha256
import json

from .models import MissionIR, PolicyDecision
from .adapters import AdapterUnavailable, OpaHttpAdapter


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


class OpaPolicyEngine:
    """Fail-closed production PDP backed by an OPA decision endpoint."""

    def __init__(self, adapter: OpaHttpAdapter, *, max_authority: str = "A2",
                 allow_external_effects: bool = False):
        if max_authority not in {f"A{i}" for i in range(6)}:
            raise ValueError("unknown maximum authority class")
        self.adapter = adapter
        self.max_authority = max_authority
        self.allow_external_effects = allow_external_effects

    def evaluate(self, mission: MissionIR, *, tool: str | None = None,
                 external_effect: bool = False) -> PolicyDecision:
        mission.validate()
        input_document = {
            "mission": {
                "fingerprint": mission.fingerprint,
                "authority_class": mission.authority_class,
                "data_class": mission.data_class,
                "allowed_tools": list(mission.allowed_tools),
                "prohibited_effects": list(mission.prohibited_effects),
            },
            "request": {"tool": tool, "external_effect": external_effect},
            "runtime": {
                "max_authority": self.max_authority,
                "allow_external_effects": self.allow_external_effects,
            },
        }
        try:
            decision = self.adapter.decide(input_document)
        except AdapterUnavailable as exc:
            digest = sha256(json.dumps(input_document, sort_keys=True,
                                       separators=(",", ":")).encode()).hexdigest()
            return PolicyDecision(False, "opa_unavailable_or_invalid", f"opa-deny-{digest}")
        result = decision.raw["result"]
        reasons = result["reasons"]
        return PolicyDecision(decision.allowed, ";".join(reasons) or "allowed",
                              self.adapter.decision_digest(input_document, decision.raw))
