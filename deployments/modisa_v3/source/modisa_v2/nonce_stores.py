"""Fail-closed replay nonce stores for authenticated MODISA webhooks."""

from __future__ import annotations

import hashlib
import importlib
import os
import re
import secrets
import sqlite3
import ssl
import stat
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import unquote, urlsplit

from .config import Settings

NONCE_DIGEST = re.compile(r"^[0-9a-f]{64}$")
REDIS_KEY_PREFIX = "modisa:webhook:nonce:v1:"
REDIS_DOMAIN = b"MODISA-REDIS-NONCE-V1\0"
NonceStoreKind = Literal["sqlite", "redis", "injected"]
ReplayScope = Literal["node_local_sqlite", "shared_redis"]
BackendStatus = Literal["unconfigured", "unproven", "ready", "unavailable"]


class NonceStoreUnavailable(RuntimeError):
    """The nonce backend cannot make a certain consume-once decision."""


class NonceStore(Protocol):
    kind: NonceStoreKind
    replay_scope: ReplayScope
    backend_configured: bool
    provider_proven: bool
    backend_status: BackendStatus

    def consume_once(
        self, *, key_id: str, nonce_sha256: str, expires_at: int, now: int
    ) -> bool:
        """Atomically return true only for a previously unseen, unexpired nonce."""


class RedisClient(Protocol):
    def set(self, name: str, value: bytes, *, nx: bool, ex: int) -> Any:
        """Perform Redis SET with explicit NX and EX options."""


class SQLiteNonceStore:
    """Durable node-local replay prevention using SQLite uniqueness."""

    kind: NonceStoreKind = "sqlite"
    replay_scope: ReplayScope = "node_local_sqlite"
    backend_configured = True
    provider_proven = False
    backend_status: BackendStatus = "ready"

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path.parent, 0o700)
        with sqlite3.connect(self.path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_nonces (
                    key_id TEXT NOT NULL,
                    nonce_sha256 TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    PRIMARY KEY(key_id, nonce_sha256)
                )
                """
            )
        os.chmod(self.path, 0o600)
        if stat.S_IMODE(self.path.stat().st_mode) != 0o600:
            raise NonceStoreUnavailable("Webhook nonce database permissions are unsafe")

    def consume_once(
        self, *, key_id: str, nonce_sha256: str, expires_at: int, now: int
    ) -> bool:
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM webhook_nonces WHERE expires_at < ?", (now,))
            try:
                conn.execute(
                    "INSERT INTO webhook_nonces(key_id,nonce_sha256,expires_at,created_at) "
                    "VALUES(?,?,?,?)",
                    (key_id, nonce_sha256, expires_at, now),
                )
            except sqlite3.IntegrityError:
                conn.rollback()
                return False
            conn.commit()
            return True
        finally:
            conn.close()


class RedisNonceStore:
    """Shared replay boundary backed by one atomic ``SET NX EX`` operation."""

    kind: NonceStoreKind = "redis"
    replay_scope: ReplayScope = "shared_redis"
    backend_configured = True

    def __init__(
        self,
        client: RedisClient,
        *,
        max_ttl_seconds: int,
        provider_proven: bool = False,
    ) -> None:
        if max_ttl_seconds < 1:
            raise ValueError("max_ttl_seconds must be positive")
        self.client = client
        self.max_ttl_seconds = max_ttl_seconds
        self.provider_proven = provider_proven
        self.backend_status: BackendStatus = "ready" if provider_proven else "unproven"

    @staticmethod
    def _key(*, key_id: str, nonce_sha256: str) -> str:
        if not key_id or key_id != key_id.strip() or "\x00" in key_id:
            raise NonceStoreUnavailable("Shared nonce input is invalid")
        if NONCE_DIGEST.fullmatch(nonce_sha256) is None:
            raise NonceStoreUnavailable("Shared nonce input is invalid")
        material = REDIS_DOMAIN + key_id.encode("utf-8") + b"\0" + bytes.fromhex(nonce_sha256)
        return REDIS_KEY_PREFIX + hashlib.sha256(material).hexdigest()

    def consume_once(
        self, *, key_id: str, nonce_sha256: str, expires_at: int, now: int
    ) -> bool:
        ttl = expires_at - now + 1
        if ttl < 1 or ttl > self.max_ttl_seconds:
            raise NonceStoreUnavailable("Shared nonce lifetime is invalid")
        redis_key = self._key(key_id=key_id, nonce_sha256=nonce_sha256)
        try:
            result = self.client.set(redis_key, b"1", nx=True, ex=ttl)
        except Exception:
            self.provider_proven = False
            self.backend_status = "unavailable"
            raise NonceStoreUnavailable("Shared nonce backend unavailable") from None
        if result is True:
            return True
        if result is None:
            return False
        self.provider_proven = False
        self.backend_status = "unavailable"
        raise NonceStoreUnavailable("Shared nonce backend returned an uncertain result")

    def prove_backend(self, *, now: int) -> None:
        """Run a two-write atomic canary without exposing or retaining its key."""
        canary = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
        first = self.consume_once(key_id="modisa-readiness-canary", nonce_sha256=canary, expires_at=now + 4, now=now)
        second = self.consume_once(key_id="modisa-readiness-canary", nonce_sha256=canary, expires_at=now + 4, now=now)
        if first is not True or second is not False:
            self.backend_status = "unavailable"
            self.provider_proven = False
            raise NonceStoreUnavailable("Shared nonce backend atomic canary failed")
        self.backend_status = "ready"
        self.provider_proven = True


def build_redis_nonce_store(settings: Settings, *, now: int) -> RedisNonceStore:
    """Build and live-prove the configured Redis backend; never fall back."""
    secret_url = settings.webhook_nonce_redis_url
    if secret_url is None:
        raise NonceStoreUnavailable("Shared nonce backend is not configured")
    value = secret_url.get_secret_value()
    if not value or value != value.strip() or any(ch in value for ch in "\r\n\x00"):
        raise NonceStoreUnavailable("Shared nonce backend configuration is invalid")
    try:
        parsed = urlsplit(value)
        port = parsed.port
        decoded_components = [
            unquote(component)
            for component in (parsed.username, parsed.password, parsed.hostname)
            if component is not None
        ]
    except (TypeError, ValueError, UnicodeError):
        raise NonceStoreUnavailable("Shared nonce backend configuration is invalid") from None
    if any(
        any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in component)
        for component in decoded_components
    ):
        raise NonceStoreUnavailable("Shared nonce backend configuration is invalid")
    if (
        parsed.scheme != "rediss"
        or not parsed.hostname
        or not parsed.username
        or not parsed.password
        or port is None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/0")
    ):
        raise NonceStoreUnavailable("Shared nonce backend configuration is invalid")
    try:
        redis_module = importlib.import_module("redis")
        backoff_module = importlib.import_module("redis.backoff")
        retry_module = importlib.import_module("redis.retry")
    except ModuleNotFoundError:
        raise NonceStoreUnavailable("Shared nonce adapter dependency is unavailable") from None
    retry = retry_module.Retry(backoff_module.NoBackoff(), 0)
    try:
        client = redis_module.Redis.from_url(
            value,
            decode_responses=False,
            retry=retry,
            retry_on_timeout=False,
            socket_timeout=settings.webhook_nonce_timeout_seconds,
            socket_connect_timeout=settings.webhook_nonce_timeout_seconds,
            max_connections=settings.webhook_nonce_max_connections,
            socket_keepalive=True,
            ssl_cert_reqs="required",
            ssl_check_hostname=True,
            ssl_min_version=ssl.TLSVersion.TLSv1_2,
        )
    except Exception:
        raise NonceStoreUnavailable("Shared nonce client could not be created") from None
    store = RedisNonceStore(
        client,
        max_ttl_seconds=(2 * settings.webhook_max_clock_skew_seconds) + 1,
    )
    store.prove_backend(now=now)
    return store
