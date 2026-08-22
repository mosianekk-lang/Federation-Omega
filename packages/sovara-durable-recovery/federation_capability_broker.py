#!/usr/bin/env python3
"""Owner-rooted, provider-neutral SOVARA Federation capability broker.

This module compiles exact, secret-free automation envelopes.  It deliberately
does not contain provider SDKs, connector clients, shell execution, credentials,
or an ``execute`` method.  Provider adapters remain separately admitted runtime
components and independent verifiers decide terminal completion.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Any, Callable, Iterable, Mapping, Sequence


OWNER_ID = "KIM_KAGISO_MOSIANE"
EXTERNAL_BOUNDARY = "EXTERNAL_BOUNDARY_NOT_OWNER_DOCTRINE"
ACTION_LIFECYCLE = (
    "discover",
    "health",
    "preflight",
    "lease",
    "canary",
    "execute",
    "readback",
    "compensate",
    "evidence",
)

SURFACE_STATES = frozenset(
    {
        "ADVERTISED",
        "CONNECTED_UNPROVEN",
        "READ_PROVEN",
        "WRITE_PROVEN",
        "AUTOMATION_PROVEN",
        "ACTIVE_PARTIAL",
        "BLOCKED_OR_UNVERIFIED",
        "QUARANTINED",
    }
)
PRESERVATION_STATES = frozenset(
    {
        "PRESERVED_ACTIVE_CORE",
        "PRESERVED_ON_DEMAND",
        "PRESERVED_SHADOW",
        "PRESERVED_EXPERIMENTAL",
        "PRESERVED_LEGACY_COMPATIBILITY",
        "PRESERVED_RECOVERY_BASELINE",
        "PRESERVED_QUARANTINED",
        "PRESERVED_DORMANT",
        "OWNER_REVIEW_REQUIRED",
        "OWNER_APPROVED_RETIREMENT",
    }
)
PROOF_STATES = frozenset(
    {
        "VERIFIED_COMPLETE",
        "PARTIAL",
        "CONTRADICTED",
        "FAILED",
        "ROLLBACK_REQUIRED",
        "OWNER_DECISION_REQUIRED",
    }
)
SECRET_KEY_PATTERN = re.compile(
    r"(^|_)(access_?token|authorization|client_?secret|credential|credentials|"
    r"id_?token|password|private_?key|refresh_?token|secret|token)($|_)",
    re.IGNORECASE,
)
BEARER_PATTERN = re.compile(r"^\s*bearer\s+", re.IGNORECASE)


class BrokerError(Exception):
    code = "BROKER_ERROR"


class ContractRejected(BrokerError):
    code = "CONTRACT_REJECTED"


class AuthorityRejected(BrokerError):
    code = "AUTHORITY_REJECTED"


class CapabilityUnavailable(BrokerError):
    code = "CAPABILITY_UNAVAILABLE"


class LeaseRejected(BrokerError):
    code = "LEASE_REJECTED"


class ReadbackRejected(BrokerError):
    code = "READBACK_REJECTED"


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ContractRejected("timestamp must be ISO-8601 with timezone") from exc
    if parsed.tzinfo is None:
        raise ContractRejected("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def reject_secret_material(value: Any, path: str = "$") -> None:
    """Reject secret-shaped keys and obvious secret values at any depth."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
            if SECRET_KEY_PATTERN.search(normalized):
                raise ContractRejected(f"secret-shaped key rejected at {path}.{key}")
            reject_secret_material(child, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            reject_secret_material(child, f"{path}[{index}]")
    elif isinstance(value, str):
        if BEARER_PATTERN.search(value) or "-----BEGIN PRIVATE KEY-----" in value:
            raise ContractRejected(f"secret-shaped value rejected at {path}")


@dataclass(frozen=True, slots=True)
class CapabilityRequest:
    mission_id: str
    owner_id: str
    capability: str
    operation: str
    target: str
    effect: str
    idempotency_key: str
    expected_artifact_sha256: str | None = None
    expected_semantic_fruit: str | None = None

    def binding(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def binding_sha256(self) -> str:
        return canonical_sha256(self.binding())


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    surface_id: str
    state: str
    capability: str
    operation: str
    proof_level: int
    write_advertised: bool
    authority_inherited: bool
    external_boundary: str


@dataclass(frozen=True, slots=True)
class LeaseRequest:
    request_id: str
    mission_id: str
    owner_id: str
    provider: str
    operation: str
    target: str
    binding_sha256: str
    requested_ttl_seconds: int
    credential_material_requested: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AutomationEnvelope:
    envelope_id: str
    request_binding_sha256: str
    selected_surface: str
    lifecycle: tuple[str, ...]
    stage_states: Mapping[str, str]
    lease_request: LeaseRequest
    execution_allowed: bool
    external_effect_allowed: bool
    executor_required: str
    verifier_required: str
    completion_rule: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["lifecycle"] = list(self.lifecycle)
        value["lease_request"] = self.lease_request.to_dict()
        value["stage_states"] = dict(self.stage_states)
        return value


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    admitted: bool
    provider: str
    lease_id: str
    binding_sha256: str
    expires_at: str
    execution_authority_inherited: bool = False


@dataclass(frozen=True, slots=True)
class ProofDecision:
    state: str
    provider: str
    target: str
    executor_id: str
    verifier_id: str
    artifact_sha256: str | None
    semantic_fruit: str | None
    evidence_sha256: str


def load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ContractRejected("JSON root must be an object")
    reject_secret_material(value)
    return value


def validate_surface_registry(registry: Mapping[str, Any]) -> None:
    reject_secret_material(registry)
    if registry.get("schemaVersion") != "8.0":
        raise ContractRejected("surface registry schemaVersion must be 8.0")
    authority = registry.get("authorityRoot") or {}
    if authority.get("ownerId") != OWNER_ID or authority.get("kind") != "SOLE_OWNER_FINAL_AUTHORITY":
        raise AuthorityRejected("registry authority root is not the exact owner identity")
    if registry.get("authorityInheritance") is not False:
        raise AuthorityRejected("surface or session authority must never be inherited")
    if registry.get("credentialInheritance") is not False:
        raise AuthorityRejected("credentials must never be inherited")
    if registry.get("externalBoundaryClassification") != EXTERNAL_BOUNDARY:
        raise ContractRejected("external provider boundaries are not classified correctly")
    surfaces = registry.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        raise ContractRejected("at least one surface contract is required")
    ids: set[str] = set()
    for surface in surfaces:
        if not isinstance(surface, Mapping):
            raise ContractRejected("surface entries must be objects")
        surface_id = surface.get("id")
        if not surface_id or surface_id in ids:
            raise ContractRejected("surface IDs must be non-empty and unique")
        ids.add(surface_id)
        if surface.get("state") not in SURFACE_STATES:
            raise ContractRejected(f"invalid state for surface {surface_id}")
        capabilities = surface.get("capabilities")
        if not isinstance(capabilities, list) or not capabilities:
            raise ContractRejected(f"surface {surface_id} has no capabilities")
        if surface.get("authorityInherited") is not False:
            raise AuthorityRejected(f"surface {surface_id} claims inherited authority")
        if surface.get("writeProven") is True and surface.get("state") not in {
            "WRITE_PROVEN", "AUTOMATION_PROVEN"
        }:
            raise ContractRejected(f"surface {surface_id} write proof conflicts with state")


def validate_preservation_register(register: Mapping[str, Any]) -> None:
    reject_secret_material(register)
    if register.get("ownerId") != OWNER_ID:
        raise AuthorityRejected("preservation register owner mismatch")
    systems = register.get("systems")
    if not isinstance(systems, list) or not systems:
        raise ContractRejected("preservation register requires systems")
    ids: set[str] = set()
    for system in systems:
        system_id = system.get("system_id")
        if not system_id or system_id in ids:
            raise ContractRejected("system IDs must be unique")
        ids.add(system_id)
        if system.get("lifecycle_state") not in PRESERVATION_STATES:
            raise ContractRejected(f"invalid lifecycle state for {system_id}")
        if system.get("lifecycle_state") == "OWNER_APPROVED_RETIREMENT":
            raise AuthorityRejected("no system has an explicit owner retirement decision")
        if not system.get("protected_capability_floor"):
            raise ContractRejected(f"system {system_id} has no protected capability floor")


class CapabilityBroker:
    """Compile provider-neutral routes without acquiring or exercising authority."""

    _STATE_SCORE = {
        "AUTOMATION_PROVEN": 7,
        "WRITE_PROVEN": 6,
        "READ_PROVEN": 5,
        "ACTIVE_PARTIAL": 4,
        "CONNECTED_UNPROVEN": 3,
        "ADVERTISED": 2,
        "BLOCKED_OR_UNVERIFIED": 1,
        "QUARANTINED": 0,
    }

    def __init__(
        self,
        registry: Mapping[str, Any],
        *,
        owner_id: str,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        validate_surface_registry(registry)
        if owner_id != OWNER_ID:
            raise AuthorityRejected("broker owner identity mismatch")
        self._registry = dict(registry)
        self._surfaces = {item["id"]: dict(item) for item in registry["surfaces"]}
        self._now = now or (lambda: datetime.now(timezone.utc))

    @property
    def registry_sha256(self) -> str:
        return canonical_sha256(self._registry)

    def discover(
        self,
        capability: str,
        operation: str,
        *,
        include_unavailable: bool = False,
    ) -> tuple[RouteCandidate, ...]:
        if not capability or not operation:
            raise ContractRejected("capability and operation are required")
        candidates: list[RouteCandidate] = []
        for surface in self._surfaces.values():
            capability_map = surface.get("capabilities", [])
            match = next(
                (
                    item for item in capability_map
                    if item.get("name") == capability and operation in item.get("operations", [])
                ),
                None,
            )
            if not match:
                continue
            if surface["state"] in {"BLOCKED_OR_UNVERIFIED", "QUARANTINED"} and not include_unavailable:
                continue
            candidates.append(
                RouteCandidate(
                    surface_id=surface["id"],
                    state=surface["state"],
                    capability=capability,
                    operation=operation,
                    proof_level=int(surface.get("proofLevel", 0)),
                    write_advertised=bool(surface.get("writeAdvertised", False)),
                    authority_inherited=False,
                    external_boundary=EXTERNAL_BOUNDARY,
                )
            )
        candidates.sort(
            key=lambda item: (
                -self._STATE_SCORE[item.state],
                -item.proof_level,
                item.surface_id,
            )
        )
        return tuple(candidates)

    def surface(self, surface_id: str) -> dict[str, Any]:
        try:
            return dict(self._surfaces[surface_id])
        except KeyError as exc:
            raise CapabilityUnavailable(f"unknown surface: {surface_id}") from exc

    def validate_provider_identity(
        self,
        surface_id: str,
        observed_identity: Mapping[str, Any],
    ) -> None:
        surface = self.surface(surface_id)
        expected = surface.get("providerIdentity")
        if not isinstance(expected, Mapping) or expected.get("state") != "EXACT":
            raise AuthorityRejected(f"surface {surface_id} provider identity is unresolved")
        exact_fields = expected.get("exactFields") or {}
        if dict(observed_identity) != dict(exact_fields):
            raise AuthorityRejected(f"surface {surface_id} provider identity substitution rejected")

    def prepare(self, request: CapabilityRequest, *, preferred_surface: str | None = None) -> AutomationEnvelope:
        if request.owner_id != OWNER_ID:
            raise AuthorityRejected("request owner identity mismatch")
        if request.effect not in {"READ", "WRITE", "EXTERNAL_COMMUNICATION", "DEPLOY"}:
            raise ContractRejected("unknown effect classification")
        reject_secret_material(request.binding())
        candidates = self.discover(request.capability, request.operation)
        if preferred_surface:
            candidates = tuple(item for item in candidates if item.surface_id == preferred_surface)
        if not candidates:
            raise CapabilityUnavailable("no currently routable surface advertises the exact capability operation")
        selected = candidates[0]
        lease = LeaseRequest(
            request_id=f"LEASE-REQUEST-{request.binding_sha256[:16]}",
            mission_id=request.mission_id,
            owner_id=request.owner_id,
            provider=selected.surface_id,
            operation=request.operation,
            target=request.target,
            binding_sha256=request.binding_sha256,
            requested_ttl_seconds=120,
        )
        stage_states = {
            "discover": "COMPLETE",
            "health": "PROVIDER_ADAPTER_REQUIRED",
            "preflight": "COMPILED",
            "lease": "BROKER_ISSUANCE_REQUIRED",
            "canary": "PROVIDER_NATIVE_CANARY_REQUIRED",
            "execute": "DISABLED_IN_THIS_PACKAGE",
            "readback": "INDEPENDENT_VERIFIER_REQUIRED",
            "compensate": "PROVIDER_ADAPTER_REQUIRED",
            "evidence": "APPEND_ONLY_RECEIPT_REQUIRED",
        }
        envelope_id = "AUTOMATION-" + canonical_sha256(
            {"request": request.binding(), "surface": selected.surface_id, "lifecycle": ACTION_LIFECYCLE}
        )[:24]
        return AutomationEnvelope(
            envelope_id=envelope_id,
            request_binding_sha256=request.binding_sha256,
            selected_surface=selected.surface_id,
            lifecycle=ACTION_LIFECYCLE,
            stage_states=stage_states,
            lease_request=lease,
            execution_allowed=False,
            external_effect_allowed=False,
            executor_required="SEPARATELY_ADMITTED_PROVIDER_NATIVE_ADAPTER",
            verifier_required="INDEPENDENT_PROVIDER_READBACK_COMPONENT",
            completion_rule="Only ProofDecision.state == VERIFIED_COMPLETE closes the mission fruit.",
        )

    def admit_lease(
        self,
        request: CapabilityRequest,
        lease: Mapping[str, Any],
        *,
        preferred_surface: str | None = None,
    ) -> AdmissionDecision:
        reject_secret_material(lease)
        envelope = self.prepare(request, preferred_surface=preferred_surface)
        required = {
            "leaseId", "provider", "operation", "target", "bindingSha256",
            "issuedAt", "expiresAt", "revocable", "credentialMaterialIncluded",
        }
        if set(lease) != required:
            raise LeaseRejected("lease metadata fields do not exactly match the contract")
        if lease["credentialMaterialIncluded"] is not False:
            raise LeaseRejected("credential material may not enter SOVARA")
        if lease["revocable"] is not True:
            raise LeaseRejected("lease must be revocable")
        if lease["provider"] != envelope.selected_surface:
            raise LeaseRejected("lease provider mismatch")
        if lease["operation"] != request.operation or lease["target"] != request.target:
            raise LeaseRejected("lease operation or target mismatch")
        if lease["bindingSha256"] != request.binding_sha256:
            raise LeaseRejected("lease binding mismatch")
        issued = parse_utc(str(lease["issuedAt"]))
        expires = parse_utc(str(lease["expiresAt"]))
        now = self._now().astimezone(timezone.utc)
        if issued > now + timedelta(seconds=5):
            raise LeaseRejected("lease issued in the future")
        if expires <= now:
            raise LeaseRejected("lease expired")
        if expires - issued > timedelta(seconds=120):
            raise LeaseRejected("lease exceeds maximum 120 second lifetime")
        return AdmissionDecision(
            admitted=True,
            provider=lease["provider"],
            lease_id=lease["leaseId"],
            binding_sha256=lease["bindingSha256"],
            expires_at=expires.isoformat().replace("+00:00", "Z"),
        )


def verify_independent_readback(
    request: CapabilityRequest,
    execution_receipt: Mapping[str, Any],
    provider_readback: Mapping[str, Any],
    *,
    executor_id: str,
    verifier_id: str,
) -> ProofDecision:
    reject_secret_material(execution_receipt)
    reject_secret_material(provider_readback)
    if not executor_id or not verifier_id or executor_id == verifier_id:
        raise ReadbackRejected("executor and verifier must be independent identities")
    required_receipt = {"provider", "target", "artifactSha256", "byteCount", "semanticFruit"}
    if set(execution_receipt) != required_receipt or set(provider_readback) != required_receipt:
        raise ReadbackRejected("receipt and readback fields must exactly match the proof contract")
    for field in required_receipt:
        if execution_receipt[field] != provider_readback[field]:
            raise ReadbackRejected(f"provider readback contradicts execution receipt: {field}")
    if execution_receipt["target"] != request.target:
        raise ReadbackRejected("provider target does not match owner request")
    if request.expected_artifact_sha256 and execution_receipt["artifactSha256"] != request.expected_artifact_sha256:
        raise ReadbackRejected("artifact SHA-256 does not match expected bytes")
    if request.expected_semantic_fruit and execution_receipt["semanticFruit"] != request.expected_semantic_fruit:
        raise ReadbackRejected("semantic fruit does not match owner objective")
    evidence = {
        "requestBindingSha256": request.binding_sha256,
        "executionReceipt": dict(execution_receipt),
        "providerReadback": dict(provider_readback),
        "executorId": executor_id,
        "verifierId": verifier_id,
    }
    return ProofDecision(
        state="VERIFIED_COMPLETE",
        provider=str(execution_receipt["provider"]),
        target=str(execution_receipt["target"]),
        executor_id=executor_id,
        verifier_id=verifier_id,
        artifact_sha256=execution_receipt["artifactSha256"],
        semantic_fruit=execution_receipt["semanticFruit"],
        evidence_sha256=canonical_sha256(evidence),
    )


def assert_exact_lifecycle(stages: Iterable[str]) -> None:
    if tuple(stages) != ACTION_LIFECYCLE:
        raise ContractRejected("surface lifecycle must exactly match the SOVARA contract")


__all__ = [
    "ACTION_LIFECYCLE", "EXTERNAL_BOUNDARY", "OWNER_ID", "PROOF_STATES",
    "PRESERVATION_STATES", "AdmissionDecision", "AuthorityRejected",
    "AutomationEnvelope", "BrokerError", "CapabilityBroker", "CapabilityRequest",
    "CapabilityUnavailable", "ContractRejected", "LeaseRejected", "LeaseRequest",
    "ProofDecision", "ReadbackRejected", "RouteCandidate", "assert_exact_lifecycle",
    "canonical_sha256", "load_json", "reject_secret_material",
    "validate_preservation_register", "validate_surface_registry",
    "verify_independent_readback",
]
