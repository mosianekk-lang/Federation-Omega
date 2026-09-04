from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import hmac
import json


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


@dataclass(frozen=True)
class ObjectiveContract:
    owner_id: str
    objective: str
    mandatory_requirements: tuple[str, ...]
    acceptance_tests: tuple[str, ...]
    prohibited_substitutions: tuple[str, ...] = ()
    invariants: tuple[str, ...] = ()
    version: int = 1
    supersedes: str | None = None
    signature: str = ""

    @property
    def unsigned_body(self) -> dict:
        body = asdict(self)
        body.pop("signature")
        return body

    @property
    def fingerprint(self) -> str:
        return sha256(_canonical(self.unsigned_body)).hexdigest()

    def validate(self) -> None:
        if not self.owner_id.strip() or not self.objective.strip():
            raise ValueError("owner and objective are required")
        if not self.mandatory_requirements or not self.acceptance_tests:
            raise ValueError("requirements and acceptance tests are required")
        if self.version < 1:
            raise ValueError("version must be positive")
        if len(set(self.mandatory_requirements)) != len(self.mandatory_requirements):
            raise ValueError("duplicate mandatory requirement")

    def sign(self, secret: bytes) -> "ObjectiveContract":
        from dataclasses import replace
        self.validate()
        return replace(self, signature=hmac.new(secret, _canonical(self.unsigned_body), sha256).hexdigest())

    def verify(self, secret: bytes) -> bool:
        expected = hmac.new(secret, _canonical(self.unsigned_body), sha256).hexdigest()
        return bool(self.signature) and hmac.compare_digest(self.signature, expected)


class ObjectiveViolation(RuntimeError):
    pass


class ObjectiveRegistry:
    """Monotonic objective registry. Only a valid owner-signed successor may replace the head."""
    def __init__(self, owner_secrets: dict[str, bytes]):
        self._secrets = owner_secrets
        self._heads: dict[str, ObjectiveContract] = {}

    def admit(self, contract: ObjectiveContract) -> ObjectiveContract:
        contract.validate()
        secret = self._secrets.get(contract.owner_id)
        if secret is None or not contract.verify(secret):
            raise ObjectiveViolation("invalid owner signature")
        current = self._heads.get(contract.owner_id)
        if current:
            if contract.version != current.version + 1:
                raise ObjectiveViolation("non-monotonic objective version")
            if contract.supersedes != current.fingerprint:
                raise ObjectiveViolation("successor does not bind prior objective")
        elif contract.version != 1 or contract.supersedes is not None:
            raise ObjectiveViolation("invalid genesis objective")
        self._heads[contract.owner_id] = contract
        return contract

    def head(self, owner_id: str) -> ObjectiveContract:
        return self._heads[owner_id]
