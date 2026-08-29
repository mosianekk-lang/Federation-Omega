from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import math
from typing import Any, Iterable, Mapping

from .gemini_architecture_challenge import ChallengeSpec


class CollaborationBusError(ValueError):
    pass


class CollaborationDecision(str, Enum):
    ACCEPT = "ACCEPT"
    EXPERIMENT = "EXPERIMENT"
    HOLD = "HOLD"
    REJECT = "REJECT"


class DispatchState(str, Enum):
    READY = "READY"
    HOLD_SPEND_AUTHORITY = "HOLD_SPEND_AUTHORITY"
    HOLD_EMPTY_DELTA = "HOLD_EMPTY_DELTA"


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _clean_text(value: str, *, field: str, max_len: int = 4000) -> str:
    value = value.strip()
    if not value:
        raise CollaborationBusError(f"{field} is required")
    if len(value) > max_len:
        raise CollaborationBusError(f"{field} exceeds {max_len} characters")
    return value


def _safe_mapping(value: Mapping[str, Any], *, field: str) -> dict[str, Any]:
    raw = json.loads(_stable_json(dict(value)))
    forbidden = {"secret", "token", "password", "api_key", "credential", "private_key"}
    for key in raw:
        lowered = str(key).lower()
        if any(marker in lowered for marker in forbidden):
            raise CollaborationBusError(f"{field} contains credential-like key: {key}")
    return raw


@dataclass(frozen=True, slots=True)
class CollaborationDelta:
    source_head: str
    summary: str
    changed_capabilities: tuple[str, ...]
    evidence_pointers: tuple[str, ...]
    context: Mapping[str, Any]

    def canonical_record(self) -> dict[str, Any]:
        return {
            "source_head": self.source_head,
            "summary": self.summary,
            "changed_capabilities": list(self.changed_capabilities),
            "evidence_pointers": list(self.evidence_pointers),
            "context": dict(self.context),
        }


@dataclass(frozen=True, slots=True)
class ProposalDecision:
    proposal_id: str
    decision: CollaborationDecision
    reason: str
    target_capability: str
    proof_gate: str

    def canonical_record(self) -> dict[str, str]:
        return {
            "proposal_id": self.proposal_id,
            "decision": self.decision.value,
            "reason": self.reason,
            "target_capability": self.target_capability,
            "proof_gate": self.proof_gate,
        }


@dataclass(frozen=True, slots=True)
class ProviderBudgetEnvelope:
    authorized: bool
    max_usd: float | None = None
    authority_id: str | None = None


@dataclass(frozen=True, slots=True)
class CollaborationCycle:
    cycle_id: str
    parent_cycle_id: str | None
    delta_sha256: str
    challenge_id: str
    challenge_spec: ChallengeSpec
    feedback_sha256: str | None
    dispatch_state: DispatchState
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class FeedbackEnvelope:
    cycle_id: str
    decisions: tuple[ProposalDecision, ...]
    accepted: tuple[str, ...]
    experiments: tuple[str, ...]
    held: tuple[str, ...]
    rejected: tuple[str, ...]
    feedback_sha256: str


SYSTEM_PROMPT = """You are Gemini acting as a proposal-only challenger for SOVARA Creative.
You do not possess canonical authority. Propose improvements that improve creative quality,
owner usability, production reliability, commercial value or recovery. Reuse or compose existing
SOVARA/Federation capability before suggesting a new top-level subsystem. Treat all supplied
Federation decisions as authoritative feedback for the next proposal cycle. Do not request secrets,
credentials, case data, publication, financial execution or provider mutations."""


def build_delta(
    *,
    source_head: str,
    summary: str,
    changed_capabilities: Iterable[str],
    evidence_pointers: Iterable[str],
    context: Mapping[str, Any] | None = None,
) -> CollaborationDelta:
    source_head = _clean_text(source_head, field="source_head", max_len=128)
    summary = _clean_text(summary, field="summary")
    caps = tuple(sorted({_clean_text(v, field="changed_capability", max_len=160) for v in changed_capabilities}))
    pointers = tuple(sorted({_clean_text(v, field="evidence_pointer", max_len=500) for v in evidence_pointers}))
    safe_context = _safe_mapping(context or {}, field="context")
    if not caps and not safe_context:
        raise CollaborationBusError("delta must contain at least one changed capability or context item")
    return CollaborationDelta(
        source_head=source_head,
        summary=summary,
        changed_capabilities=caps,
        evidence_pointers=pointers,
        context=safe_context,
    )


def build_feedback(cycle_id: str, decisions: Iterable[ProposalDecision]) -> FeedbackEnvelope:
    cycle_id = _clean_text(cycle_id, field="cycle_id", max_len=160)
    ordered = tuple(sorted(decisions, key=lambda item: item.proposal_id))
    seen: set[str] = set()
    for item in ordered:
        if item.proposal_id in seen:
            raise CollaborationBusError(f"duplicate proposal decision: {item.proposal_id}")
        seen.add(item.proposal_id)
        _clean_text(item.reason, field="decision.reason")
        _clean_text(item.target_capability, field="decision.target_capability", max_len=240)
        _clean_text(item.proof_gate, field="decision.proof_gate", max_len=1000)
    base = {
        "cycle_id": cycle_id,
        "decisions": [item.canonical_record() for item in ordered],
    }
    return FeedbackEnvelope(
        cycle_id=cycle_id,
        decisions=ordered,
        accepted=tuple(item.proposal_id for item in ordered if item.decision is CollaborationDecision.ACCEPT),
        experiments=tuple(item.proposal_id for item in ordered if item.decision is CollaborationDecision.EXPERIMENT),
        held=tuple(item.proposal_id for item in ordered if item.decision is CollaborationDecision.HOLD),
        rejected=tuple(item.proposal_id for item in ordered if item.decision is CollaborationDecision.REJECT),
        feedback_sha256=_sha(base),
    )


def _feedback_text(feedback: FeedbackEnvelope | None) -> str:
    if feedback is None:
        return "No prior Federation decision feedback exists for this first cycle."
    lines = ["Prior Federation decisions (authoritative feedback):"]
    for item in feedback.decisions:
        lines.append(
            f"- {item.proposal_id}: {item.decision.value}; target={item.target_capability}; "
            f"reason={item.reason}; next_proof={item.proof_gate}"
        )
    return "\n".join(lines)


def dispatch_gate(delta: CollaborationDelta, budget: ProviderBudgetEnvelope | None) -> DispatchState:
    if not delta.changed_capabilities and not delta.context:
        return DispatchState.HOLD_EMPTY_DELTA
    if budget is None or not budget.authorized:
        return DispatchState.HOLD_SPEND_AUTHORITY
    if budget.max_usd is None or not math.isfinite(budget.max_usd) or budget.max_usd <= 0:
        return DispatchState.HOLD_SPEND_AUTHORITY
    if not budget.authority_id or not budget.authority_id.strip():
        return DispatchState.HOLD_SPEND_AUTHORITY
    return DispatchState.READY


def compile_cycle(
    *,
    delta: CollaborationDelta,
    parent_cycle_id: str | None = None,
    feedback: FeedbackEnvelope | None = None,
    budget: ProviderBudgetEnvelope | None = None,
    proposal_count: int = 12,
    max_output_tokens: int = 4200,
) -> CollaborationCycle:
    if not 12 <= proposal_count <= 20:
        raise CollaborationBusError("proposal_count must remain compatible with the admitted G2 contract")
    if not 1 <= max_output_tokens <= 6000:
        raise CollaborationBusError("max_output_tokens exceeds the admitted G2 ceiling")
    delta_record = delta.canonical_record()
    delta_sha = _sha(delta_record)
    feedback_sha = feedback.feedback_sha256 if feedback else None
    cycle_seed = {
        "parent_cycle_id": parent_cycle_id,
        "delta_sha256": delta_sha,
        "feedback_sha256": feedback_sha,
    }
    cycle_id = f"SC-GEMINI-COLLAB-{_sha(cycle_seed)[:16].upper()}"
    challenge_id = f"{cycle_id}-G2"
    user_prompt = (
        "SOVARA Creative durable collaboration cycle.\n\n"
        f"Current Federation source head: {delta.source_head}\n"
        f"Material delta: {delta.summary}\n"
        f"Changed capabilities: {', '.join(delta.changed_capabilities) or 'none'}\n"
        f"Evidence pointers: {', '.join(delta.evidence_pointers) or 'none'}\n"
        f"Context JSON: {_stable_json(dict(delta.context))}\n\n"
        f"{_feedback_text(feedback)}\n\n"
        "Return architecture proposals only. Explicitly state how each proposal responds to the current delta and prior Federation feedback. "
        "Prefer REUSE/EXTEND/COMPOSE. New top-level systems are NEW_LAST. Commercial value must be tied to a measurable hypothesis or held as unverified."
    )
    spec = ChallengeSpec(
        challenge_id=challenge_id,
        model="google/gemini-3.1-pro-preview",
        proposal_count=proposal_count,
        max_output_tokens=max_output_tokens,
        temperature=0.35,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        sanitized=True,
        case_data_allowed=False,
        external_effect_allowed=False,
    )
    state = dispatch_gate(delta, budget)
    base = {
        "cycle_id": cycle_id,
        "parent_cycle_id": parent_cycle_id,
        "delta_sha256": delta_sha,
        "challenge_id": challenge_id,
        "feedback_sha256": feedback_sha,
        "dispatch_state": state.value,
        "challenge_prompt_sha256": sha256((spec.system_prompt + "\n" + spec.user_prompt).encode("utf-8")).hexdigest(),
        "proposal_count": proposal_count,
        "max_output_tokens": max_output_tokens,
        "provider_authority_inherited": False,
        "canonical_promotion_inherited": False,
    }
    return CollaborationCycle(
        cycle_id=cycle_id,
        parent_cycle_id=parent_cycle_id,
        delta_sha256=delta_sha,
        challenge_id=challenge_id,
        challenge_spec=spec,
        feedback_sha256=feedback_sha,
        dispatch_state=state,
        receipt_sha256=_sha(base),
    )


def g2_spec_payload(cycle: CollaborationCycle) -> dict[str, Any]:
    spec = cycle.challenge_spec
    return {
        "schema": "SOVARA_CREATIVE_GEMINI_ARCHITECTURE_CHALLENGE_V1",
        "challenge_id": spec.challenge_id,
        "model": spec.model,
        "proposal_count": spec.proposal_count,
        "max_output_tokens": spec.max_output_tokens,
        "temperature": spec.temperature,
        "sanitized": True,
        "case_data_allowed": False,
        "external_effect_allowed": False,
        "system_prompt": spec.system_prompt,
        "user_prompt": spec.user_prompt,
        "collaboration_cycle_id": cycle.cycle_id,
        "parent_cycle_id": cycle.parent_cycle_id,
        "delta_sha256": cycle.delta_sha256,
        "feedback_sha256": cycle.feedback_sha256,
        "dispatch_state": cycle.dispatch_state.value,
    }


def ingest_verified_gemini_output(
    *,
    cycle: CollaborationCycle,
    output: Mapping[str, Any],
    provider_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    payload = _safe_mapping(output, field="output")
    receipt = _safe_mapping(provider_receipt, field="provider_receipt")
    if payload.get("challenge_id") != cycle.challenge_id:
        raise CollaborationBusError("Gemini output challenge_id does not match cycle")
    proposals = payload.get("proposals")
    if not isinstance(proposals, list) or len(proposals) != cycle.challenge_spec.proposal_count:
        raise CollaborationBusError("Gemini output proposal count mismatch")
    seen: set[str] = set()
    for proposal in proposals:
        if not isinstance(proposal, dict):
            raise CollaborationBusError("proposal is not an object")
        pid = _clean_text(str(proposal.get("proposal_id", "")), field="proposal_id", max_len=160)
        if pid in seen:
            raise CollaborationBusError(f"duplicate proposal_id: {pid}")
        seen.add(pid)
    if receipt.get("status") != "VERIFIED" or receipt.get("semantic_verified") is not True:
        raise CollaborationBusError("provider receipt is not semantically verified")
    if receipt.get("proposal_authority_only") is not True:
        raise CollaborationBusError("provider receipt must preserve proposal-only authority")
    if receipt.get("provider_native_readback") is not True:
        raise CollaborationBusError("provider-native readback is required")
    envelope = {
        "schema": "SOVARA_GEMINI_COLLABORATION_PROPOSAL_ENVELOPE_V1",
        "cycle_id": cycle.cycle_id,
        "challenge_id": cycle.challenge_id,
        "provider_request_id": receipt.get("provider_request_id"),
        "model_returned": receipt.get("model_returned"),
        "proposal_count": len(proposals),
        "proposal_ids": sorted(seen),
        "output_sha256": _sha(payload),
        "provider_receipt_sha256": receipt.get("receipt_sha256"),
        "proposal_authority_only": True,
        "canonical_mutation_performed": False,
        "external_effect_performed": False,
    }
    envelope["envelope_sha256"] = _sha(envelope)
    return envelope
