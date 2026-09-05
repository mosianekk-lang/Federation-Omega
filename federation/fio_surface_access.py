"""FIO-Ω / SIR-Ω v1.5 — SOVARA-derived Kim Dataverse surface access fabric.

This module gives FIO a deterministic census/routing layer across KDV surfaces
without creating a new authority plane. Safe A0/A1 operations may auto-route
when a current surface attestation exists. External effects, communications,
security/credential changes, spend and irreversible actions are delegated to
SOVARA/Human-First and never self-authorized here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Sequence


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def digest(value: Any) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


class SurfaceClass(str, Enum):
    CANONICAL_STATE = "CANONICAL_STATE"
    PROVIDER_DATA = "PROVIDER_DATA"
    COMMUNICATION = "COMMUNICATION"
    SCHEDULING = "SCHEDULING"
    CREATIVE = "CREATIVE"
    SOURCE_CI = "SOURCE_CI"
    MODEL_PROVIDER = "MODEL_PROVIDER"
    PROVIDER_RUNTIME = "PROVIDER_RUNTIME"
    COLLABORATION = "COLLABORATION"
    WORKFLOW = "WORKFLOW"
    CONTROL_PLANE = "CONTROL_PLANE"
    HOST_INTERFACE = "HOST_INTERFACE"
    OTHER = "OTHER"


class SurfaceMode(str, Enum):
    HELD = "HELD"
    READ_ONLY = "READ_ONLY"
    SAFE_INTERNAL = "SAFE_INTERNAL"
    ACTION_SPECIFIC = "ACTION_SPECIFIC"


@dataclass(frozen=True, slots=True)
class SurfaceManifest:
    surface_id: str
    name: str
    surface_class: SurfaceClass
    capabilities: tuple[str, ...]
    authority_ceiling: str = "A0_READ_ONLY"
    privacy_ceiling: str = "P1_INTERNAL"
    direct_adapter: str = ""
    fallback_adapter: str = ""
    external_effect_default: bool = False
    explicit_communication_send_only: bool = False
    auto_enroll_unknown: bool = True
    freshness_ttl_minutes: int = 75

    def validate(self) -> None:
        if not self.surface_id.strip() or not self.name.strip():
            raise ValueError("SURFACE_IDENTITY_REQUIRED")
        if not self.capabilities:
            raise ValueError("SURFACE_CAPABILITIES_REQUIRED")
        if self.external_effect_default:
            raise ValueError("SURFACE_EXTERNAL_EFFECT_DEFAULT_PROHIBITED")
        if self.freshness_ttl_minutes < 1:
            raise ValueError("SURFACE_FRESHNESS_TTL_INVALID")


@dataclass(frozen=True, slots=True)
class SurfaceAttestation:
    surface_id: str
    present: bool
    direct_route_live: bool
    fallback_route_live: bool
    read_capable: bool
    write_capable: bool
    semantic_readback_ready: bool
    fresh: bool
    proof_refs: tuple[str, ...]
    observed_at: str
    current_authority: str = "A0_READ_ONLY"
    failure_domain: str = ""

    def validate(self) -> None:
        if not self.surface_id.strip():
            raise ValueError("SURFACE_ATTESTATION_ID_REQUIRED")
        if self.present and not self.proof_refs:
            raise ValueError("SURFACE_ATTESTATION_PROOF_REQUIRED")
        if (self.direct_route_live or self.fallback_route_live) and not self.present:
            raise ValueError("SURFACE_ROUTE_WITHOUT_PRESENCE")
        if self.write_capable and not self.read_capable:
            raise ValueError("SURFACE_WRITE_REQUIRES_READ_CAPABILITY")


@dataclass(frozen=True, slots=True)
class SurfaceAction:
    action_id: str
    surface_id: str
    capability: str
    requested_authority: str = "A0_READ_ONLY"
    external_effect: bool = False
    effect_class: str = "NONE"
    authorization_ref: str = ""
    readback_required: bool = True
    rollback_required: bool = False
    explicit_owner_directive: bool = False
    communication_send: bool = False
    public_publish_or_share: bool = False
    financial_or_booking_effect: bool = False
    security_or_credential_effect: bool = False
    irreversible: bool = False

    def validate(self) -> None:
        if not all((self.action_id.strip(), self.surface_id.strip(), self.capability.strip())):
            raise ValueError("SURFACE_ACTION_IDENTITY_REQUIRED")
        if self.external_effect and self.effect_class == "NONE":
            raise ValueError("SURFACE_EXTERNAL_EFFECT_CLASS_REQUIRED")


@dataclass(frozen=True, slots=True)
class SurfaceRouteDecision:
    action_id: str
    surface_id: str
    state: str
    mode: SurfaceMode
    selected_adapter: str = ""
    auto_execute_internal: bool = False
    delegate_to_sovara: bool = False
    human_required: bool = False
    reasons: tuple[str, ...] = field(default_factory=tuple)
    proof_refs: tuple[str, ...] = field(default_factory=tuple)

    @property
    def fingerprint(self) -> str:
        return digest(asdict(self))


_AUTHORITY_RANK = {
    "A0_READ_ONLY": 0,
    "A1_INTERNAL": 1,
    "A2_REVERSIBLE_EXTERNAL": 2,
    "A3_CONSEQUENTIAL": 3,
    "PROVIDER_ACTION": 2,
}


def _rank(value: str) -> int:
    return _AUTHORITY_RANK.get(str(value), 99)


class SurfaceRegistry:
    """Dynamic surface registry. Unknown surfaces fail closed to read-only shadow."""

    def __init__(self, manifests: Sequence[SurfaceManifest]) -> None:
        for item in manifests:
            item.validate()
        if len({item.surface_id for item in manifests}) != len(manifests):
            raise ValueError("DUPLICATE_SURFACE_ID")
        self._manifests = {item.surface_id: item for item in manifests}

    @property
    def surface_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._manifests))

    def manifest(self, surface_id: str) -> SurfaceManifest | None:
        return self._manifests.get(surface_id)

    @staticmethod
    def unknown_shadow(surface_id: str) -> SurfaceManifest:
        return SurfaceManifest(
            surface_id=surface_id,
            name=f"Unverified surface {surface_id}",
            surface_class=SurfaceClass.OTHER,
            capabilities=("DISCOVER", "READ"),
            authority_ceiling="A0_READ_ONLY",
            privacy_ceiling="P3_RESTRICTED",
            external_effect_default=False,
            auto_enroll_unknown=True,
        )


class SovaraDerivedSurfaceRouter:
    """Route FIO work using SOVARA's no-inheritance, safe-lane doctrine."""

    def __init__(self, registry: SurfaceRegistry) -> None:
        self.registry = registry

    @staticmethod
    def _attestation(surface_id: str, attestations: Sequence[SurfaceAttestation]) -> SurfaceAttestation | None:
        for item in attestations:
            if item.surface_id == surface_id:
                item.validate()
                return item
        return None

    def route(self, action: SurfaceAction, attestations: Sequence[SurfaceAttestation]) -> SurfaceRouteDecision:
        action.validate()
        manifest = self.registry.manifest(action.surface_id)
        if manifest is None:
            return SurfaceRouteDecision(
                action.action_id,
                action.surface_id,
                "DISCOVERED_READ_ONLY_SHADOW",
                SurfaceMode.READ_ONLY,
                auto_execute_internal=False,
                reasons=("UNKNOWN_SURFACE_AUTO_ENROLLED_READ_ONLY", "NO_AUTHORITY_INHERITANCE"),
            )
        manifest.validate()
        status = self._attestation(action.surface_id, attestations)
        if status is None or not status.present:
            return SurfaceRouteDecision(
                action.action_id,
                action.surface_id,
                "SURFACE_UNAVAILABLE_HELD",
                SurfaceMode.HELD,
                reasons=("CURRENT_SURFACE_ATTESTATION_REQUIRED",),
            )
        if not status.fresh:
            return SurfaceRouteDecision(
                action.action_id,
                action.surface_id,
                "SURFACE_STALE_DOWNGRADED",
                SurfaceMode.READ_ONLY,
                selected_adapter=manifest.direct_adapter if status.direct_route_live else manifest.fallback_adapter,
                reasons=("SURFACE_PROOF_STALE", "REVALIDATE_BEFORE_EFFECT"),
                proof_refs=status.proof_refs,
            )
        if action.capability not in set(manifest.capabilities):
            return SurfaceRouteDecision(
                action.action_id,
                action.surface_id,
                "CAPABILITY_NOT_EXPOSED",
                SurfaceMode.HELD,
                reasons=("SURFACE_CAPABILITY_MISMATCH",),
                proof_refs=status.proof_refs,
            )
        if _rank(action.requested_authority) > _rank(manifest.authority_ceiling):
            return SurfaceRouteDecision(
                action.action_id,
                action.surface_id,
                "SURFACE_AUTHORITY_CEILING_HELD",
                SurfaceMode.HELD,
                human_required=True,
                reasons=("SURFACE_AUTHORITY_CEILING_EXCEEDED",),
                proof_refs=status.proof_refs,
            )

        selected = ""
        if status.direct_route_live:
            selected = manifest.direct_adapter
        elif status.fallback_route_live:
            selected = manifest.fallback_adapter
        if not selected:
            return SurfaceRouteDecision(
                action.action_id,
                action.surface_id,
                "NO_LIVE_SURFACE_ROUTE",
                SurfaceMode.HELD,
                reasons=("NO_CURRENT_DIRECT_OR_FALLBACK_ROUTE",),
                proof_refs=status.proof_refs,
            )

        if action.communication_send and manifest.explicit_communication_send_only and not action.explicit_owner_directive:
            return SurfaceRouteDecision(
                action.action_id,
                action.surface_id,
                "EXPLICIT_OWNER_DIRECTIVE_REQUIRED",
                SurfaceMode.HELD,
                selected_adapter=selected,
                human_required=True,
                reasons=("COMMUNICATION_SEND_EXPLICIT_ONLY",),
                proof_refs=status.proof_refs,
            )

        consequence_flags = (
            action.communication_send,
            action.public_publish_or_share,
            action.financial_or_booking_effect,
            action.security_or_credential_effect,
            action.irreversible,
        )
        is_external = action.external_effect or any(consequence_flags) or _rank(action.requested_authority) >= 2
        if is_external:
            reasons: list[str] = ["DELEGATE_EFFECT_ADMISSION_TO_SOVARA"]
            if not action.authorization_ref:
                reasons.append("EXACT_AUTHORIZATION_REF_REQUIRED")
            if action.readback_required is not True:
                reasons.append("SEMANTIC_READBACK_REQUIRED")
            if action.rollback_required is False and not action.irreversible:
                reasons.append("ROLLBACK_PLAN_REQUIRED")
            if action.irreversible:
                reasons.append("IRREVERSIBLE_ACTION_HUMAN_REQUIRED")
            return SurfaceRouteDecision(
                action.action_id,
                action.surface_id,
                "DELEGATE_TO_SOVARA" if len(reasons) == 1 else "SOVARA_PREFLIGHT_HELD",
                SurfaceMode.ACTION_SPECIFIC,
                selected_adapter=selected,
                auto_execute_internal=False,
                delegate_to_sovara=True,
                human_required=bool(action.irreversible or len(reasons) > 1),
                reasons=tuple(reasons),
                proof_refs=status.proof_refs,
            )

        if not status.read_capable:
            return SurfaceRouteDecision(
                action.action_id,
                action.surface_id,
                "SURFACE_READ_NOT_PROVEN",
                SurfaceMode.HELD,
                selected_adapter=selected,
                reasons=("READ_CAPABILITY_READBACK_REQUIRED",),
                proof_refs=status.proof_refs,
            )
        if _rank(action.requested_authority) == 1 and not status.write_capable:
            return SurfaceRouteDecision(
                action.action_id,
                action.surface_id,
                "SURFACE_WRITE_NOT_PROVEN",
                SurfaceMode.READ_ONLY,
                selected_adapter=selected,
                reasons=("WRITE_CAPABILITY_READBACK_REQUIRED",),
                proof_refs=status.proof_refs,
            )
        if action.readback_required and not status.semantic_readback_ready:
            return SurfaceRouteDecision(
                action.action_id,
                action.surface_id,
                "SEMANTIC_READBACK_NOT_READY",
                SurfaceMode.HELD,
                selected_adapter=selected,
                reasons=("SURFACE_SEMANTIC_READBACK_REQUIRED",),
                proof_refs=status.proof_refs,
            )

        return SurfaceRouteDecision(
            action.action_id,
            action.surface_id,
            "AUTO_ROUTE_SAFE_INTERNAL",
            SurfaceMode.SAFE_INTERNAL,
            selected_adapter=selected,
            auto_execute_internal=True,
            reasons=("CURRENT_SURFACE_PROOF", "SAFE_WITHIN_SURFACE_AUTHORITY", "NO_AUTHORITY_INHERITANCE"),
            proof_refs=status.proof_refs,
        )

    def route_batch(self, actions: Iterable[SurfaceAction], attestations: Sequence[SurfaceAttestation]) -> tuple[SurfaceRouteDecision, ...]:
        """One failed surface never globally stalls independent actions."""
        return tuple(self.route(action, attestations) for action in actions)


def default_kdv_surface_manifests() -> tuple[SurfaceManifest, ...]:
    """Compact current baseline; KDV remains the live registry for future surfaces."""
    return (
        SurfaceManifest("KDV", "Kim Dataverse", SurfaceClass.CANONICAL_STATE, ("READ", "WRITE", "RECONCILE"), "A1_INTERNAL", "P3_RESTRICTED", "GOOGLE_DRIVE_CONNECTOR", "KDV_FABRIC"),
        SurfaceManifest("GOOGLE_DRIVE", "Google Drive", SurfaceClass.PROVIDER_DATA, ("READ", "WRITE", "SEARCH", "ARTIFACT"), "A2_REVERSIBLE_EXTERNAL", "P3_RESTRICTED", "GOOGLE_DRIVE_CONNECTOR", "APPS_SCRIPT_TRANSPORT"),
        SurfaceManifest("GMAIL", "Gmail", SurfaceClass.COMMUNICATION, ("READ", "SEARCH", "LABEL", "SEND"), "A2_REVERSIBLE_EXTERNAL", "P2_PRIVATE", "GMAIL_CONNECTOR", "", explicit_communication_send_only=True),
        SurfaceManifest("GOOGLE_CALENDAR", "Google Calendar", SurfaceClass.SCHEDULING, ("READ", "SEARCH", "WRITE"), "A2_REVERSIBLE_EXTERNAL", "P2_PRIVATE", "GOOGLE_CALENDAR_CONNECTOR", ""),
        SurfaceManifest("GITHUB", "GitHub", SurfaceClass.SOURCE_CI, ("READ", "WRITE", "BRANCH", "PR", "CI"), "A2_REVERSIBLE_EXTERNAL", "P0_PUBLIC_REPO", "GITHUB_CONNECTOR", "KDV"),
        SurfaceManifest("CANVA", "Canva", SurfaceClass.CREATIVE, ("READ", "WRITE", "GENERATE", "EDIT"), "A1_INTERNAL", "P1_INTERNAL", "CANVA_CONNECTOR", ""),
        SurfaceManifest("OUTLOOK_EMAIL", "Outlook Email", SurfaceClass.COMMUNICATION, ("READ", "SEARCH", "SEND"), "A2_REVERSIBLE_EXTERNAL", "P2_PRIVATE", "OUTLOOK_EMAIL_CONNECTOR", "", explicit_communication_send_only=True),
        SurfaceManifest("OUTLOOK_CALENDAR", "Outlook Calendar", SurfaceClass.SCHEDULING, ("READ", "SEARCH", "WRITE"), "A2_REVERSIBLE_EXTERNAL", "P2_PRIVATE", "OUTLOOK_CALENDAR_CONNECTOR", ""),
        SurfaceManifest("GOOGLE_CLOUD", "Google Cloud", SurfaceClass.PROVIDER_RUNTIME, ("READ", "DEPLOY", "IAM", "PUBSUB", "RUN"), "PROVIDER_ACTION", "P3_RESTRICTED", "FO_OPERATOR", "SOVARA_WIF"),
        SurfaceManifest("OPENAI_PLATFORM", "OpenAI Platform", SurfaceClass.MODEL_PROVIDER, ("READ", "KEY_SETUP", "MODEL_RUN"), "PROVIDER_ACTION", "P2_PRIVATE", "OPENAI_PLATFORM_CONNECTOR", "SOVARA_PROVIDER_CELL"),
    )


__all__ = [
    "SurfaceAction", "SurfaceAttestation", "SurfaceClass", "SurfaceManifest",
    "SurfaceMode", "SurfaceRegistry", "SurfaceRouteDecision",
    "SovaraDerivedSurfaceRouter", "default_kdv_surface_manifests", "digest",
]
