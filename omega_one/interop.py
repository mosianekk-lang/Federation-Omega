"""Omega-One zero-dilution interoperability projections.

Omega-One's Universal Capability Contract (UCC) remains the semantic source of truth.
External standards receive portable projections; richer Omega-One semantics are never
deleted, flattened or granted away simply because a target standard cannot express them.

This module is deliberately non-effect: it contains no network clients, credentials,
provider calls, agent execution or SOVARA authority.

Target standards:
- MCP 2026-07-28: stateless request routing, per-request client metadata and tool calls.
- A2A 1.0: Agent Card capability discovery plus protocol extensions.
- OpenTelemetry semantic conventions 1.44-era GenAI/tool tracing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
import re
from typing import Any, Mapping


MCP_PROTOCOL_VERSION = "2026-07-28"
A2A_PROTOCOL_VERSION = "1.0.0"
OTEL_SEMCONV_VERSION = "1.44.0"
OMEGA_GOVERNANCE_EXTENSION_URI = "urn:omega-one:governance:v1"


class EffectClass(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    EXTERNAL_EFFECT = "EXTERNAL_EFFECT"


class OmegaTaskState(str, Enum):
    SUBMITTED = "SUBMITTED"
    WORKING = "WORKING"
    INPUT_REQUIRED = "INPUT_REQUIRED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class UniversalCapabilityContract:
    capability_id: str
    name: str
    description: str
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    output_schema: Mapping[str, Any] = field(default_factory=dict)
    effect_class: EffectClass = EffectClass.READ
    authority_ceiling: str = "A1_INTERNAL"
    privacy_class: str = "P1_INTERNAL"
    rollback_required: bool = False
    proof_required: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> "UniversalCapabilityContract":
        if not self.capability_id.strip() or not self.name.strip():
            raise ValueError("capability_id and name are required")
        if self.effect_class != EffectClass.READ and not self.rollback_required:
            raise ValueError("effectful UCC requires rollback_required=True")
        return self


@dataclass(frozen=True)
class McpToolProjection:
    protocol_version: str
    method: str
    name: str
    tool: Mapping[str, Any]
    headers: Mapping[str, str]
    request_meta: Mapping[str, Any]
    execution_ready: bool
    hold_reason: str | None


@dataclass(frozen=True)
class A2AAgentProjection:
    protocol_version: str
    agent_card: Mapping[str, Any]
    execution_ready: bool
    hold_reason: str | None


@dataclass(frozen=True)
class OTelProjection:
    semconv_version: str
    span_name: str
    attributes: Mapping[str, Any]


@dataclass(frozen=True)
class InteropBundle:
    capability_id: str
    source_contract: UniversalCapabilityContract
    source_ucc_sha256: str
    zero_dilution_verified: bool
    mcp: McpToolProjection
    a2a: A2AAgentProjection
    otel: OTelProjection
    bundle_sha256: str


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _safe_name(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-")
    if not slug:
        raise ValueError("name cannot normalize to empty")
    return slug[:128]


def _execution_gate(ucc: UniversalCapabilityContract) -> tuple[bool, str | None]:
    if ucc.effect_class == EffectClass.EXTERNAL_EFFECT:
        return False, "SOVARA_EFFECT_AUTHORITY_REQUIRED"
    return True, None


def _a2a_execution_gate(ucc: UniversalCapabilityContract) -> tuple[bool, str | None]:
    base_ready, base_hold = _execution_gate(ucc)
    if not base_ready:
        return base_ready, base_hold
    # This module creates an Agent Card template only. A real A2A endpoint/interface is
    # provider/runtime state and must be bound and independently proven elsewhere.
    return False, "A2A_RUNTIME_INTERFACE_REQUIRED"


class OmegaInteropSpine:
    """Compile a UCC into additive, non-authoritative standards projections.

    Superset invariant: the exact internal UCC travels in the InteropBundle and is hash-bound.
    A target standard may receive only a portable subset, but that projection can never become
    authority to delete or weaken the richer Omega-One contract.
    """

    @classmethod
    def compile(cls, ucc: UniversalCapabilityContract, *, mission_id: str, trace_id: str = "") -> InteropBundle:
        ucc.validate()
        if not mission_id.strip():
            raise ValueError("mission_id is required")

        source_ucc_sha256 = _sha256(asdict(ucc))
        mcp_ready, mcp_hold = _execution_gate(ucc)
        a2a_ready, a2a_hold = _a2a_execution_gate(ucc)
        name = _safe_name(ucc.name)

        governance_params = {
            "sourceUccSha256": source_ucc_sha256,
            "capabilityId": ucc.capability_id,
            "effectClass": ucc.effect_class.value,
            "authorityCeiling": ucc.authority_ceiling,
            "privacyClass": ucc.privacy_class,
            "rollbackRequired": ucc.rollback_required,
            "proofRequired": list(ucc.proof_required),
            "portableProjectionOnly": True,
            "zeroDilution": True,
        }

        mcp = McpToolProjection(
            protocol_version=MCP_PROTOCOL_VERSION,
            method="tools/call",
            name=name,
            tool={
                "name": name,
                "description": ucc.description,
                "inputSchema": dict(ucc.input_schema),
                "outputSchema": dict(ucc.output_schema),
                "_meta": {
                    "omega.capability_id": ucc.capability_id,
                    "omega.source_ucc_sha256": source_ucc_sha256,
                    "omega.effect_class": ucc.effect_class.value,
                    "omega.authority_ceiling": ucc.authority_ceiling,
                    "omega.privacy_class": ucc.privacy_class,
                    "omega.proof_required": list(ucc.proof_required),
                    "omega.portable_projection_only": True,
                    "omega.zero_dilution": True,
                },
            },
            headers={
                "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
                "Mcp-Method": "tools/call",
                "Mcp-Name": name,
            },
            request_meta={
                "io.modelcontextprotocol/clientInfo": {
                    "name": "omega-one",
                    "version": "0.8.5-candidate",
                },
                "omega/sourceUccSha256": source_ucc_sha256,
                **({"omega/traceId": trace_id} if trace_id else {}),
            },
            execution_ready=mcp_ready,
            hold_reason=mcp_hold,
        )

        skill = {
            "id": ucc.capability_id,
            "name": ucc.name,
            "description": ucc.description,
            "tags": sorted({"omega-one", ucc.effect_class.value.lower(), ucc.privacy_class.lower()}),
            "inputModes": ["application/json"],
            "outputModes": ["application/json"],
        }
        agent_card = {
            "name": f"Omega-One — {ucc.name}",
            "description": "Zero-dilution A2A projection of an Omega-One Universal Capability Contract.",
            "supportedInterfaces": [],
            "version": "0.8.5-candidate",
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
                "extendedAgentCard": False,
                "extensions": [
                    {
                        "uri": OMEGA_GOVERNANCE_EXTENSION_URI,
                        "description": "Preserves Omega-One authority, privacy, proof and rollback semantics without transferring execution sovereignty.",
                        "required": True,
                        "params": governance_params,
                    }
                ],
            },
            "defaultInputModes": ["application/json"],
            "defaultOutputModes": ["application/json"],
            "skills": [skill],
        }
        a2a = A2AAgentProjection(
            protocol_version=A2A_PROTOCOL_VERSION,
            agent_card=agent_card,
            execution_ready=a2a_ready,
            hold_reason=a2a_hold,
        )

        otel = OTelProjection(
            semconv_version=OTEL_SEMCONV_VERSION,
            span_name=f"execute_tool {name}",
            attributes={
                "service.name": "omega-one",
                "omega.mission.id": mission_id,
                "omega.capability.id": ucc.capability_id,
                "omega.source_ucc.sha256": source_ucc_sha256,
                "omega.effect.class": ucc.effect_class.value,
                "omega.authority.ceiling": ucc.authority_ceiling,
                "omega.privacy.class": ucc.privacy_class,
                "omega.rollback.required": ucc.rollback_required,
                "omega.execution.ready": mcp_ready,
                "omega.hold.reason": mcp_hold or "",
                "omega.zero_dilution": True,
                "gen_ai.operation.name": "execute_tool",
                **({"omega.trace.id": trace_id} if trace_id else {}),
            },
        )

        body = {
            "capability_id": ucc.capability_id,
            "source_ucc_sha256": source_ucc_sha256,
            "mcp": asdict(mcp),
            "a2a": asdict(a2a),
            "otel": asdict(otel),
        }
        bundle = InteropBundle(
            capability_id=ucc.capability_id,
            source_contract=ucc,
            source_ucc_sha256=source_ucc_sha256,
            zero_dilution_verified=True,
            mcp=mcp,
            a2a=a2a,
            otel=otel,
            bundle_sha256=hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest(),
        )
        if not cls.verify_zero_dilution(bundle):
            raise ValueError("zero-dilution invariant failed")
        return bundle

    @staticmethod
    def verify_zero_dilution(bundle: InteropBundle) -> bool:
        return bundle.zero_dilution_verified and _sha256(asdict(bundle.source_contract)) == bundle.source_ucc_sha256

    @staticmethod
    def task_state_to_a2a(state: OmegaTaskState) -> str:
        mapping = {
            OmegaTaskState.SUBMITTED: "submitted",
            OmegaTaskState.WORKING: "working",
            OmegaTaskState.INPUT_REQUIRED: "input-required",
            OmegaTaskState.AUTH_REQUIRED: "auth-required",
            OmegaTaskState.COMPLETED: "completed",
            OmegaTaskState.FAILED: "failed",
            OmegaTaskState.CANCELLED: "canceled",
            OmegaTaskState.REJECTED: "rejected",
            OmegaTaskState.UNKNOWN: "unknown",
        }
        return mapping[state]
