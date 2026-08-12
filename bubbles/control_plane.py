from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping


class EffectClass(str, Enum):
    READ = "READ"
    LOW_RISK_WRITE = "LOW_RISK_WRITE"
    CONSEQUENTIAL_WRITE = "CONSEQUENTIAL_WRITE"


class RouteKind(str, Enum):
    CHATGPT_NATIVE = "CHATGPT_NATIVE"
    GITHUB_COMMAND_BUS = "GITHUB_COMMAND_BUS"
    MCP_READ_ONLY = "MCP_READ_ONLY"


@dataclass(frozen=True)
class AdapterSpec:
    adapter_id: str
    route_kind: RouteKind
    authority_ceiling: str
    supports_read: bool = True
    supports_write: bool = False
    required_proofs: frozenset[str] = field(default_factory=frozenset)
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActionRequest:
    adapter_id: str
    action: str
    effect: EffectClass
    target_alias: str
    payload: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RouteDecision:
    state: str
    route_kind: RouteKind | None
    adapter_id: str
    action: str
    missing_proofs: tuple[str, ...] = ()
    reason: str = ""


_SECRET_TOKENS = (
    "password",
    "secret",
    "private_key",
    "access_token",
    "refresh_token",
    "api_key",
    "authorization",
    "credential",
)


def _contains_secret_field(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in _SECRET_TOKENS):
                return True
            if _contains_secret_field(child):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_secret_field(item) for item in value)
    return False


DEFAULT_ADAPTERS: dict[str, AdapterSpec] = {
    "google_drive": AdapterSpec(
        adapter_id="google_drive",
        route_kind=RouteKind.CHATGPT_NATIVE,
        authority_ceiling="A1",
        supports_write=True,
        required_proofs=frozenset({"connector_permission_verified"}),
        notes=("Prefer the native ChatGPT Google Drive app for supported actions.",),
    ),
    "gmail": AdapterSpec(
        adapter_id="gmail",
        route_kind=RouteKind.CHATGPT_NATIVE,
        authority_ceiling="A1",
        supports_write=True,
        required_proofs=frozenset({"connector_permission_verified"}),
    ),
    "canva": AdapterSpec(
        adapter_id="canva",
        route_kind=RouteKind.CHATGPT_NATIVE,
        authority_ceiling="A1",
        supports_write=True,
        required_proofs=frozenset({"connector_permission_verified"}),
    ),
    "github": AdapterSpec(
        adapter_id="github",
        route_kind=RouteKind.CHATGPT_NATIVE,
        authority_ceiling="A1",
        supports_write=True,
        required_proofs=frozenset({"connector_permission_verified"}),
        notes=("GitHub is the canonical Bubbles command-bus ingress.",),
    ),
    "bubbles_command_bus": AdapterSpec(
        adapter_id="bubbles_command_bus",
        route_kind=RouteKind.GITHUB_COMMAND_BUS,
        authority_ceiling="A1_INTERNAL",
        supports_read=True,
        supports_write=False,
        notes=("Internal harmless canary used to prove ChatGPT-to-Actions command ingress and immutable receipt readback.",),
    ),
    "google_cloud_wif_plan": AdapterSpec(
        adapter_id="google_cloud_wif_plan",
        route_kind=RouteKind.GITHUB_COMMAND_BUS,
        authority_ceiling="A1_READ",
        supports_read=True,
        supports_write=False,
        notes=(
            "Read-only handoff to the default-branch Bubbles provider worker.",
            "The worker may mint short-lived OIDC credentials but may only execute ops/bootstrap_github_wif.sh --plan.",
        ),
    ),
    "google_cloud": AdapterSpec(
        adapter_id="google_cloud",
        route_kind=RouteKind.GITHUB_COMMAND_BUS,
        authority_ceiling="A1_ROUTE_SPECIFIC",
        supports_write=True,
        required_proofs=frozenset(
            {
                "provider_identity_verified",
                "target_verified",
                "action_scope_verified",
                "provider_readback_contract",
            }
        ),
        notes=("Reuse existing GitHub Actions/WIF assets; no universal cloud authority claim.",),
    ),
    "apps_script": AdapterSpec(
        adapter_id="apps_script",
        route_kind=RouteKind.GITHUB_COMMAND_BUS,
        authority_ceiling="A1_ROUTE_SPECIFIC",
        supports_write=True,
        required_proofs=frozenset(
            {
                "project_identity_verified",
                "oauth_scope_verified",
                "action_scope_verified",
                "provider_readback_contract",
            }
        ),
        notes=("Reuse ops/apps_script_authorization_gate.py and existing activation assets.",),
    ),
    "google_ai_studio": AdapterSpec(
        adapter_id="google_ai_studio",
        route_kind=RouteKind.GITHUB_COMMAND_BUS,
        authority_ceiling="A1_EXPERIMENT",
        supports_write=True,
        required_proofs=frozenset(
            {
                "provider_identity_verified",
                "resource_target_verified",
                "action_scope_verified",
                "provider_readback_contract",
            }
        ),
        notes=("Treat AI Studio resources as experimental until provider inventory/readback is fresh.",),
    ),
    "bubbles_mcp": AdapterSpec(
        adapter_id="bubbles_mcp",
        route_kind=RouteKind.MCP_READ_ONLY,
        authority_ceiling="A1_READ",
        supports_write=False,
        notes=("ChatGPT Pro custom MCP is treated as read/fetch only; never smuggle writes through a read tool.",),
    ),
}


class BubblesControlPlane:
    """Fail-closed route selector for ChatGPT-facing Kim Dataverse operations.

    The control plane selects an authorised execution route. It does not create
    provider authority and never treats source/configuration existence as proof
    that a provider action executed.
    """

    def __init__(self, adapters: Mapping[str, AdapterSpec] | None = None) -> None:
        self._adapters = dict(adapters or DEFAULT_ADAPTERS)

    def adapter(self, adapter_id: str) -> AdapterSpec:
        try:
            return self._adapters[adapter_id]
        except KeyError as exc:
            raise KeyError(f"Unknown Bubbles adapter: {adapter_id}") from exc

    def decide(
        self,
        request: ActionRequest,
        observed_proofs: frozenset[str] = frozenset(),
    ) -> RouteDecision:
        spec = self.adapter(request.adapter_id)

        if _contains_secret_field(request.payload):
            return RouteDecision(
                state="CONSTRAINT",
                route_kind=None,
                adapter_id=spec.adapter_id,
                action=request.action,
                reason="Secret-bearing fields are prohibited in Bubbles command payloads.",
            )

        if request.effect is EffectClass.READ and not spec.supports_read:
            return RouteDecision(
                state="CONSTRAINT",
                route_kind=None,
                adapter_id=spec.adapter_id,
                action=request.action,
                reason="Adapter does not support reads.",
            )

        if request.effect is not EffectClass.READ and not spec.supports_write:
            return RouteDecision(
                state="CONSTRAINT",
                route_kind=spec.route_kind,
                adapter_id=spec.adapter_id,
                action=request.action,
                reason="Selected route is read-only for this ChatGPT surface.",
            )

        missing = tuple(sorted(spec.required_proofs.difference(observed_proofs)))
        if missing:
            return RouteDecision(
                state="CONSTRAINT",
                route_kind=spec.route_kind,
                adapter_id=spec.adapter_id,
                action=request.action,
                missing_proofs=missing,
                reason="Fresh route/provider proof is required before execution.",
            )

        return RouteDecision(
            state="READY",
            route_kind=spec.route_kind,
            adapter_id=spec.adapter_id,
            action=request.action,
            reason="Route selected; execution still requires route-native receipt/readback.",
        )

    @staticmethod
    def command_envelope(request: ActionRequest) -> dict[str, object]:
        if _contains_secret_field(request.payload):
            raise ValueError("Secret-bearing fields are prohibited in Bubbles command payloads")

        body = {
            "schema": "BUBBLES-CONTROL-COMMAND-V1",
            "adapter_id": request.adapter_id,
            "action": request.action,
            "effect": request.effect.value,
            "target_alias": request.target_alias,
            "payload": dict(request.payload),
        }
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return {
            **body,
            "command_sha256": sha256(canonical.encode("utf-8")).hexdigest(),
            "truth_boundary": (
                "Envelope creation proves intent formatting only; provider execution, "
                "authority and success require independent route-native readback."
            ),
        }
