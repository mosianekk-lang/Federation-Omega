from __future__ import annotations

import base64
from pathlib import Path

import pytest

from modisa_v2.config import Settings
from modisa_v2.services import Services, build_services


def b64_key(byte: int) -> str:
    return base64.urlsafe_b64encode(bytes([byte]) * 32).decode("ascii").rstrip("=")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        OPENAI_API_KEY=None,
        MODISA_LEDGER_HMAC_KEY_B64=b64_key(7),
        MODISA_EVIDENCE_AES_KEY_B64=b64_key(9),
        MODISA_JWT_SECRET="test-jwt-secret-not-for-production",
        MODISA_AUTH_DISABLED_DEV=True,
        MODISA_DATABASE_PATH=tmp_path / "state" / "modisa.sqlite3",
        MODISA_SESSION_DB=tmp_path / "state" / "sessions.sqlite3",
        MODISA_EVIDENCE_ROOT=tmp_path / "vault",
        MODISA_DATA_ROOT=tmp_path / "data",
    )


@pytest.fixture
def services(settings: Settings) -> Services:
    return build_services(settings)
