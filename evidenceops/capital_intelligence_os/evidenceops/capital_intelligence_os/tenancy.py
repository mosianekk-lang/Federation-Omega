from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .models import Domain


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    user_id: str
    roles: tuple[str, ...] = field(default_factory=tuple)
    allowed_domains: tuple[Domain, ...] = field(default_factory=lambda: tuple(Domain))

    def validate(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not self.user_id.strip():
            raise ValueError("user_id is required")
        if len(set(self.roles)) != len(self.roles):
            raise ValueError("roles must not contain duplicates")

    def allows(self, domain: Domain) -> bool:
        return domain in self.allowed_domains


class TenantBoundaryGuard:
    """Central tenant-boundary guard used before any cross-object operation."""

    @staticmethod
    def assert_tenant(ctx: TenantContext, record_tenant_id: str) -> None:
        ctx.validate()
        if ctx.tenant_id != record_tenant_id:
            raise PermissionError("TENANT_BOUNDARY_VIOLATION")

    @staticmethod
    def assert_domain(ctx: TenantContext, domain: Domain) -> None:
        ctx.validate()
        if not ctx.allows(domain):
            raise PermissionError("DOMAIN_NOT_AUTHORISED_FOR_TENANT_CONTEXT")

    @staticmethod
    def scope_ids(ctx: TenantContext, tenant_ids: Iterable[str]) -> None:
        for tenant_id in tenant_ids:
            TenantBoundaryGuard.assert_tenant(ctx, tenant_id)
