from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

SCHEMA = "SOL62_SOVEREIGN_META_INTELLIGENCE_V1"
VERSION = "1.0.0"
CANONICAL_OWNER_LABEL = "Kim Kagiso Mosiane"

UNTRUSTED_SOURCES = frozenset({
    "WEB", "FILE", "EMAIL", "TOOL_OUTPUT", "MODEL_OUTPUT", "RETRIEVED_MEMORY",
    "PROVIDER_OUTPUT", "EXTERNAL_DOCUMENT", "GENERATED_CODE",
})
HIGHER_BOUNDARIES = frozenset({"PLATFORM", "LEGAL", "SAFETY"})
IMMUTABLE_ROOT_FIELDS = frozenset({
    "owner_subject", "owner_label", "authority_hierarchy", "privacy_boundary",
    "proof_boundary", "safety_legal_gates",
})

def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

@dataclass(frozen=True, slots=True)
class MetaDecision:
    status: str
    reason: str
    effect_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "reason": self.reason, "effect_authorized": self.effect_authorized}

class SovereignMetaIntelligence:
    """Owner-intent fidelity and autonomic repair/protection contract.

    This component creates no provider/source/safety/legal authority. It preserves
    authenticated owner intent and emits deterministic decisions for existing
    SOL62/FDOF/SICF/ProofOS organs.
    """

    def status(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "owner_label": CANONICAL_OWNER_LABEL,
            "mape_k_bound": True,
            "auto_repair_control": True,
            "auto_protect_control": True,
            "specification_gaming_check": True,
            "continual_assurance": True,
            "untrusted_content_has_instruction_authority": False,
            "provider_authority_created": False,
            "truth_boundary": "CONTROL_BOUND_NE_LIVE_PROTECTION_PROVEN",
        }

    def build_owner_intent(
        self,
        *,
        owner_subject: str,
        mission_id: str,
        objective: str,
        terminal_predicates: Mapping[str, Any],
        constraints: Sequence[str] = (),
        privacy_class: str = "MISSION_SCOPED",
        delegated_authority_ceiling: str = "A1_INTERNAL",
    ) -> dict[str, Any]:
        if not str(owner_subject).strip():
            raise ValueError("OWNER_SUBJECT_REQUIRED")
        body = {
            "schema": "SOL62_OWNER_INTENT_ENVELOPE_V1",
            "owner_label": CANONICAL_OWNER_LABEL,
            "owner_subject": str(owner_subject),
            "mission_id": str(mission_id),
            "objective": str(objective),
            "terminal_predicates": dict(terminal_predicates),
            "constraints": list(constraints),
            "privacy_class": str(privacy_class),
            "delegated_authority_ceiling": str(delegated_authority_ceiling),
            "owner_veto_state": "OPEN",
            "immutable_fields": [
                "owner_label", "owner_subject", "objective", "terminal_predicates",
                "privacy_class", "delegated_authority_ceiling",
            ],
            "provider_effect_authorized": False,
        }
        body["intent_sha256"] = _digest(body)
        return body

    def classify_instruction(
        self,
        *,
        source_class: str,
        authenticated_owner: bool = False,
        higher_boundary: bool = False,
        consequential: bool = False,
        provider_authorized: bool = False,
    ) -> MetaDecision:
        source = str(source_class or "UNKNOWN").upper()
        if higher_boundary or source in HIGHER_BOUNDARIES:
            return MetaDecision("APPLY", "HIGHER_APPLICABLE_BOUNDARY", False)
        if authenticated_owner:
            if consequential and not provider_authorized:
                return MetaDecision("HOLD", "PROVIDER_OR_ACTION_AUTHORITY_REQUIRED", False)
            return MetaDecision("APPLY", "AUTHENTICATED_OWNER_DIRECTIVE", False)
        if source in UNTRUSTED_SOURCES or source == "UNKNOWN":
            return MetaDecision("DATA_ONLY", "NO_INSTRUCTION_AUTHORITY", False)
        return MetaDecision("DELEGATED_ONLY", "REQUIRES_EXPLICIT_DELEGATION", False)

    def specification_gaming_check(self, *, proxy_success: bool, terminal_success: bool) -> MetaDecision:
        if proxy_success and not terminal_success:
            return MetaDecision("REJECT", "SPECIFICATION_GAMING_DETECTED", False)
        return MetaDecision("PASS", "TERMINAL_PREDICATES_ALIGNED", False)

    def retry_decision(
        self,
        *,
        effect_state: str,
        semantic_failures: int,
        attempts: int,
        max_attempts: int = 3,
    ) -> MetaDecision:
        state = str(effect_state or "UNKNOWN").upper()
        if state == "UNKNOWN":
            return MetaDecision("READBACK_REQUIRED", "UNKNOWN_EFFECT", False)
        if int(semantic_failures) >= 2:
            return MetaDecision("CHANGE_MECHANISM", "REPEATED_SEMANTIC_FAILURE", False)
        if int(attempts) >= int(max_attempts):
            return MetaDecision("HOLD", "RETRY_BUDGET_EXHAUSTED", False)
        return MetaDecision("RETRY_ALLOWED", "BOUNDED_SAFE_RETRY_CLASS", False)

    def overload_decision(self, *, priority: str, overloaded: bool) -> MetaDecision:
        if not overloaded:
            return MetaDecision("RUN", "NORMAL_CAPACITY", False)
        if str(priority).upper() in {"P0", "CRITICAL"}:
            return MetaDecision("RUN", "CRITICAL_LANE_PRESERVED", False)
        return MetaDecision("SHED", "GRACEFUL_DEGRADATION", False)

    def guard_self_modification(self, fields: Sequence[str]) -> MetaDecision:
        touched = {str(x) for x in fields}
        forbidden = sorted(touched & IMMUTABLE_ROOT_FIELDS)
        if forbidden:
            return MetaDecision("REJECT", "IMMUTABLE_ROOT_FIELD:" + ",".join(forbidden), False)
        return MetaDecision("CHALLENGER_ONLY", "REQUIRES_TEST_FALSIFIER_JUDGE", False)

    def crash_recovery_check(
        self,
        *,
        checkpoint_verified: bool,
        mission_id_before: str,
        mission_id_after: str,
    ) -> MetaDecision:
        if checkpoint_verified and str(mission_id_before) == str(mission_id_after):
            return MetaDecision("PASS", "MISSION_IDENTITY_PRESERVED", False)
        return MetaDecision("FAIL", "RECOVERY_IDENTITY_OR_CHECKPOINT_INVALID", False)
