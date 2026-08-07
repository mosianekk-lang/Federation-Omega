from __future__ import annotations

from dataclasses import dataclass
import uuid

from .models import InformationClass, utc_now_iso
from .store import SqliteStateStore


@dataclass(frozen=True)
class RestrictedEntry:
    tenant_id: str
    reason: str
    issuer_id: str | None = None
    security_id: str | None = None
    information_class: InformationClass = InformationClass.RESTRICTED
    start_at: str = ""
    review_at: str | None = None
    restriction_id: str = ""

    def normalized(self) -> "RestrictedEntry":
        if not self.issuer_id and not self.security_id:
            raise ValueError("issuer_id or security_id is required")
        return RestrictedEntry(
            tenant_id=self.tenant_id, reason=self.reason, issuer_id=self.issuer_id,
            security_id=self.security_id, information_class=self.information_class,
            start_at=self.start_at or utc_now_iso(), review_at=self.review_at,
            restriction_id=self.restriction_id or str(uuid.uuid4()),
        )


class RestrictedListRegistry:
    def __init__(self, store: SqliteStateStore) -> None:
        self.store = store

    def add(self, entry: RestrictedEntry) -> RestrictedEntry:
        entry = entry.normalized()
        self.store._connection.execute(
            "INSERT INTO restrictions(tenant_id,restriction_id,issuer_id,security_id,reason,information_class,start_at,review_at,cleared_at) VALUES (?,?,?,?,?,?,?,?,NULL)",
            (entry.tenant_id, entry.restriction_id, entry.issuer_id, entry.security_id, entry.reason, entry.information_class.value, entry.start_at, entry.review_at),
        )
        return entry

    def clear(self, tenant_id: str, restriction_id: str) -> None:
        self.store._connection.execute(
            "UPDATE restrictions SET cleared_at=? WHERE tenant_id=? AND restriction_id=? AND cleared_at IS NULL",
            (utc_now_iso(), tenant_id, restriction_id),
        )

    def is_restricted(self, tenant_id: str, issuer_id: str | None = None, security_id: str | None = None) -> bool:
        if not issuer_id and not security_id:
            return False
        conditions = ["tenant_id=?", "cleared_at IS NULL"]
        params: list[object] = [tenant_id]
        lookup = []
        if issuer_id:
            lookup.append("issuer_id=?"); params.append(issuer_id)
        if security_id:
            lookup.append("security_id=?"); params.append(security_id)
        conditions.append("(" + " OR ".join(lookup) + ")")
        row = self.store._connection.execute("SELECT 1 FROM restrictions WHERE " + " AND ".join(conditions) + " LIMIT 1", params).fetchone()
        return row is not None
