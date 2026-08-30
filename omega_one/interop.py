"""Omega-One interoperability projections for MCP, A2A and OpenTelemetry.

The module preserves Omega-One's internal Universal Capability Contract (UCC) as the
semantic source of truth, then projects only the portable subset into external standards.
It is deliberately non-effect: no network clients, credentials, provider calls or agent
execution live here.

Target standards:
- MCP protocol version 2026-07-28: stateless request metadata, tools/resources and
  task-extension compatible lifecycle hints.
- A2A 1.0: agent capability discovery and task-lifecycle projection.
- OpenTelemetry semantic conventions: trace correlation attributes.
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
            # Translation may still occur, but an effectful contract must preserve the
            # reversible-state invariant before it can be considered execution-ready.
            raise ValueError("effectful UCC requires rollback_required=True")
        return self


@dataclass(frozen=True)
class McpToolProjection:
    protocol_version: str
    method: str
    name: str
    tool: Mapping[str, Any]
    headers: Mapping[str, str]
    execution_ready: bool
    hold_reason: str | None


@dataclass(frozen=True)
class A2AAgentSkillProjection:
    protocol_version: str
    skill: Mapping[str, Any]
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
    mcp: McpToolProjection
    a2a: A2AAgentSkillProjection
    otel: OTelProjection
    bundle_sha256: str


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _safe_name(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-")
    if not slug:
        raise ValueError("name cannot normalize to empty")
    return slug[:128]


def _execution_gate(ucc: UniversalCapabilityContract) -> tuple[bool, str | None]:
    if ucc.effect_class == EffectClass.EXTERNAL_EFFECT:
        return False, "SOVARA_EFFECT_AUTHORITY_REQUIRED"
    if ucc.effect_class == EffectClass.WRITE and ucc.authority_ceiling == "A1_INTERNAL":
        return True, None
    return True, None


class OmegaInteropSpine:
    """Compile UCC into non-authoritative external-standard projections."""

    @classmethod
    def compile(cls, ucc: UniversalCapabilityContract, *, mission_id: str, trace_id: str = "") -> InteropBundle:
        ucc.validate()
        if not mission_id.strip():
            raise ValueError("mission_id is required")
        execution_ready, hold_reason = _execution_gate(ucc)
        name = _safe_name(ucc.name)

        mcp = McpToolProjection(
            protocol_version=MCP_PROTOCOL_VERSION,
            method="tools/call",
            name=name,
            tool={
                "name": name,
                "description": ucc.description,
                "inputSchema": dict(ucc.input_schema),
                "_meta": {
                    "omega.capability_id": ucc.capability_id,
                    "omega.effect_class": ucc.effect_class.value,
                    "omega.authority_ceiling": ucc.authority_ceiling,
                    "omega.privacy_class": ucc.privacy_class,
                    "omega.proof_required": list(ucc.proof_required),
                },
            },
            headers={
                "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
                "Mcp-Method": "tools/call",
                "Mcp-Name": name,
            },
            execution_ready=execution_ready,
            hold_reason=hold_reason,
        )

        a2a = A2AAgentSkillProjection(
            protocol_version=A2A_PROTOCOL_VERSION,
            skill={
                "id": ucc.capability_id,
                "name": ucc.name,
                "description": ucc.description,
                "tags": sorted({
                    "omega-one",
                    ucc.effect_class.value.lower(),
                    ucc.privacy_class.lower(),
                }),
                "inputModes": ["application/json"],
                "outputModes": ["application/json"],
                "extensions": {
                    "omega": {
                        "authority_ceiling": ucc.authority_ceiling,
                        "rollback_required": ucc.rollback_required,
                        "proof_required": list(ucc.proof_required),
                    }
                },
            },
            execution_ready=execution_ready,
            hold_reason=hold_reason,
        )

        otel = OTelProjection(
            semconv_version=OTEL_SEMCONV_VERSION,
            span_name=f"omega.capability {name}",
            attributes={
                "service.name": "omega-one",
                "omega.mission.id": mission_id,
                "omega.capability.id": ucc.capability_id,
                "omega.effect.class": ucc.effect_class.value,
                "omega.authority.ceiling": ucc.authority_ceiling,
                "omega.privacy.class": ucc.privacy_class,
                "omega.rollback.required": ucc.rollback_required,
                "omega.execution.ready": execution_ready,
                "omega.hold.reason": hold_reason or "",
                "gen_ai.operation.name": "execute_capability",
                **({"omega.trace.id": trace_id} if trace_id else {}),
            },
        )

        body = {
            "capability_id": ucc.capability_id,
            "mcp": asdict(mcp),
            "a2a": asdict(a2a),
            "otel": asdict(otel),
        }
        return InteropBundle(
            capability_id=ucc.capability_id,
            mcp=mcp,
            a2a=a2a,
            otel=otel,
            bundle_sha256=hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest(),
        )

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
