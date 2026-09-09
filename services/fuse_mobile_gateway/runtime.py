from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from federation.mobile_gateway.fuse_mobile_v1 import (
    Capability,
    EffectClass,
    FederationCapabilityManifest,
    MobileRequest,
    RouteDecision,
    default_capability_contracts,
    route_request,
)

SESSION_SCHEMA = "FUSE_MOBILE_SESSION_V1"
SESSION_ISSUER = "fuse-mobile-gateway"
SESSION_AUDIENCE = "fuse-mobile"
DEFAULT_SESSION_TTL_SECONDS = 900


class RuntimeBindingError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class VerifiedIdentity:
    subject: str
    claims: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionResult:
    text: str
    trace_id: str
    status: str = "COMPLETE"
    provider: str | None = None
    model: str | None = None
    source_refs: tuple[str, ...] = field(default_factory=tuple)


class IdentityVerifier(Protocol):
    async def verify(self, credential: str) -> VerifiedIdentity: ...


class OwnerIdentityVerifier(Protocol):
    async def verify_assertion(self, assertion: str) -> VerifiedIdentity: ...


class DeviceCredentialManagerProtocol(Protocol):
    async def enroll(self, credential: str) -> tuple[VerifiedIdentity, str]: ...
    async def enroll_verified(self, identity: VerifiedIdentity) -> tuple[VerifiedIdentity, str]: ...
    async def verify(self, credential: str) -> VerifiedIdentity: ...
    async def revoke(self, credential: str, *, expected_subject: str) -> None: ...


class SessionManagerProtocol(Protocol):
    async def issue(self, identity: VerifiedIdentity) -> tuple[str, int]: ...
    async def verify(self, token: str) -> VerifiedIdentity: ...


class ChatExecutor(Protocol):
    async def execute(
        self,
        *,
        request: MobileRequest,
        decision: RouteDecision,
        identity: VerifiedIdentity,
    ) -> ExecutionResult: ...


class CapabilityHealthProvider(Protocol):
    async def capabilities(self, identity: VerifiedIdentity) -> tuple[Capability, ...]: ...


class DisabledIdentityVerifier:
    async def verify(self, credential: str) -> VerifiedIdentity:
        del credential
        raise RuntimeBindingError("IDENTITY_VERIFIER_UNBOUND")


class DisabledOwnerIdentityVerifier:
    async def verify_assertion(self, assertion: str) -> VerifiedIdentity:
        del assertion
        raise RuntimeBindingError("OWNER_IAP_VERIFIER_UNBOUND")


class DisabledChatExecutor:
    async def execute(
        self,
        *,
        request: MobileRequest,
        decision: RouteDecision,
        identity: VerifiedIdentity,
    ) -> ExecutionResult:
        del request, decision, identity
        raise RuntimeBindingError("FEDERATION_EXECUTOR_UNBOUND")


class SourceOnlyCapabilityHealth:
    """Expose source presence without promoting provider/runtime maturity."""

    async def capabilities(self, identity: VerifiedIdentity) -> tuple[Capability, ...]:
        del identity
        contracts = list(default_capability_contracts())
        contracts.extend(
            [
                Capability(
                    "GOOGLE-AI-STUDIO-GEMINI-DEVELOPER-API",
                    "MODEL_PROVIDER",
                    ".github/workflows/sovara-ai-studio-semantic-canary.yml",
                    health="CONFIGURED",
                    authority="ACTION_SPECIFIC_UNPROVEN",
                    freshness_ttl_seconds=0,
                ),
                Capability(
                    "SOVARA-GEMINI-GATEWAY",
                    "MODEL_PROVIDER",
                    "services/gemini_gateway",
                    health="CONFIGURED",
                    authority="PRIVATE_RUNTIME_PROOF_REQUIRED",
                    freshness_ttl_seconds=0,
                ),
                Capability(
                    "FEDERATION-OMEGA-OPERATOR",
                    "INTERNAL_EXECUTION_CONTROL",
                    "ops/federation_omega_operator",
                    health="CONFIGURED",
                    authority="SERVER_SIDE_ONLY",
                    freshness_ttl_seconds=0,
                ),
            ]
        )
        return tuple(
            Capability(
                c.capability_id,
                c.kind,
                c.route,
                health=c.health if c.health != "UNKNOWN" else "CONFIGURED",
                authority=c.authority,
                freshness_ttl_seconds=c.freshness_ttl_seconds,
            )
            for c in contracts
        )


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


class SessionCodec:
    """Legacy deterministic HMAC codec retained for compatibility and unit courts.

    Production FUSE Mobile runtime uses a stateful SessionManagerProtocol so a
    previously-issued session can be invalidated when its bound device is revoked.
    """

    def __init__(self, secret: bytes, *, ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS):
        if len(secret) < 32:
            raise ValueError("SESSION_SECRET_TOO_SHORT")
        if ttl_seconds <= 0 or ttl_seconds > 3600:
            raise ValueError("SESSION_TTL_OUT_OF_RANGE")
        self._secret = secret
        self._ttl_seconds = ttl_seconds

    def issue(self, identity: VerifiedIdentity, *, now: int | None = None) -> tuple[str, int]:
        issued_at = int(time.time() if now is None else now)
        expires_at = issued_at + self._ttl_seconds
        payload = {
            "schema": SESSION_SCHEMA,
            "iss": SESSION_ISSUER,
            "aud": SESSION_AUDIENCE,
            "sub": identity.subject,
            "iat": issued_at,
            "exp": expires_at,
            "jti": secrets.token_hex(16),
        }
        encoded = _b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        signature = _b64encode(hmac.new(self._secret, encoded.encode(), hashlib.sha256).digest())
        return f"{encoded}.{signature}", expires_at

    def verify(self, token: str, *, now: int | None = None) -> VerifiedIdentity:
        try:
            encoded, supplied_signature = token.split(".", 1)
            expected_signature = _b64encode(hmac.new(self._secret, encoded.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(supplied_signature, expected_signature):
                raise RuntimeBindingError("SESSION_SIGNATURE_INVALID")
            payload = json.loads(_b64decode(encoded).decode())
        except RuntimeBindingError:
            raise
        except Exception as exc:
            raise RuntimeBindingError("SESSION_MALFORMED") from exc

        current = int(time.time() if now is None else now)
        if payload.get("schema") != SESSION_SCHEMA:
            raise RuntimeBindingError("SESSION_SCHEMA_INVALID")
        if payload.get("iss") != SESSION_ISSUER or payload.get("aud") != SESSION_AUDIENCE:
            raise RuntimeBindingError("SESSION_SCOPE_INVALID")
        if not payload.get("sub"):
            raise RuntimeBindingError("SESSION_SUBJECT_MISSING")
        if int(payload.get("exp", 0)) <= current:
            raise RuntimeBindingError("SESSION_EXPIRED")
        return VerifiedIdentity(subject=str(payload["sub"]))


@dataclass
class GatewayRuntime:
    session_codec: SessionCodec | None = None
    session_manager: SessionManagerProtocol | None = None
    identity_verifier: IdentityVerifier = field(default_factory=DisabledIdentityVerifier)
    owner_identity_verifier: OwnerIdentityVerifier = field(default_factory=DisabledOwnerIdentityVerifier)
    device_manager: DeviceCredentialManagerProtocol | None = None
    health_provider: CapabilityHealthProvider = field(default_factory=SourceOnlyCapabilityHealth)
    chat_executor: ChatExecutor = field(default_factory=DisabledChatExecutor)
    source_scopes: tuple[str, ...] = ("KDV",)
    model_scopes: tuple[str, ...] = ("AUTO", "GOOGLE_AI_STUDIO", "GEMINI_VERTEX", "OPENROUTER")
    agent_scopes: tuple[str, ...] = ("FUSE", "FIO", "SOVARA", "BUBBLES")
    tool_scopes: tuple[str, ...] = ("KDV", "PROOFOS", "ARTIFACTS")

    @property
    def _session_backend_ready(self) -> bool:
        return self.session_manager is not None or self.session_codec is not None

    @property
    def session_ready(self) -> bool:
        return self._session_backend_ready and not isinstance(self.identity_verifier, DisabledIdentityVerifier)

    @property
    def enrollment_ready(self) -> bool:
        return self._session_backend_ready and self.device_manager is not None

    @property
    def iap_enrollment_ready(self) -> bool:
        return self.enrollment_ready and not isinstance(self.owner_identity_verifier, DisabledOwnerIdentityVerifier)

    @property
    def execution_ready(self) -> bool:
        return not isinstance(self.chat_executor, DisabledChatExecutor)

    async def _session_response(self, identity: VerifiedIdentity) -> dict:
        if self.session_manager is not None:
            token, expires_epoch = await self.session_manager.issue(identity)
        elif self.session_codec is not None:
            token, expires_epoch = self.session_codec.issue(identity)
        else:
            raise RuntimeBindingError("SESSION_SIGNER_UNBOUND")
        return {
            "schema": SESSION_SCHEMA,
            "access_token": token,
            "token_type": "Bearer",
            "expires_at": datetime.fromtimestamp(expires_epoch, tz=timezone.utc).isoformat(),
            "subject": identity.subject,
        }

    async def enroll_device(self, credential: str) -> dict:
        if self.device_manager is None or not self._session_backend_ready:
            raise RuntimeBindingError("OWNER_ENROLLMENT_UNBOUND")
        identity, device_token = await self.device_manager.enroll(credential)
        response = await self._session_response(identity)
        response.update(
            {
                "device_token": device_token,
                "device_token_type": "FUSE-Device",
                "device_token_recoverable": False,
            }
        )
        return response

    async def enroll_iap_owner(self, assertion: str) -> dict:
        if not self.iap_enrollment_ready or self.device_manager is None:
            raise RuntimeBindingError("OWNER_IAP_ENROLLMENT_UNBOUND")
        identity = await self.owner_identity_verifier.verify_assertion(assertion)
        identity, device_token = await self.device_manager.enroll_verified(identity)
        response = await self._session_response(identity)
        response.update(
            {
                "device_token": device_token,
                "device_token_type": "FUSE-Device",
                "device_token_recoverable": False,
                "owner_identity_source": "GOOGLE_IAP",
            }
        )
        return response

    async def issue_session(self, credential: str) -> dict:
        if not self._session_backend_ready:
            raise RuntimeBindingError("SESSION_SIGNER_UNBOUND")
        identity = await self.identity_verifier.verify(credential)
        return await self._session_response(identity)

    async def revoke_device(self, identity: VerifiedIdentity, credential: str) -> None:
        if self.device_manager is None:
            raise RuntimeBindingError("DEVICE_REVOCATION_UNBOUND")
        await self.device_manager.revoke(credential, expected_subject=identity.subject)

    async def verify_session(self, token: str) -> VerifiedIdentity:
        if self.session_manager is not None:
            return await self.session_manager.verify(token)
        if self.session_codec is not None:
            return self.session_codec.verify(token)
        raise RuntimeBindingError("SESSION_SIGNER_UNBOUND")

    async def manifest(self, identity: VerifiedIdentity) -> FederationCapabilityManifest:
        now = int(time.time())
        capabilities = await self.health_provider.capabilities(identity)
        return FederationCapabilityManifest(
            subject=identity.subject,
            issued_at=datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
            expires_at=datetime.fromtimestamp(now + 300, tz=timezone.utc).isoformat(),
            capabilities=capabilities,
            source_scopes=self.source_scopes,
            model_scopes=self.model_scopes,
            agent_scopes=self.agent_scopes,
            tool_scopes=self.tool_scopes,
            policies={
                "external_effects": "OWNER_GATED",
                "provider_credentials": "SERVER_SIDE_ONLY",
                "private_data": "MINIMUM_SUFFICIENT_ROUTING",
                "provider_health": "FRESH_READBACK_REQUIRED",
                "device_credentials": "OPAQUE_HASHED_SERVER_SIDE_REVOCABLE",
                "session_credentials": "OPAQUE_HASH_ONLY_DEVICE_BOUND_REVOCABLE",
                "private_transport": "GOOGLE_IAP_IDENTITY_PLUS_FUSE_SESSION",
            },
        )

    async def execute(self, identity: VerifiedIdentity, request: MobileRequest) -> ExecutionResult:
        manifest = await self.manifest(identity)
        decision = route_request(request, manifest)
        if decision.owner_gate_required or not decision.effect_allowed:
            raise RuntimeBindingError("OWNER_EFFECT_APPROVAL_REQUIRED")
        return await self.chat_executor.execute(request=request, decision=decision, identity=identity)


def bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise RuntimeBindingError("AUTHORIZATION_REQUIRED")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise RuntimeBindingError("BEARER_TOKEN_REQUIRED")
    return token.strip()


def effect_from_string(value: str) -> EffectClass:
    try:
        return EffectClass(value)
    except ValueError as exc:
        raise RuntimeBindingError("EFFECT_CLASS_INVALID") from exc
