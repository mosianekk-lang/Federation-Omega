from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol
from urllib.parse import quote

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import firestore
from google.oauth2 import id_token as google_id_token

from federation.mobile_gateway.fuse_mobile_v1 import (
    Capability,
    KIM_DATAVERSE_SHEET_ID,
    MobileRequest,
    RouteDecision,
    default_capability_contracts,
)
from services.fuse_mobile_gateway.runtime import (
    DEFAULT_SESSION_TTL_SECONDS,
    ExecutionResult,
    GatewayRuntime,
    RuntimeBindingError,
    VerifiedIdentity,
)
from services.gemini_gateway.app import MetadataIdentity, VertexGeminiClient

CANONICAL_PROJECT_ID = "sov-hybrid-suite"
CANONICAL_PROJECT_NUMBER = "257649435135"
CANONICAL_REGION = "africa-south1"
CANONICAL_SERVICE = "fuse-mobile-gateway"
IAP_ISSUER = "https://cloud.google.com/iap"
IAP_CERTS_URL = "https://www.gstatic.com/iap/verify/public_key"
IAP_EXPECTED_AUDIENCE = (
    f"/projects/{CANONICAL_PROJECT_NUMBER}/locations/{CANONICAL_REGION}/services/{CANONICAL_SERVICE}"
)
DEFAULT_KDV_RANGE = "FUSE_MISSION_CURRENTNESS!A1:N100"
DEVICE_TOKEN_PREFIX = "fmdv1_"
SESSION_TOKEN_PREFIX = "fmsv1_"
DEVICE_COLLECTION = "fuse_mobile_devices"
ENROLLMENT_COLLECTION = "fuse_mobile_enrollments"
SESSION_COLLECTION = "fuse_mobile_sessions"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(ch in "0123456789abcdef" for ch in value.lower())


@dataclass(frozen=True)
class DeviceRecord:
    subject: str
    active: bool


@dataclass(frozen=True)
class SessionRecord:
    subject: str
    device_hash: str
    expires_at_epoch: int


class DeviceRepository(Protocol):
    async def consume_enrollment(self, *, enrollment_hash: str, subject: str, device_hash: str) -> None: ...
    async def put_device(self, *, subject: str, device_hash: str) -> None: ...
    async def get_device(self, device_hash: str) -> DeviceRecord | None: ...
    async def revoke_device(self, device_hash: str) -> None: ...


class SessionRepository(Protocol):
    async def put_session(
        self,
        *,
        session_hash: str,
        subject: str,
        device_hash: str,
        issued_at_epoch: int,
        expires_at_epoch: int,
    ) -> None: ...

    async def get_session(self, session_hash: str) -> SessionRecord | None: ...


class FirestoreDeviceRepository:
    """Hash-only device credential store using the Cloud Run service identity."""

    def __init__(self, client: firestore.Client):
        self.client = client

    async def consume_enrollment(self, *, enrollment_hash: str, subject: str, device_hash: str) -> None:
        def write() -> None:
            transaction = self.client.transaction()
            enrollment_ref = self.client.collection(ENROLLMENT_COLLECTION).document(enrollment_hash)
            device_ref = self.client.collection(DEVICE_COLLECTION).document(device_hash)

            @firestore.transactional
            def consume(tx):
                snapshot = enrollment_ref.get(transaction=tx)
                if snapshot.exists and bool((snapshot.to_dict() or {}).get("consumed")):
                    raise RuntimeBindingError("OWNER_ENROLLMENT_ALREADY_CONSUMED")
                now = int(time.time())
                tx.set(
                    enrollment_ref,
                    {"consumed": True, "subject": subject, "consumed_at_epoch": now},
                )
                tx.set(
                    device_ref,
                    {
                        "subject": subject,
                        "active": True,
                        "issued_at_epoch": now,
                        "identity_source": "ONE_USE_BOOTSTRAP",
                    },
                )

            consume(transaction)

        await asyncio.to_thread(write)

    async def put_device(self, *, subject: str, device_hash: str) -> None:
        def write() -> None:
            self.client.collection(DEVICE_COLLECTION).document(device_hash).set(
                {
                    "subject": subject,
                    "active": True,
                    "issued_at_epoch": int(time.time()),
                    "identity_source": "GOOGLE_IAP",
                }
            )

        await asyncio.to_thread(write)

    async def get_device(self, device_hash: str) -> DeviceRecord | None:
        def read() -> DeviceRecord | None:
            snapshot = self.client.collection(DEVICE_COLLECTION).document(device_hash).get()
            if not snapshot.exists:
                return None
            data = snapshot.to_dict() or {}
            subject = str(data.get("subject") or "")
            if not subject:
                return None
            return DeviceRecord(subject=subject, active=bool(data.get("active")))

        return await asyncio.to_thread(read)

    async def revoke_device(self, device_hash: str) -> None:
        def write() -> None:
            self.client.collection(DEVICE_COLLECTION).document(device_hash).set(
                {"active": False, "revoked_at_epoch": int(time.time())}, merge=True
            )

        await asyncio.to_thread(write)


class FirestoreSessionRepository:
    """Persist only SHA-256 session-token hashes and revocation-relevant metadata."""

    def __init__(self, client: firestore.Client):
        self.client = client

    async def put_session(
        self,
        *,
        session_hash: str,
        subject: str,
        device_hash: str,
        issued_at_epoch: int,
        expires_at_epoch: int,
    ) -> None:
        def write() -> None:
            self.client.collection(SESSION_COLLECTION).document(session_hash).set(
                {
                    "subject": subject,
                    "device_hash": device_hash,
                    "issued_at_epoch": issued_at_epoch,
                    "expires_at_epoch": expires_at_epoch,
                }
            )

        await asyncio.to_thread(write)

    async def get_session(self, session_hash: str) -> SessionRecord | None:
        def read() -> SessionRecord | None:
            snapshot = self.client.collection(SESSION_COLLECTION).document(session_hash).get()
            if not snapshot.exists:
                return None
            data = snapshot.to_dict() or {}
            subject = str(data.get("subject") or "")
            device_hash = str(data.get("device_hash") or "")
            try:
                expires_at_epoch = int(data.get("expires_at_epoch") or 0)
            except (TypeError, ValueError):
                return None
            if not subject or not _is_sha256(device_hash) or expires_at_epoch <= 0:
                return None
            return SessionRecord(
                subject=subject,
                device_hash=device_hash.lower(),
                expires_at_epoch=expires_at_epoch,
            )

        return await asyncio.to_thread(read)


class DeviceCredentialManager:
    """Issue opaque revocable device credentials after a proven owner identity route."""

    def __init__(
        self,
        repository: DeviceRepository,
        *,
        owner_subject: str,
        enrollment_sha256: str | None = None,
        token_factory=None,
    ) -> None:
        if not owner_subject.strip():
            raise ValueError("OWNER_SUBJECT_REQUIRED")
        normalized_enrollment = (enrollment_sha256 or "").lower()
        if normalized_enrollment and not _is_sha256(normalized_enrollment):
            raise ValueError("ENROLLMENT_SHA256_INVALID")
        self.repository = repository
        self.owner_subject = owner_subject.strip()
        self.enrollment_sha256 = normalized_enrollment
        self._token_factory = token_factory or (lambda: DEVICE_TOKEN_PREFIX + secrets.token_urlsafe(32))

    @staticmethod
    def _identity(subject: str, device_hash: str, *, source: str | None = None) -> VerifiedIdentity:
        claims = {"device_id": device_hash[:16], "device_hash": device_hash}
        if source:
            claims["owner_identity_source"] = source
        return VerifiedIdentity(subject, claims)

    def _new_device(self) -> tuple[str, str]:
        device_token = str(self._token_factory())
        if not device_token.startswith(DEVICE_TOKEN_PREFIX) or len(device_token) < len(DEVICE_TOKEN_PREFIX) + 32:
            raise RuntimeBindingError("DEVICE_TOKEN_FACTORY_INVALID")
        return device_token, _sha256(device_token)

    async def enroll(self, credential: str) -> tuple[VerifiedIdentity, str]:
        if not self.enrollment_sha256:
            raise RuntimeBindingError("OWNER_ENROLLMENT_UNBOUND")
        observed = _sha256(credential)
        if not hmac.compare_digest(observed, self.enrollment_sha256):
            raise RuntimeBindingError("OWNER_ENROLLMENT_INVALID")
        device_token, device_hash = self._new_device()
        await self.repository.consume_enrollment(
            enrollment_hash=self.enrollment_sha256,
            subject=self.owner_subject,
            device_hash=device_hash,
        )
        return self._identity(self.owner_subject, device_hash, source="ONE_USE_BOOTSTRAP"), device_token

    async def enroll_verified(self, identity: VerifiedIdentity) -> tuple[VerifiedIdentity, str]:
        if identity.subject != self.owner_subject:
            raise RuntimeBindingError("OWNER_IDENTITY_MISMATCH")
        device_token, device_hash = self._new_device()
        await self.repository.put_device(subject=self.owner_subject, device_hash=device_hash)
        return self._identity(self.owner_subject, device_hash, source="GOOGLE_IAP"), device_token

    async def verify(self, credential: str) -> VerifiedIdentity:
        if not credential.startswith(DEVICE_TOKEN_PREFIX):
            raise RuntimeBindingError("DEVICE_CREDENTIAL_INVALID")
        device_hash = _sha256(credential)
        record = await self.repository.get_device(device_hash)
        if record is None or not record.active:
            raise RuntimeBindingError("DEVICE_CREDENTIAL_INVALID")
        return self._identity(record.subject, device_hash)

    async def revoke(self, credential: str, *, expected_subject: str) -> None:
        identity = await self.verify(credential)
        if identity.subject != expected_subject:
            raise RuntimeBindingError("DEVICE_SUBJECT_MISMATCH")
        await self.repository.revoke_device(_sha256(credential))


class IAPOwnerIdentityVerifier:
    """Verify the signed IAP assertion for exactly one configured owner account."""

    def __init__(
        self,
        *,
        owner_subject: str,
        owner_email_sha256: str,
        audience: str = IAP_EXPECTED_AUDIENCE,
        verify_fn: Callable[[str, str], dict[str, Any]] | None = None,
    ) -> None:
        if not owner_subject.strip():
            raise ValueError("OWNER_SUBJECT_REQUIRED")
        if not _is_sha256(owner_email_sha256):
            raise ValueError("OWNER_EMAIL_SHA256_REQUIRED")
        if audience != IAP_EXPECTED_AUDIENCE:
            raise ValueError("IAP_AUDIENCE_MISMATCH")
        self.owner_subject = owner_subject.strip()
        self.owner_email_sha256 = owner_email_sha256.lower()
        self.audience = audience
        self._verify_fn = verify_fn or self._verify_google_assertion

    @staticmethod
    def _verify_google_assertion(assertion: str, audience: str) -> dict[str, Any]:
        return google_id_token.verify_token(
            assertion,
            GoogleAuthRequest(),
            audience=audience,
            certs_url=IAP_CERTS_URL,
        )

    async def verify_assertion(self, assertion: str) -> VerifiedIdentity:
        if not assertion.strip():
            raise RuntimeBindingError("IAP_ASSERTION_REQUIRED")
        try:
            payload = await asyncio.to_thread(self._verify_fn, assertion, self.audience)
        except Exception as exc:
            raise RuntimeBindingError("IAP_ASSERTION_INVALID") from exc
        if str(payload.get("iss") or "") != IAP_ISSUER:
            raise RuntimeBindingError("IAP_ISSUER_INVALID")
        if str(payload.get("aud") or "") != self.audience:
            raise RuntimeBindingError("IAP_AUDIENCE_INVALID")
        email = str(payload.get("email") or "").strip().lower()
        if not email or not hmac.compare_digest(_sha256(email), self.owner_email_sha256):
            raise RuntimeBindingError("IAP_OWNER_EMAIL_INVALID")
        iap_subject = str(payload.get("sub") or "").strip()
        if not iap_subject:
            raise RuntimeBindingError("IAP_SUBJECT_MISSING")
        return VerifiedIdentity(
            self.owner_subject,
            {"auth_source": "GOOGLE_IAP", "iap_subject_sha256": _sha256(iap_subject)},
        )


class OpaqueSessionManager:
    """Short-lived random bearer sessions backed by hash-only Firestore records."""

    def __init__(
        self,
        repository: SessionRepository,
        devices: DeviceRepository,
        *,
        ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
        token_factory=None,
        clock=None,
    ) -> None:
        if ttl_seconds <= 0 or ttl_seconds > 3600:
            raise ValueError("SESSION_TTL_OUT_OF_RANGE")
        self.repository = repository
        self.devices = devices
        self.ttl_seconds = ttl_seconds
        self._token_factory = token_factory or (lambda: SESSION_TOKEN_PREFIX + secrets.token_urlsafe(32))
        self._clock = clock or (lambda: int(time.time()))

    async def issue(self, identity: VerifiedIdentity) -> tuple[str, int]:
        device_hash = str(identity.claims.get("device_hash") or "").lower()
        if not _is_sha256(device_hash):
            raise RuntimeBindingError("SESSION_DEVICE_BINDING_REQUIRED")
        record = await self.devices.get_device(device_hash)
        if record is None or not record.active:
            raise RuntimeBindingError("SESSION_DEVICE_REVOKED")
        if record.subject != identity.subject:
            raise RuntimeBindingError("SESSION_SUBJECT_MISMATCH")
        token = str(self._token_factory())
        if not token.startswith(SESSION_TOKEN_PREFIX) or len(token) < len(SESSION_TOKEN_PREFIX) + 32:
            raise RuntimeBindingError("SESSION_TOKEN_FACTORY_INVALID")
        issued_at = int(self._clock())
        expires_at = issued_at + self.ttl_seconds
        await self.repository.put_session(
            session_hash=_sha256(token),
            subject=identity.subject,
            device_hash=device_hash,
            issued_at_epoch=issued_at,
            expires_at_epoch=expires_at,
        )
        return token, expires_at

    async def verify(self, token: str) -> VerifiedIdentity:
        if not token.startswith(SESSION_TOKEN_PREFIX) or len(token) < len(SESSION_TOKEN_PREFIX) + 32:
            raise RuntimeBindingError("SESSION_INVALID")
        session = await self.repository.get_session(_sha256(token))
        if session is None:
            raise RuntimeBindingError("SESSION_INVALID")
        if session.expires_at_epoch <= int(self._clock()):
            raise RuntimeBindingError("SESSION_EXPIRED")
        device = await self.devices.get_device(session.device_hash)
        if device is None or not device.active:
            raise RuntimeBindingError("SESSION_DEVICE_REVOKED")
        if device.subject != session.subject:
            raise RuntimeBindingError("SESSION_SUBJECT_MISMATCH")
        return VerifiedIdentity(
            session.subject,
            {"device_id": session.device_hash[:16], "device_hash": session.device_hash},
        )


@dataclass(frozen=True)
class KDVSnapshot:
    source_ref: str
    range_name: str
    observed_at: str
    rows: tuple[dict[str, str], ...]
    fresh_count: int
    stale_count: int

    def compact_context(self, *, max_rows: int = 12) -> str:
        payload = {
            "source_ref": self.source_ref,
            "range": self.range_name,
            "observed_at": self.observed_at,
            "fresh_count": self.fresh_count,
            "stale_count": self.stale_count,
            "rows": list(self.rows[:max_rows]),
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)


class KDVSheetsReader:
    def __init__(
        self,
        identity: MetadataIdentity,
        *,
        spreadsheet_id: str = KIM_DATAVERSE_SHEET_ID,
        range_name: str = DEFAULT_KDV_RANGE,
        client_factory=None,
    ) -> None:
        self.identity = identity
        self.spreadsheet_id = spreadsheet_id
        self.range_name = range_name
        self._client_factory = client_factory or (lambda: httpx.AsyncClient(timeout=15.0))

    @staticmethod
    def _rows(values: list[list[Any]], *, now: datetime | None = None) -> tuple[tuple[dict[str, str], ...], int, int]:
        if not values:
            return (), 0, 0
        headers = [str(value) for value in values[0]]
        current = now or datetime.now(timezone.utc)
        rows: list[dict[str, str]] = []
        fresh = 0
        stale = 0
        for raw in values[1:]:
            padded = list(raw) + [""] * max(0, len(headers) - len(raw))
            row = {headers[index]: str(padded[index]) for index in range(len(headers))}
            if not any(row.values()):
                continue
            expiry_raw = row.get("Expires_At_SAST", "").strip()
            freshness = "UNKNOWN"
            if expiry_raw:
                try:
                    expiry = datetime.fromisoformat(expiry_raw)
                    if expiry.tzinfo is None:
                        expiry = expiry.replace(tzinfo=timezone.utc)
                    freshness = "FRESH" if expiry > current else "STALE"
                except ValueError:
                    freshness = "UNKNOWN"
            row["_runtime_freshness"] = freshness
            fresh += int(freshness == "FRESH")
            stale += int(freshness == "STALE")
            rows.append(row)
        return tuple(rows), fresh, stale

    async def read(self) -> KDVSnapshot:
        token = await asyncio.to_thread(self.identity.access_token)
        encoded_range = quote(self.range_name, safe="")
        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/{self.spreadsheet_id}/"
            f"values/{encoded_range}?majorDimension=ROWS&valueRenderOption=FORMATTED_VALUE"
        )
        async with self._client_factory() as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeBindingError("KDV_READ_FAILED")
        payload = response.json()
        values = payload.get("values")
        if not isinstance(values, list):
            raise RuntimeBindingError("KDV_VALUES_INVALID")
        rows, fresh, stale = self._rows(values)
        return KDVSnapshot(
            source_ref=f"KDV:{self.spreadsheet_id}:{self.range_name}",
            range_name=self.range_name,
            observed_at=datetime.now(timezone.utc).isoformat(),
            rows=rows,
            fresh_count=fresh,
            stale_count=stale,
        )


class RuntimeCapabilityHealth:
    def __init__(self, kdv: KDVSheetsReader, identity: MetadataIdentity):
        self.kdv = kdv
        self.identity = identity

    async def capabilities(self, identity: VerifiedIdentity) -> tuple[Capability, ...]:
        del identity
        contracts = list(default_capability_contracts())
        try:
            snapshot = await self.kdv.read()
            kdv_health = "RUNTIME_VERIFIED"
            kdv_authority = f"READ_ONLY;FRESH={snapshot.fresh_count};STALE={snapshot.stale_count}"
        except Exception:
            kdv_health = "DEGRADED"
            kdv_authority = "READ_ONLY_UNVERIFIED"
        try:
            provider_identity = await asyncio.to_thread(self.identity.snapshot)
            vertex_health = "CONNECTED"
            vertex_authority = f"ADC:{provider_identity['service_account']}"
        except Exception:
            vertex_health = "DEGRADED"
            vertex_authority = "ADC_UNVERIFIED"
        rendered: list[Capability] = []
        for capability in contracts:
            if capability.capability_id == "KDV":
                rendered.append(
                    Capability(
                        capability.capability_id,
                        capability.kind,
                        capability.route,
                        health=kdv_health,
                        authority=kdv_authority,
                        freshness_ttl_seconds=60,
                    )
                )
            else:
                rendered.append(capability)
        rendered.append(
            Capability(
                "GOOGLE-VERTEX-GEMINI",
                "MODEL_PROVIDER",
                "services.gemini_gateway.VertexGeminiClient",
                health=vertex_health,
                authority=vertex_authority,
                freshness_ttl_seconds=60,
            )
        )
        return tuple(rendered)


class VertexKDVChatExecutor:
    def __init__(self, kdv: KDVSheetsReader, vertex: VertexGeminiClient):
        self.kdv = kdv
        self.vertex = vertex

    async def execute(
        self,
        *,
        request: MobileRequest,
        decision: RouteDecision,
        identity: VerifiedIdentity,
    ) -> ExecutionResult:
        snapshot = await self.kdv.read()
        prompt = (
            "You are the bounded FUSE Mobile read-only response executor. "
            "Answer the owner's request using the supplied Kim Dataverse context where relevant. "
            "Rows marked STALE are historical evidence only and must never be represented as current. "
            "Do not claim external effects were executed.\n\n"
            f"Owner subject: {identity.subject}\n"
            f"Compiled route: {decision.strategy} / {','.join(decision.components)}\n"
            f"Kim Dataverse context: {snapshot.compact_context()}\n\n"
            f"Owner request: {request.intent}"
        )
        provider = await asyncio.to_thread(
            self.vertex.generate,
            prompt=prompt,
            temperature=0.0,
            max_output_tokens=1024,
        )
        return ExecutionResult(
            text=str(provider.get("text") or ""),
            trace_id=str(provider["provider_request_id"]),
            provider=str(provider["provider"]),
            model=str(provider["model_identity"]),
            source_refs=(snapshot.source_ref,),
        )


def runtime_from_environment() -> GatewayRuntime:
    """Bind production adapters only when a complete private owner route is configured."""

    owner_subject = os.getenv("FUSE_MOBILE_OWNER_SUBJECT", "").strip()
    enrollment_sha256 = os.getenv("FUSE_MOBILE_OWNER_ENROLLMENT_SHA256", "").strip().lower()
    owner_email_sha256 = os.getenv("FUSE_MOBILE_OWNER_EMAIL_SHA256", "").strip().lower()
    if not any((owner_subject, enrollment_sha256, owner_email_sha256)):
        return GatewayRuntime()
    if not owner_subject or (not enrollment_sha256 and not owner_email_sha256):
        raise RuntimeBindingError("RUNTIME_CONFIGURATION_INCOMPLETE")
    if enrollment_sha256 and not _is_sha256(enrollment_sha256):
        raise RuntimeBindingError("RUNTIME_CONFIGURATION_INCOMPLETE")
    if owner_email_sha256 and not _is_sha256(owner_email_sha256):
        raise RuntimeBindingError("RUNTIME_CONFIGURATION_INCOMPLETE")
    project = os.getenv("GOOGLE_CLOUD_PROJECT", CANONICAL_PROJECT_ID).strip()
    if project != CANONICAL_PROJECT_ID:
        raise RuntimeBindingError("CANONICAL_PROJECT_MISMATCH")

    client = firestore.Client(project=project)
    device_repository = FirestoreDeviceRepository(client)
    session_repository = FirestoreSessionRepository(client)
    manager = DeviceCredentialManager(
        device_repository,
        owner_subject=owner_subject,
        enrollment_sha256=enrollment_sha256 or None,
    )
    session_manager = OpaqueSessionManager(session_repository, device_repository)
    metadata_identity = MetadataIdentity()
    kdv = KDVSheetsReader(
        metadata_identity,
        range_name=os.getenv("FUSE_MOBILE_KDV_RANGE", DEFAULT_KDV_RANGE).strip() or DEFAULT_KDV_RANGE,
    )
    vertex = VertexGeminiClient(metadata_identity)
    runtime = GatewayRuntime(
        session_manager=session_manager,
        identity_verifier=manager,
        device_manager=manager,
        health_provider=RuntimeCapabilityHealth(kdv, metadata_identity),
        chat_executor=VertexKDVChatExecutor(kdv, vertex),
    )
    if owner_email_sha256:
        runtime.owner_identity_verifier = IAPOwnerIdentityVerifier(
            owner_subject=owner_subject,
            owner_email_sha256=owner_email_sha256,
        )
    return runtime
