"""Gemini/AI Studio provider-cell planning contract.

This module never reads a credential value and never invokes Google. It compiles
a provider call plan for a separately authorized SOVARA/Google execution cell.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from .core import PrivacyEnvelope, assert_public_safe, clean, digest


@dataclass(frozen=True)
class GeminiCallPlan:
    plan_id: str
    mission_id: str
    provider: str
    protocol: str
    model_ref: str
    credential_reference: str
    request_body: Mapping[str, Any]
    tool_allowlist: tuple[str, ...]
    required_readback_fields: tuple[str, ...]
    privacy_envelope_id: str | None
    provider_authority_required: bool
    billed_project_identity_required: bool
    semantic_nonce_required: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GeminiAdapter:
    PROVIDER = "GOOGLE_GEMINI"
    PROTOCOL = "VERTEX_AI_GENERATE_CONTENT_REST"
    REQUIRED_READBACK = (
        "provider_request_id",
        "model_identity",
        "semantic_nonce",
        "finish_state",
        "usage",
        "latency_ms",
        "provider_identity",
    )

    @classmethod
    def compile_call(
        cls,
        *,
        mission_id: str,
        model_ref: str,
        contents: Any,
        credential_reference: str = "CLOUD_RUN_ADC",
        system_instruction: str | None = None,
        tool_allowlist: Iterable[str] = (),
        generation_config: Mapping[str, Any] | None = None,
        privacy_envelope: PrivacyEnvelope | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> GeminiCallPlan:
        if not mission_id.strip() or not model_ref.strip() or not credential_reference.strip():
            raise ValueError("GEMINI_CALL_IDENTITY_REQUIRED")
        body: dict[str, Any] = {"contents": contents}
        if system_instruction:
            body["system_instruction"] = system_instruction
        if generation_config:
            body["generation_config"] = dict(generation_config)
        if metadata:
            body["metadata"] = dict(metadata)
        if privacy_envelope is not None and isinstance(contents, Mapping):
            body["contents"] = privacy_envelope.filter_payload(contents)
        assert_public_safe(body)
        stable = {
            "mission_id": mission_id.strip(),
            "model_ref": model_ref.strip(),
            "credential_reference": credential_reference.strip(),
            "request_body_sha256": digest(body),
            "tool_allowlist": clean(tool_allowlist),
            "privacy_envelope_id": privacy_envelope.envelope_id if privacy_envelope else None,
        }
        return GeminiCallPlan(
            plan_id=f"FC-GEMINI-{digest(stable)[:24].upper()}",
            mission_id=mission_id.strip(),
            provider=cls.PROVIDER,
            protocol=cls.PROTOCOL,
            model_ref=model_ref.strip(),
            credential_reference=credential_reference.strip(),
            request_body=body,
            tool_allowlist=clean(tool_allowlist),
            required_readback_fields=cls.REQUIRED_READBACK,
            privacy_envelope_id=privacy_envelope.envelope_id if privacy_envelope else None,
            provider_authority_required=True,
            billed_project_identity_required=True,
            semantic_nonce_required=True,
        )

    @staticmethod
    def validate_readback(plan: GeminiCallPlan, readback: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
        missing = tuple(sorted(field for field in plan.required_readback_fields if readback.get(field) in (None, "", [])))
        nonce = readback.get("semantic_nonce")
        if plan.semantic_nonce_required and not nonce:
            missing = tuple(sorted(set((*missing, "semantic_nonce"))))
        return not missing, missing

    @staticmethod
    def provider_promotion_allowed(plan: GeminiCallPlan, readback: Mapping[str, Any]) -> bool:
        valid, _ = GeminiAdapter.validate_readback(plan, readback)
        return valid and bool(readback.get("provider_identity")) and bool(readback.get("model_identity"))
