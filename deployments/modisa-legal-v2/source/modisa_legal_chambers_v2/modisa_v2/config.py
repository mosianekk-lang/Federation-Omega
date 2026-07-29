from __future__ import annotations

import base64
import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    primary_model: str = Field(default="gpt-5.6-sol", alias="MODISA_PRIMARY_MODEL")
    prep_model: str = Field(default="gpt-5.6-terra", alias="MODISA_PREP_MODEL")
    volume_model: str = Field(default="gpt-5.6-luna", alias="MODISA_VOLUME_MODEL")
    max_agent_turns: int = Field(default=32, ge=4, le=128, alias="MODISA_MAX_AGENT_TURNS")

    database_path: Path = Field(default=Path("./state/modisa_v2.sqlite3"), alias="MODISA_DATABASE_PATH")
    session_db: Path = Field(default=Path("./state/agent_sessions.sqlite3"), alias="MODISA_SESSION_DB")
    session_backend: str = Field(default="sqlite", alias="MODISA_SESSION_BACKEND")
    session_database_url: str | None = Field(default=None, alias="MODISA_SESSION_DATABASE_URL")
    evidence_root: Path = Field(default=Path("./evidence_vault"), alias="MODISA_EVIDENCE_ROOT")
    data_root: Path = Field(default=Path("./data"), alias="MODISA_DATA_ROOT")

    ledger_hmac_key_b64: str | None = Field(default=None, alias="MODISA_LEDGER_HMAC_KEY_B64")
    evidence_aes_key_b64: str | None = Field(default=None, alias="MODISA_EVIDENCE_AES_KEY_B64")
    jwt_secret: str | None = Field(default=None, alias="MODISA_JWT_SECRET")

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
        return bool(self.openai_api_key and self.openai_api_key.strip())

    @staticmethod
    def _decode_key(value: str | None, expected_bytes: int, label: str) -> bytes | None:
        if not value:
            return None
        try:
            padded = value + "=" * (-len(value) % 4)
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
    def authorised_read_roots(self) -> tuple[Path, ...]:
        roots = (self.data_root.resolve(), self.evidence_root.resolve(), Path.cwd().resolve())
        return tuple(dict.fromkeys(roots))

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_db.parent.mkdir(parents=True, exist_ok=True)
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
        os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
