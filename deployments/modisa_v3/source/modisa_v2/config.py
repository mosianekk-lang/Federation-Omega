from __future__ import annotations

import base64
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY", repr=False)
    primary_model: str = Field(default="gpt-5.6-sol", alias="MODISA_PRIMARY_MODEL")
    prep_model: str = Field(default="gpt-5.6-terra", alias="MODISA_PREP_MODEL")
    volume_model: str = Field(default="gpt-5.6-luna", alias="MODISA_VOLUME_MODEL")
    max_agent_turns: int = Field(default=32, ge=4, le=128, alias="MODISA_MAX_AGENT_TURNS")

    database_path: Path = Field(default=Path("./state/modisa_v2.sqlite3"), alias="MODISA_DATABASE_PATH")
    session_db: Path = Field(default=Path("./state/agent_sessions.sqlite3"), alias="MODISA_SESSION_DB")
    session_backend: str = Field(default="sqlite", alias="MODISA_SESSION_BACKEND")
    session_database_url: SecretStr | None = Field(
        default=None, alias="MODISA_SESSION_DATABASE_URL", repr=False
    )
    evidence_root: Path = Field(default=Path("./evidence_vault"), alias="MODISA_EVIDENCE_ROOT")
    data_root: Path = Field(default=Path("./data"), alias="MODISA_DATA_ROOT")

    ledger_hmac_key_b64: SecretStr | None = Field(
        default=None, alias="MODISA_LEDGER_HMAC_KEY_B64", repr=False
    )
    evidence_aes_key_b64: SecretStr | None = Field(
        default=None, alias="MODISA_EVIDENCE_AES_KEY_B64", repr=False
    )
    jwt_secret: SecretStr | None = Field(default=None, alias="MODISA_JWT_SECRET", repr=False)
    webhook_auth_secret_ref: str | None = Field(
        default=None, alias="MODISA_WEBHOOK_AUTH_SECRET_REF"
    )
    webhook_auth_key_id: str = Field(default="modisa-webhook-v1", alias="MODISA_WEBHOOK_AUTH_KEY_ID")
    webhook_nonce_db: Path = Field(
        default=Path("./state/webhook_nonces.sqlite3"), alias="MODISA_WEBHOOK_NONCE_DB"
    )
    webhook_nonce_store: Literal["sqlite", "redis"] = Field(
        default="sqlite", alias="MODISA_WEBHOOK_NONCE_STORE"
    )
    webhook_nonce_redis_url: SecretStr | None = Field(
        default=None, alias="MODISA_WEBHOOK_NONCE_REDIS_URL"
    )
    webhook_nonce_timeout_seconds: float = Field(
        default=1.0, ge=0.1, le=5.0, alias="MODISA_WEBHOOK_NONCE_TIMEOUT_SECONDS"
    )
    webhook_nonce_max_connections: int = Field(
        default=32, ge=1, le=128, alias="MODISA_WEBHOOK_NONCE_MAX_CONNECTIONS"
    )
    webhook_max_clock_skew_seconds: int = Field(
        default=300, ge=30, le=3600, alias="MODISA_WEBHOOK_MAX_CLOCK_SKEW_SECONDS"
    )
    webhook_max_body_bytes: int = Field(
        default=1_048_576, ge=1024, le=16_777_216, alias="MODISA_WEBHOOK_MAX_BODY_BYTES"
    )
    webhook_secret_timeout_seconds: float = Field(
        default=5.0, ge=0.1, le=30.0, alias="MODISA_WEBHOOK_SECRET_TIMEOUT_SECONDS"
    )

    auth_disabled_dev: bool = Field(default=False, alias="MODISA_AUTH_DISABLED_DEV")
    allow_unencrypted_dev: bool = Field(default=False, alias="MODISA_ALLOW_UNENCRYPTED_DEV")
    external_actions_enabled: bool = Field(default=False, alias="MODISA_EXTERNAL_ACTIONS_ENABLED")
    log_level: str = Field(default="INFO", alias="MODISA_LOG_LEVEL")

    max_file_bytes: int = 250 * 1024 * 1024
    max_mime_parts: int = 20_000
    max_mime_depth: int = 32
    max_decoded_bytes: int = 2 * 1024 * 1024 * 1024
    max_zip_entries: int = 20_000
    max_zip_expanded_bytes: int = 4 * 1024 * 1024 * 1024
    max_zip_ratio: float = 200.0

    @property
    def api_key_present(self) -> bool:
        return bool(
            self.openai_api_key and self.openai_api_key.get_secret_value().strip()
        )

    @staticmethod
    def _decode_key(
        value: SecretStr | None, expected_bytes: int, label: str
    ) -> bytes | None:
        if not value:
            return None
        raw_value = value.get_secret_value()
        try:
            padded = raw_value + "=" * (-len(raw_value) % 4)
            decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        except Exception as exc:
            raise ValueError(f"{label} must be URL-safe base64") from exc
        if len(decoded) != expected_bytes:
            raise ValueError(f"{label} must decode to exactly {expected_bytes} bytes")
        return decoded

    @property
    def ledger_hmac_key(self) -> bytes | None:
        return self._decode_key(self.ledger_hmac_key_b64, 32, "MODISA_LEDGER_HMAC_KEY_B64")

    @property
    def evidence_aes_key(self) -> bytes | None:
        return self._decode_key(self.evidence_aes_key_b64, 32, "MODISA_EVIDENCE_AES_KEY_B64")

    @property
    def production_security_ready(self) -> bool:
        return all((self.ledger_hmac_key, self.evidence_aes_key, self.jwt_secret)) and not self.auth_disabled_dev

    @property
    def webhook_auth_configured(self) -> bool:
        return bool(self.webhook_auth_secret_ref and self.webhook_auth_secret_ref.strip())

    @property
    def authorised_read_roots(self) -> tuple[Path, ...]:
        roots = (self.data_root.resolve(), self.evidence_root.resolve(), Path.cwd().resolve())
        return tuple(dict.fromkeys(roots))

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_db.parent.mkdir(parents=True, exist_ok=True)
        self.webhook_nonce_db.parent.mkdir(parents=True, exist_ok=True)
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        self.data_root.mkdir(parents=True, exist_ok=True)

    def runtime_security_errors(self) -> list[str]:
        errors: list[str] = []
        if self.ledger_hmac_key is None:
            errors.append("proof-ledger HMAC key missing")
        if self.evidence_aes_key is None and not self.allow_unencrypted_dev:
            errors.append("evidence encryption key missing")
        if not self.jwt_secret and not self.auth_disabled_dev:
            errors.append("JWT secret missing")
        return errors


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings


def install_openai_key(settings: Settings) -> None:
    if settings.openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key.get_secret_value())
