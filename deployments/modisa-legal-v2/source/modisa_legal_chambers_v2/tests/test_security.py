import jwt
import pytest
from fastapi import HTTPException

from modisa_v2.config import Settings
from modisa_v2.security import AccessRequirement, AuthService, contains_secret, redact_secrets


def test_secret_detection_and_redaction():
    text = "OPENAI_API_KEY=" + "sk-" + "proj-" + "abcdefghijklmnopqrstuvwxyz123456"
    assert contains_secret(text)
    assert "sk-proj" not in redact_secrets(text)


def test_jwt_and_matter_scope(tmp_path):
    settings = Settings(
        MODISA_JWT_SECRET="test-secret-key-with-at-least-thirty-two-bytes",
        MODISA_AUTH_DISABLED_DEV=False,
        MODISA_ALLOW_UNENCRYPTED_DEV=True,
        MODISA_DATABASE_PATH=tmp_path / "db.sqlite3",
        MODISA_SESSION_DB=tmp_path / "session.sqlite3",
        MODISA_EVIDENCE_ROOT=tmp_path / "vault",
        MODISA_DATA_ROOT=tmp_path / "data",
    )
    service = AuthService(settings)
    token = jwt.encode(
        {"sub": "kim", "roles": ["OWNER"], "matter_ids": ["MAT-1"], "scopes": ["release:evaluate"]},
        "test-secret-key-with-at-least-thirty-two-bytes",
        algorithm="HS256",
    )
    principal = service.decode(token)
    service.enforce(principal, AccessRequirement(roles=frozenset({"OWNER"}), scopes=frozenset({"release:evaluate"})), "MAT-1")
    with pytest.raises(HTTPException):
        service.enforce(principal, AccessRequirement(roles=frozenset({"OWNER"})), "MAT-2")
