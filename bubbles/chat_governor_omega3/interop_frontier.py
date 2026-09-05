"""Protocol-neutral interoperability projections for ChatGov Ω3.6.

These envelopes borrow capability patterns from A2A and current MCP without
claiming wire-level certification. They provide deterministic task identity,
capability discovery, cache hints and trace correlation while keeping authority
and authentication outside the advertisement itself.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


def _stable(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def _digest(value: Any) -> str:
    return sha256(_stable(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class CapabilityAdvertisement:
    system_id: str
    name: str
    version: str
    skills: tuple[str, ...]
    authority_ceiling: str = "A0_READ_ONLY"
    authentication_required: bool = True
    protocol_hints: tuple[str, ...] = ("A2A-LIKE", "MCP-LIKE")

    @classmethod
    def build(
        cls, *, system_id: str, name: str, version: str, skills: Sequence[str],
        authority_ceiling: str = "A0_READ_ONLY", authentication_required: bool = True,
    ) -> "CapabilityAdvertisement":
        if not all(map(str.strip, (system_id, name, version))):
            raise ValueError("CAPABILITY_ADVERTISEMENT_IDENTITY_REQUIRED")
        normalized = tuple(sorted(set(map(str, skills))))
        if not normalized:
            raise ValueError("CAPABILITY_ADVERTISEMENT_SKILLS_REQUIRED")
        return cls(system_id, name, version, normalized, authority_ceiling, authentication_required)

    @property
    def fingerprint(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True, slots=True)
class AgentTaskEnvelope:
    task_id: str
    context_id: str
    mission_id: str
    skill_id: str
    input_ref: str
    trace_id: str
    artifact_refs: tuple[str, ...] = ()
    state: str = "SUBMITTED"
    authority_ref: str = ""
    effectful: bool = False

    def validate(self) -> None:
        if not all(map(str.strip, (self.task_id, self.context_id, self.mission_id, self.skill_id, self.input_ref, self.trace_id))):
            raise ValueError("AGENT_TASK_IDENTITY_REQUIRED")
        if self.state not in {"SUBMITTED", "WORKING", "INPUT_REQUIRED", "COMPLETED", "FAILED", "CANCELED"}:
            raise ValueError("AGENT_TASK_STATE_INVALID")
        if self.effectful and not self.authority_ref.strip():
            raise ValueError("AGENT_TASK_EFFECT_AUTHORITY_REQUIRED")

    @property
    def fingerprint(self) -> str:
        self.validate()
        return _digest(asdict(self))


@dataclass(frozen=True, slots=True)
class MCPRequestMetadata:
    protocol_version: str
    capabilities: tuple[str, ...]
    traceparent: str = ""
    task_id: str = ""
    ttl_ms: int = 0
    cache_scope: str = "session"
    extra: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def build(
        cls, *, protocol_version: str, capabilities: Sequence[str], traceparent: str = "",
        task_id: str = "", ttl_ms: int = 0, cache_scope: str = "session",
        extra: Mapping[str, Any] | None = None,
    ) -> "MCPRequestMetadata":
        if not protocol_version.strip():
            raise ValueError("MCP_PROTOCOL_VERSION_REQUIRED")
        if cache_scope not in {"session", "mission", "provider"} or ttl_ms < 0:
            raise ValueError("MCP_CACHE_HINT_INVALID")
        return cls(
            protocol_version=protocol_version,
            capabilities=tuple(sorted(set(map(str, capabilities)))),
            traceparent=traceparent,
            task_id=task_id,
            ttl_ms=ttl_ms,
            cache_scope=cache_scope,
            extra=dict(extra or {}),
        )

    @property
    def cache_key(self) -> str:
        return _digest({
            "protocol_version": self.protocol_version,
            "capabilities": self.capabilities,
            "cache_scope": self.cache_scope,
            "extra": dict(self.extra),
        })


@dataclass(frozen=True, slots=True)
class InteropAdmissionDecision:
    state: str
    admitted: bool
    reasons: tuple[str, ...]


def admit_agent_task(
    task: AgentTaskEnvelope, advertisement: CapabilityAdvertisement,
    *, authenticated: bool, current_authority: str,
) -> InteropAdmissionDecision:
    task.validate()
    if task.skill_id not in advertisement.skills:
        return InteropAdmissionDecision("SKILL_NOT_ADVERTISED", False, ("CAPABILITY_NEGOTIATION_REQUIRED",))
    if advertisement.authentication_required and not authenticated:
        return InteropAdmissionDecision("AUTHENTICATION_REQUIRED", False, ("NO_AUTHORITY_INHERITANCE",))
    if task.effectful and not task.authority_ref:
        return InteropAdmissionDecision("EFFECT_AUTHORITY_REQUIRED", False, ("EXACT_AUTHORITY_REF_REQUIRED",))
    if task.effectful and current_authority in {"", "A0_READ_ONLY", "A1_INTERNAL"}:
        return InteropAdmissionDecision("CURRENT_AUTHORITY_INSUFFICIENT", False, ("NO_AUTHORITY_INHERITANCE",))
    return InteropAdmissionDecision("ADMITTED", True, ("SKILL_MATCH", "AUTHENTICATION_CHECKED", "AUTHORITY_EXPLICIT"))


__all__ = [
    "AgentTaskEnvelope", "CapabilityAdvertisement", "InteropAdmissionDecision",
    "MCPRequestMetadata", "admit_agent_task",
]
