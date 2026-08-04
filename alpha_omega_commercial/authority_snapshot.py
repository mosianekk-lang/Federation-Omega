from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable


LIVE_AUTHORITY_CLASS = "LIVE_PROVIDER_NATIVE"
OPERATIONAL_STATES = {"FRESH_VERIFIED", "FRESH_VERIFIED_READBACK"}
MAX_SNAPSHOT_LIFETIME_SECONDS = 7 * 86400


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def valid_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except (TypeError, ValueError):
        return False
    return True


@dataclass(frozen=True)
class AuthorityDomainLease:
    domain: str
    state: str
    authority_class: str
    provider: str
    locator: str
    observed_at: str
    scope: tuple[str, ...]
    evidence_sha256: str
    max_age_seconds: int
    domain_sha256: str = ""

    def unsigned_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("domain_sha256", None)
        payload["scope"] = sorted(payload["scope"])
        return payload

    def expected_sha256(self) -> str:
        return digest(self.unsigned_payload())

    def with_hash(self) -> "AuthorityDomainLease":
        payload = self.unsigned_payload()
        payload["scope"] = tuple(payload["scope"])
        return AuthorityDomainLease(**payload, domain_sha256=digest(self.unsigned_payload()))


@dataclass(frozen=True)
class CommercialAuthoritySnapshot:
    snapshot_id: str
    generated_at: str
    expires_at: str
    source_projection_sha256: str
    source_ledger_head: str
    source_ledger_integrity: bool
    domains: dict[str, AuthorityDomainLease] = field(default_factory=dict)
    snapshot_sha256: str = ""

    def unsigned_payload(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "generated_at": self.generated_at,
            "expires_at": self.expires_at,
            "source_projection_sha256": self.source_projection_sha256,
            "source_ledger_head": self.source_ledger_head,
            "source_ledger_integrity": self.source_ledger_integrity,
            "domains": {
                domain: asdict(lease)
                for domain, lease in sorted(self.domains.items())
            },
        }

    def expected_sha256(self) -> str:
        return digest(self.unsigned_payload())

    def with_hash(self) -> "CommercialAuthoritySnapshot":
        return CommercialAuthoritySnapshot(
            snapshot_id=self.snapshot_id,
            generated_at=self.generated_at,
            expires_at=self.expires_at,
            source_projection_sha256=self.source_projection_sha256,
            source_ledger_head=self.source_ledger_head,
            source_ledger_integrity=self.source_ledger_integrity,
            domains=self.domains,
            snapshot_sha256=self.expected_sha256(),
        )

    def to_dict(self) -> dict[str, Any]:
        value = self.unsigned_payload()
        value["snapshot_sha256"] = self.snapshot_sha256
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CommercialAuthoritySnapshot":
        domains = {
            domain: AuthorityDomainLease(
                domain=item["domain"],
                state=item["state"],
                authority_class=item["authority_class"],
                provider=item["provider"],
                locator=item["locator"],
                observed_at=item["observed_at"],
                scope=tuple(item.get("scope", [])),
                evidence_sha256=item["evidence_sha256"],
                max_age_seconds=int(item["max_age_seconds"]),
                domain_sha256=item.get("domain_sha256", ""),
            )
            for domain, item in value.get("domains", {}).items()
        }
        return cls(
            snapshot_id=value["snapshot_id"],
            generated_at=value["generated_at"],
            expires_at=value["expires_at"],
            source_projection_sha256=value["source_projection_sha256"],
            source_ledger_head=value["source_ledger_head"],
            source_ledger_integrity=bool(value["source_ledger_integrity"]),
            domains=domains,
            snapshot_sha256=value.get("snapshot_sha256", ""),
        )


@dataclass(frozen=True)
class AuthoritySnapshotDecision:
    valid: bool
    domain: str
    reasons: tuple[str, ...]
    snapshot_id: str | None
    snapshot_sha256: str | None
    evidence_sha256: str | None


class CommercialAuthoritySnapshotValidator:
    """Validate evidence-bound live-authority snapshots for consequential actions.

    Raw caller-supplied authority state is never sufficient. A live authority domain
    must be bound to a hash-valid snapshot, an intact source ledger, explicit scope,
    provider evidence and a non-expired observation.
    """

    def __init__(self, snapshot: CommercialAuthoritySnapshot | dict[str, Any] | None) -> None:
        if isinstance(snapshot, dict):
            snapshot = CommercialAuthoritySnapshot.from_dict(snapshot)
        self.snapshot = snapshot

    def validate_domain(
        self,
        domain: str,
        *,
        required_scope: Iterable[str] = (),
        now: str,
    ) -> AuthoritySnapshotDecision:
        reasons: list[str] = []
        snapshot = self.snapshot
        if snapshot is None:
            return AuthoritySnapshotDecision(
                valid=False,
                domain=domain,
                reasons=("AUTHORITY_SNAPSHOT_REQUIRED",),
                snapshot_id=None,
                snapshot_sha256=None,
                evidence_sha256=None,
            )

        if not snapshot.snapshot_id.strip():
            reasons.append("SNAPSHOT_ID_MISSING")
        if snapshot.snapshot_sha256 != snapshot.expected_sha256():
            reasons.append("SNAPSHOT_HASH_INVALID")
        if not snapshot.source_ledger_integrity:
            reasons.append("SOURCE_LEDGER_INTEGRITY_FAILED")
        if not valid_sha256(snapshot.source_projection_sha256):
            reasons.append("SOURCE_PROJECTION_HASH_INVALID")
        if not snapshot.source_ledger_head.strip() or snapshot.source_ledger_head == "GENESIS":
            reasons.append("SOURCE_LEDGER_HEAD_MISSING")

        try:
            generated = parse_utc(snapshot.generated_at)
            expires = parse_utc(snapshot.expires_at)
            current = parse_utc(now)
            if expires <= generated:
                reasons.append("SNAPSHOT_EXPIRY_INVALID")
            if current < generated:
                reasons.append("SNAPSHOT_FROM_FUTURE")
            if current > expires:
                reasons.append("SNAPSHOT_EXPIRED")
            if (expires - generated).total_seconds() > MAX_SNAPSHOT_LIFETIME_SECONDS:
                reasons.append("SNAPSHOT_VALIDITY_TOO_LONG")
        except (TypeError, ValueError):
            generated = None
            current = None
            reasons.append("SNAPSHOT_TIMESTAMP_INVALID")

        lease = snapshot.domains.get(domain)
        if lease is None:
            reasons.append("AUTHORITY_DOMAIN_NOT_IN_SNAPSHOT")
            return AuthoritySnapshotDecision(
                valid=False,
                domain=domain,
                reasons=tuple(sorted(set(reasons))),
                snapshot_id=snapshot.snapshot_id,
                snapshot_sha256=snapshot.snapshot_sha256,
                evidence_sha256=None,
            )

        if lease.domain != domain:
            reasons.append("AUTHORITY_DOMAIN_MISMATCH")
        if lease.domain_sha256 != lease.expected_sha256():
            reasons.append("AUTHORITY_DOMAIN_HASH_INVALID")
        if lease.state not in OPERATIONAL_STATES:
            reasons.append("AUTHORITY_STATE_NOT_OPERATIONAL")
        if lease.authority_class != LIVE_AUTHORITY_CLASS:
            reasons.append("AUTHORITY_CLASS_NOT_LIVE_PROVIDER_NATIVE")
        if not lease.provider.strip() or not lease.locator.strip():
            reasons.append("AUTHORITY_PROVIDER_LOCATOR_MISSING")
        if not valid_sha256(lease.evidence_sha256):
            reasons.append("AUTHORITY_EVIDENCE_HASH_INVALID")
        if lease.max_age_seconds <= 0:
            reasons.append("AUTHORITY_MAX_AGE_INVALID")

        missing_scope = sorted(set(required_scope) - set(lease.scope))
        if missing_scope:
            reasons.append("AUTHORITY_SCOPE_MISSING:" + ",".join(missing_scope))

        try:
            observed = parse_utc(lease.observed_at)
            if generated is not None and observed > generated:
                reasons.append("AUTHORITY_OBSERVED_AFTER_SNAPSHOT")
            if current is not None:
                age = (current - observed).total_seconds()
                if age < 0:
                    reasons.append("AUTHORITY_OBSERVATION_FROM_FUTURE")
                if age > lease.max_age_seconds:
                    reasons.append("AUTHORITY_OBSERVATION_STALE")
        except (TypeError, ValueError):
            reasons.append("AUTHORITY_OBSERVATION_TIMESTAMP_INVALID")

        return AuthoritySnapshotDecision(
            valid=not reasons,
            domain=domain,
            reasons=tuple(sorted(set(reasons))),
            snapshot_id=snapshot.snapshot_id,
            snapshot_sha256=snapshot.snapshot_sha256,
            evidence_sha256=lease.evidence_sha256,
        )

    def authority_view(self, *, now: str) -> dict[str, dict[str, Any]]:
        snapshot = self.snapshot
        if snapshot is None:
            return {}
        result: dict[str, dict[str, Any]] = {}
        for domain, lease in snapshot.domains.items():
            decision = self.validate_domain(domain, now=now)
            result[domain] = {
                "state": lease.state if decision.valid else "STALE_REVALIDATION_REQUIRED",
                "authority_class": lease.authority_class if decision.valid else "UNVERIFIED",
                "provider": lease.provider,
                "locator": lease.locator,
                "observed_at": lease.observed_at,
                "scope": sorted(lease.scope),
                "evidence_sha256": lease.evidence_sha256,
                "snapshot_id": snapshot.snapshot_id,
                "snapshot_sha256": snapshot.snapshot_sha256,
                "snapshot_valid": decision.valid,
                "snapshot_reasons": list(decision.reasons),
            }
        return result


def build_authority_snapshot(
    *,
    snapshot_id: str,
    generated_at: str,
    expires_at: str,
    source_projection_sha256: str,
    source_ledger_head: str,
    source_ledger_integrity: bool,
    domains: Iterable[AuthorityDomainLease],
) -> CommercialAuthoritySnapshot:
    hashed_domains = {
        lease.domain: lease if lease.domain_sha256 else lease.with_hash()
        for lease in domains
    }
    return CommercialAuthoritySnapshot(
        snapshot_id=snapshot_id,
        generated_at=generated_at,
        expires_at=expires_at,
        source_projection_sha256=source_projection_sha256,
        source_ledger_head=source_ledger_head,
        source_ledger_integrity=source_ledger_integrity,
        domains=hashed_domains,
    ).with_hash()
