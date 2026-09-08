from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import quote

import httpx
from google.cloud import firestore

from federation.mobile_gateway.fuse_mobile_v1 import (
    Capability,
    KIM_DATAVERSE_SHEET_ID,
    MobileRequest,
    RouteDecision,
    default_capability_contracts,
)
from services.fuse_mobile_gateway.runtime import (
    ExecutionResult,
    GatewayRuntime,
    RuntimeBindingError,
    SessionCodec,
    VerifiedIdentity,
)
from services.gemini_gateway.app import MetadataIdentity, VertexGeminiClient

CANONICAL_PROJECT_ID = "sov-hybrid-suite"
DEFAULT_KDV_RANGE = "FUSE_MISSION_CURRENTNESS!A1:N100"
DEVICE_TOKEN_PREFIX = "fmdv1_"
DEVICE_COLLECTION = "fuse_mobile_devices"
ENROLLMENT_COLLECTION = "fuse_mobile_enrollments"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DeviceRecord:
    subject: str
    active: bool


class DeviceRepository(Protocol):
    async def consume_enrollment(self, *, enrollment_hash: str, subject: str, device_hash: str) -> None: ...
    async def get_device(self, device_hash: str) -> DeviceRecord | None: ...
    async def revoke_device(self, device_hash: str) -> None: ...


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
                    {
                        "consumed": True,
                        "subject": subject,
                        "consumed_at_epoch": now,
                    },
                )
                tx.set(
                    device_ref,
                    {
                        "subject": subject,
                        "active": True,
                        "issued_at_epoch": now,
                    },
                )

            consume(transaction)

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


class DeviceCredentialManager:
    """One-use owner enrollment followed by opaque, revocable device credentials."""

    def __init__(
        self,
        repository: DeviceRepository,
        *,
        owner_subject: str,
        enrollment_sha256: str,
        token_factory=None,
    ) -> None:
        if not owner_subject.strip():
            raise ValueError("OWNER_SUBJECT_REQUIRED")
        if len(enrollment_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in enrollment_sha256.lower()):
            raise ValueError("ENROLLMENT_SHA256_REQUIRED")
        self.repository = repository
        self.owner_subject = owner_subject.strip()
        self.enrollment_sha256 = enrollment_sha256.lower()
        self._token_factory = token_factory or (lambda: DEVICE_TOKEN_PREFIX + secrets.token_urlsafe(32))

    async def enroll(self, credential: str) -> tuple[VerifiedIdentity, str]:
        observed = _sha256(credential)
        if not hmac.compare_digest(observed, self.enrollment_sha256):
            raise RuntimeBindingError("OWNER_ENROLLMENT_INVALID")
        device_token = str(self._token_factory())
        if not device_token.startswith(DEVICE_TOKEN_PREFIX) or len(device_token) < len(DEVICE_TOKEN_PREFIX) + 32:
            raise RuntimeBindingError("DEVICE_TOKEN_FACTORY_INVALID")
        device_hash = _sha256(device_token)
        await self.repository.consume_enrollment(
            enrollment_hash=self.enrollment_sha256,
            subject=self.owner_subject,
            device_hash=device_hash,
        )
        return VerifiedIdentity(self.owner_subject, {"device_id": device_hash[:16]}), device_token

    async def verify(self, credential: str) -> VerifiedIdentity:
        if not credential.startswith(DEVICE_TOKEN_PREFIX):
            raise RuntimeBindingError("DEVICE_CREDENTIAL_INVALID")
        device_hash = _sha256(credential)
        record = await self.repository.get_device(device_hash)
        if record is None or not record.active:
            raise RuntimeBindingError("DEVICE_CREDENTIAL_INVALID")
        return VerifiedIdentity(record.subject, {"device_id": device_hash[:16]})

    async def revoke(self, credential: str, *, expected_subject: str) -> None:
        identity = await self.verify(credential)
        if identity.subject != expected_subject:
            raise RuntimeBindingError("DEVICE_SUBJECT_MISMATCH")
        await self.repository.revoke_device(_sha256(credential))


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
        observed_at = datetime.now(timezone.utc).isoformat()
        return KDVSnapshot(
            source_ref=f"KDV:{self.spreadsheet_id}:{self.range_name}",
            range_name=self.range_name,
            observed_at=observed_at,
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


def _decode_session_secret(raw: str) -> bytes:
    try:
        secret = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except Exception as exc:
        raise RuntimeBindingError("SESSION_SECRET_INVALID") from exc
    if len(secret) < 32:
        raise RuntimeBindingError("SESSION_SECRET_INVALID")
    return secret


def runtime_from_environment() -> GatewayRuntime:
    """Bind production adapters only when the complete private runtime contract is configured."""

    required = {
        "FUSE_MOBILE_SESSION_SECRET_B64": os.getenv("FUSE_MOBILE_SESSION_SECRET_B64", "").strip(),
        "FUSE_MOBILE_OWNER_SUBJECT": os.getenv("FUSE_MOBILE_OWNER_SUBJECT", "").strip(),
        "FUSE_MOBILE_OWNER_ENROLLMENT_SHA256": os.getenv("FUSE_MOBILE_OWNER_ENROLLMENT_SHA256", "").strip().lower(),
    }
    if not any(required.values()):
        return GatewayRuntime()
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeBindingError("RUNTIME_CONFIGURATION_INCOMPLETE")

    project = os.getenv("GOOGLE_CLOUD_PROJECT", CANONICAL_PROJECT_ID).strip()
    if project != CANONICAL_PROJECT_ID:
        raise RuntimeBindingError("CANONICAL_PROJECT_MISMATCH")

    session_codec = SessionCodec(_decode_session_secret(required["FUSE_MOBILE_SESSION_SECRET_B64"]))
    repository = FirestoreDeviceRepository(firestore.Client(project=project))
    manager = DeviceCredentialManager(
        repository,
        owner_subject=required["FUSE_MOBILE_OWNER_SUBJECT"],
        enrollment_sha256=required["FUSE_MOBILE_OWNER_ENROLLMENT_SHA256"],
    )
    metadata_identity = MetadataIdentity()
    kdv = KDVSheetsReader(
        metadata_identity,
        range_name=os.getenv("FUSE_MOBILE_KDV_RANGE", DEFAULT_KDV_RANGE).strip() or DEFAULT_KDV_RANGE,
    )
    vertex = VertexGeminiClient(metadata_identity)
    return GatewayRuntime(
        session_codec=session_codec,
        identity_verifier=manager,
        device_manager=manager,
        health_provider=RuntimeCapabilityHealth(kdv, metadata_identity),
        chat_executor=VertexKDVChatExecutor(kdv, vertex),
    )
