from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


VERIFIED_STATES = frozenset(
    {
        "VERIFIED",
        "CONTROL_PLANE_VERIFIED",
        "OPERATIONAL_VERIFIED_SCOPED",
        "INFERENCE_VERIFIED_SCOPED",
        "PROVIDER_READBACK_VERIFIED",
    }
)


class AttestationError(RuntimeError):
    pass


class NoFreshProviderRoute(AttestationError):
    pass


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _reject_secret_payload(value: Any, path: str = "details") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            suspicious = any(token in normalized for token in ("password", "private_key", "access_token", "refresh_token", "secret_value", "api_key_value"))
            if suspicious and not normalized.endswith(("_reference", "_ref", "_present")):
                raise AttestationError(f"raw secret-bearing attestation field forbidden: {path}.{key}")
            _reject_secret_payload(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_secret_payload(child, f"{path}[{index}]")


@dataclass(frozen=True)
class ProviderAttestation:
    attestation_id: str
    provider: str
    surface: str
    subject: str
    state: str
    capabilities: tuple[str, ...]
    observed_at_epoch: int
    expires_at_epoch: int
    evidence_refs: tuple[str, ...]
    source_revision: str
    details: Mapping[str, Any] = field(default_factory=dict)
    attestation_sha256: str = ""

    @classmethod
    def build(
        cls,
        *,
        attestation_id: str,
        provider: str,
        surface: str,
        subject: str,
        state: str,
        capabilities: Sequence[str],
        observed_at_epoch: int,
        expires_at_epoch: int,
        evidence_refs: Sequence[str],
        source_revision: str,
        details: Mapping[str, Any] | None = None,
    ) -> "ProviderAttestation":
        detail_map = dict(details or {})
        _reject_secret_payload(detail_map)
        if not all(item.strip() for item in (attestation_id, provider, surface, subject, state, source_revision)):
            raise AttestationError("provider attestation identity fields are required")
        if expires_at_epoch <= observed_at_epoch:
            raise AttestationError("provider attestation expiry must be after observation")
        evidence = tuple(str(item).strip() for item in evidence_refs if str(item).strip())
        if not evidence:
            raise AttestationError("provider attestation requires non-empty evidence references")
        caps = tuple(sorted({str(item).strip().upper() for item in capabilities if str(item).strip()}))
        if not caps:
            raise AttestationError("provider attestation requires at least one capability")
        body = {
            "attestation_id": attestation_id,
            "provider": provider.upper(),
            "surface": surface.upper(),
            "subject": subject,
            "state": state.upper(),
            "capabilities": caps,
            "observed_at_epoch": int(observed_at_epoch),
            "expires_at_epoch": int(expires_at_epoch),
            "evidence_refs": evidence,
            "source_revision": source_revision,
            "details": detail_map,
        }
        return cls(**body, attestation_sha256=_digest(body))

    def is_fresh(self, now_epoch: int) -> bool:
        return self.observed_at_epoch <= now_epoch < self.expires_at_epoch

    def is_verified_for(self, capability: str, now_epoch: int) -> bool:
        return (
            self.state in VERIFIED_STATES
            and capability.strip().upper() in self.capabilities
            and self.is_fresh(now_epoch)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "attestation_id": self.attestation_id,
            "provider": self.provider,
            "surface": self.surface,
            "subject": self.subject,
            "state": self.state,
            "capabilities": list(self.capabilities),
            "observed_at_epoch": self.observed_at_epoch,
            "expires_at_epoch": self.expires_at_epoch,
            "evidence_refs": list(self.evidence_refs),
            "source_revision": self.source_revision,
            "details": dict(self.details),
            "attestation_sha256": self.attestation_sha256,
        }


class ProviderAttestationStore:
    """Provider truth table designed to share the SLOS durable connection."""

    def __init__(self, connection: sqlite3.Connection):
        self.db = connection
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS provider_attestations(
              attestation_id TEXT PRIMARY KEY,
              provider TEXT NOT NULL,
              surface TEXT NOT NULL,
              subject TEXT NOT NULL,
              state TEXT NOT NULL,
              capabilities_json TEXT NOT NULL,
              observed_at_epoch INTEGER NOT NULL,
              expires_at_epoch INTEGER NOT NULL,
              evidence_refs_json TEXT NOT NULL,
              source_revision TEXT NOT NULL,
              details_json TEXT NOT NULL,
              attestation_sha256 TEXT NOT NULL
            )
            """
        )
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_provider_attestation_route ON provider_attestations(provider,surface,subject,expires_at_epoch)"
        )
        self.db.commit()

    def put(self, attestation: ProviderAttestation) -> ProviderAttestation:
        row = self.db.execute(
            "SELECT attestation_sha256 FROM provider_attestations WHERE attestation_id=?",
            (attestation.attestation_id,),
        ).fetchone()
        if row:
            prior_hash = row[0]
            if prior_hash != attestation.attestation_sha256:
                raise AttestationError("ATTESTATION_ID_REUSED_WITH_DIFFERENT_CONTENT")
            return attestation
        with self.db:
            self.db.execute(
                "INSERT INTO provider_attestations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    attestation.attestation_id,
                    attestation.provider,
                    attestation.surface,
                    attestation.subject,
                    attestation.state,
                    _stable_json(attestation.capabilities),
                    attestation.observed_at_epoch,
                    attestation.expires_at_epoch,
                    _stable_json(attestation.evidence_refs),
                    attestation.source_revision,
                    _stable_json(dict(attestation.details)),
                    attestation.attestation_sha256,
                ),
            )
        return attestation

    @staticmethod
    def _from_row(row: sqlite3.Row | tuple[Any, ...]) -> ProviderAttestation:
        values = tuple(row)
        return ProviderAttestation(
            attestation_id=values[0],
            provider=values[1],
            surface=values[2],
            subject=values[3],
            state=values[4],
            capabilities=tuple(json.loads(values[5])),
            observed_at_epoch=int(values[6]),
            expires_at_epoch=int(values[7]),
            evidence_refs=tuple(json.loads(values[8])),
            source_revision=values[9],
            details=json.loads(values[10]),
            attestation_sha256=values[11],
        )

    def resolve(
        self,
        *,
        provider: str,
        surface: str,
        capability: str,
        now_epoch: int,
        subject: str | None = None,
    ) -> ProviderAttestation | None:
        sql = (
            "SELECT attestation_id,provider,surface,subject,state,capabilities_json,observed_at_epoch,"
            "expires_at_epoch,evidence_refs_json,source_revision,details_json,attestation_sha256 "
            "FROM provider_attestations WHERE provider=? AND surface=? AND expires_at_epoch>?"
        )
        params: list[Any] = [provider.upper(), surface.upper(), int(now_epoch)]
        if subject is not None:
            sql += " AND subject=?"
            params.append(subject)
        sql += " ORDER BY observed_at_epoch DESC"
        for row in self.db.execute(sql, tuple(params)):
            attestation = self._from_row(row)
            if attestation.is_verified_for(capability, now_epoch):
                return attestation
        return None

    def expire_before(self, now_epoch: int) -> int:
        with self.db:
            cursor = self.db.execute(
                "DELETE FROM provider_attestations WHERE expires_at_epoch<=?", (int(now_epoch),)
            )
        return int(cursor.rowcount)


@dataclass(frozen=True)
class ProviderRoutePolicy:
    operation: str
    provider: str
    surface: str
    capability: str
    subject: str | None = None
    priority: int = 100


@dataclass(frozen=True)
class ProviderRouteDecision:
    operation: str
    provider: str
    surface: str
    subject: str
    capability: str
    attestation_id: str
    evidence_refs: tuple[str, ...]
    expires_at_epoch: int


class DynamicProviderRouter:
    """Route from current expiring provider evidence, never static truth snapshots."""

    def __init__(self, store: ProviderAttestationStore, policies: Sequence[ProviderRoutePolicy]):
        self.store = store
        self.policies = tuple(sorted(policies, key=lambda item: (item.operation, item.priority)))

    def route(self, operation: str, *, now_epoch: int) -> ProviderRouteDecision:
        candidates = [item for item in self.policies if item.operation == operation]
        if not candidates:
            raise NoFreshProviderRoute(f"no provider policy registered for operation {operation}")
        failures: list[str] = []
        for policy in candidates:
            attestation = self.store.resolve(
                provider=policy.provider,
                surface=policy.surface,
                capability=policy.capability,
                now_epoch=now_epoch,
                subject=policy.subject,
            )
            if attestation is None:
                failures.append(f"{policy.provider}/{policy.surface}:{policy.capability}")
                continue
            return ProviderRouteDecision(
                operation=operation,
                provider=attestation.provider,
                surface=attestation.surface,
                subject=attestation.subject,
                capability=policy.capability,
                attestation_id=attestation.attestation_id,
                evidence_refs=attestation.evidence_refs,
                expires_at_epoch=attestation.expires_at_epoch,
            )
        raise NoFreshProviderRoute(
            f"no fresh verified provider attestation for {operation}; checked=" + ",".join(failures)
        )


__all__ = [
    "AttestationError",
    "DynamicProviderRouter",
    "NoFreshProviderRoute",
    "ProviderAttestation",
    "ProviderAttestationStore",
    "ProviderRouteDecision",
    "ProviderRoutePolicy",
    "VERIFIED_STATES",
]
