from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from .errors import InvalidRequest

_SAFE_ID = re.compile(r"^[A-Za-z0-9._:/@-]{1,256}$")
_RESOURCE = re.compile(r"^[A-Za-z0-9._:/@-]{3,512}$")
_OPERATION_ID = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def _validate(pattern: re.Pattern[str], value: str, field: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise InvalidRequest(f"{field} is invalid")
    return value


class AuthorityClass(str, Enum):
    A0 = "A0"
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"


class ActionClass(str, Enum):
    READ = "READ"
    VERIFY = "VERIFY"
    WRITE = "WRITE"
    DEPLOY = "DEPLOY"
    ADMIN = "ADMIN"


@dataclass(frozen=True)
class SecretReference:
    provider: str
    resource: str
    version: str

    def __post_init__(self) -> None:
        _validate(_SAFE_ID, self.provider, "provider")
        _validate(_RESOURCE, self.resource, "resource")
        _validate(_SAFE_ID, self.version, "version")
        if self.version.lower() == "latest":
            raise InvalidRequest("an exact secret version is required")

    @property
    def reference_id(self) -> str:
        return f"{self.provider}:{self.resource}:{self.version}"


@dataclass(frozen=True)
class WorkloadIdentity:
    subject: str
    audience: str
    authority: AuthorityClass

    def __post_init__(self) -> None:
        _validate(_SAFE_ID, self.subject, "subject")
        _validate(_SAFE_ID, self.audience, "audience")


@dataclass(frozen=True)
class CapabilityRequest:
    mission_id: str
    mission_version: int
    operation_id: str
    identity: WorkloadIdentity
    secret: SecretReference
    connector: str
    action: str
    ttl_seconds: int = 300

    def __post_init__(self) -> None:
        _validate(_SAFE_ID, self.mission_id, "mission_id")
        _validate(_OPERATION_ID, self.operation_id, "operation_id")
        _validate(_SAFE_ID, self.connector, "connector")
        _validate(_SAFE_ID, self.action, "action")
        if not isinstance(self.mission_version, int) or self.mission_version < 1:
            raise InvalidRequest("mission_version must be a positive integer")
        if not isinstance(self.ttl_seconds, int) or not 1 <= self.ttl_seconds <= 900:
            raise InvalidRequest("ttl_seconds must be between 1 and 900")

    def policy_facts(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "mission_version": self.mission_version,
            "subject": self.identity.subject,
            "audience": self.identity.audience,
            "authority": self.identity.authority.value,
            "resource": self.secret.reference_id,
            "connector": self.connector,
            "action": self.action,
        }


@dataclass(frozen=True)
class CapabilityClaims:
    token_id: str
    mission_id: str
    mission_version: int
    operation_id: str
    subject: str
    audience: str
    authority: str
    resource: str
    connector: str
    action: str
    issued_at: int
    expires_at: int
    nonce: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionReceipt:
    operation_id: str
    token_id: str
    mission_id: str
    connector: str
    action: str
    state: str
    result_digest: str
    audit_sequence: int
    replayed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
