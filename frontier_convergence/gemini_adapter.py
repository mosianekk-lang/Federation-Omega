"""Gemini/AI Studio provider-cell planning contracts.

This module never reads credential values and never invokes Google. It compiles
provider-neutral Google call plans for separately authorized SOVARA execution
cells. V1 generateContent remains available as rollback; V2 adds the Vertex
Interactions API as the preferred Gemini 3 transport.
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
    PROTOCOL_VERTEX_GENERATE_CONTENT = PROTOCOL
    PROTOCOL_VERTEX_INTERACTIONS = "VERTEX_AI_INTERACTIONS_REST"
    PROTOCOL_GEMINI_INTERACTIONS = "GEMINI_INTERACTIONS_REST"

    SUPPORTED_PROTOCOLS = frozenset(
        {
            PROTOCOL_VERTEX_GENERATE_CONTENT,
            PROTOCOL_VERTEX_INTERACTIONS,
            PROTOCOL_GEMINI_INTERACTIONS,
        }
    )

    REQUIRED_READBACK = (
        "provider_request_id",
        "model_identity",
        "semantic_nonce",
        "finish_state",
        "usage",
        "latency_ms",
        "provider_identity",
    )
    INTERACTIONS_REQUIRED_READBACK = (
        "provider_request_id",
        "model_identity",
        "semantic_nonce",
        "finish_state",
        "usage",
        "latency_ms",
        "provider_identity",
        "interaction_id",
        "interaction_status",
        "response_digest",
        "observed_at",
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
        """Compile the admitted V1 generateContent rollback plan."""
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
            "protocol": cls.PROTOCOL_VERTEX_GENERATE_CONTENT,
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
            protocol=cls.PROTOCOL_VERTEX_GENERATE_CONTENT,
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

    @classmethod
    def compile_interaction(
        cls,
        *,
        mission_id: str,
        input_data: Any,
        model_ref: str = "gemini-3.8-flash",
        credential_reference: str = "GITHUB_WIF_ADC",
        protocol: str = PROTOCOL_VERTEX_INTERACTIONS,
        store: bool = False,
        previous_interaction_id: str | None = None,
        background: bool = False,
        system_instruction: str | None = None,
        tool_allowlist: Iterable[str] = (),
        tools: Iterable[Mapping[str, Any]] = (),
        response_format: Mapping[str, Any] | None = None,
        generation_config: Mapping[str, Any] | None = None,
        privacy_envelope: PrivacyEnvelope | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> GeminiCallPlan:
        """Compile a V2 Interactions API plan without executing it.

        Sensitive/private callers are expected to keep store False. In
        stateless mode provider continuation and background execution are
        rejected before any provider call is possible.
        """
        if not mission_id.strip() or not model_ref.strip() or not credential_reference.strip():
            raise ValueError("GEMINI_INTERACTION_IDENTITY_REQUIRED")
        if protocol not in cls.SUPPORTED_PROTOCOLS - {cls.PROTOCOL_VERTEX_GENERATE_CONTENT}:
            raise ValueError("GEMINI_INTERACTION_PROTOCOL_UNSUPPORTED")
        if not store and previous_interaction_id:
            raise ValueError("STATELESS_INTERACTION_CANNOT_REFERENCE_PREVIOUS")
        if not store and background:
            raise ValueError("STATELESS_INTERACTION_CANNOT_RUN_BACKGROUND")

        filtered_input = input_data
        if privacy_envelope is not None and isinstance(input_data, Mapping):
            filtered_input = privacy_envelope.filter_payload(input_data)

        body: dict[str, Any] = {
            "model": model_ref.strip(),
            "input": filtered_input,
            "store": bool(store),
        }
        if previous_interaction_id:
            body["previous_interaction_id"] = previous_interaction_id.strip()
        if background:
            body["background"] = True
        if system_instruction:
            body["system_instruction"] = system_instruction
        tool_rows = tuple(dict(row) for row in tools)
        if tool_rows:
            body["tools"] = list(tool_rows)
        if response_format:
            body["response_format"] = dict(response_format)
        if generation_config:
            body["generation_config"] = dict(generation_config)
        if metadata:
            body["metadata"] = dict(metadata)

        assert_public_safe(body)
        stable = {
            "mission_id": mission_id.strip(),
            "protocol": protocol,
            "model_ref": model_ref.strip(),
            "credential_reference": credential_reference.strip(),
            "request_body_sha256": digest(body),
            "tool_allowlist": clean(tool_allowlist),
            "privacy_envelope_id": privacy_envelope.envelope_id if privacy_envelope else None,
        }
        return GeminiCallPlan(
            plan_id=f"FC-GEMINI-INT-{digest(stable)[:24].upper()}",
            mission_id=mission_id.strip(),
            provider=cls.PROVIDER,
            protocol=protocol,
            model_ref=model_ref.strip(),
            credential_reference=credential_reference.strip(),
            request_body=body,
            tool_allowlist=clean(tool_allowlist),
            required_readback_fields=cls.INTERACTIONS_REQUIRED_READBACK,
            privacy_envelope_id=privacy_envelope.envelope_id if privacy_envelope else None,
            provider_authority_required=True,
            billed_project_identity_required=True,
            semantic_nonce_required=True,
        )

    @staticmethod
    def validate_readback(plan: GeminiCallPlan, readback: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
        missing = tuple(
            sorted(
                field
                for field in plan.required_readback_fields
                if readback.get(field) in (None, "", [])
            )
        )
        nonce = readback.get("semantic_nonce")
        if plan.semantic_nonce_required and not nonce:
            missing = tuple(sorted(set((*missing, "semantic_nonce"))))
        return not missing, missing

    @staticmethod
    def provider_promotion_allowed(plan: GeminiCallPlan, readback: Mapping[str, Any]) -> bool:
        valid, _ = GeminiAdapter.validate_readback(plan, readback)
        return valid and bool(readback.get("provider_identity")) and bool(readback.get("model_identity"))
