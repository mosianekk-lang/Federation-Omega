from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Callable
import re

from .authority import AuthorityGuard
from .models import (
    ActionDisposition, ActionRequest, AuthorityLevel, Domain, Event,
    InformationClass, stable_sha256,
)
from .store import SqliteStateStore

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

@dataclass(frozen=True)
class ProviderCanarySpec:
    expected_source_sha: str
    runtime_source_sha: str
    runtime_identity: str
    tenant_id: str
    db_path: str
    def validate(self) -> None:
        if not _SHA_RE.fullmatch(self.expected_source_sha) or not _SHA_RE.fullmatch(self.runtime_source_sha):
            raise ValueError("source SHAs must be lowercase 40-character Git commit SHAs")
        if self.expected_source_sha != self.runtime_source_sha:
            raise ValueError("runtime source SHA does not match expected source SHA")
        if not self.runtime_identity.strip() or not self.tenant_id.strip():
            raise ValueError("runtime_identity and tenant_id are required")
        if self.db_path.strip() in {"", ":memory:"}:
            raise ValueError("provider canary requires a persistent database path")

@dataclass(frozen=True)
class ProviderCanaryReceipt:
    source_sha: str
    runtime_identity: str
    tenant_id: str
    release: str
    release_checks_passed: bool
    database_quick_check: bool
    event_persisted_after_reopen: bool
    state_digest_stable_after_reopen: bool
    learning_chain_valid: bool
    live_order_denied: bool
    private_to_market_denied: bool
    external_effects_enabled: bool
    receipt_digest: str = ""
    def payload(self) -> dict[str, object]:
        data=asdict(self); data.pop("receipt_digest",None); return data
    @property
    def passed(self) -> bool:
        return all((self.release_checks_passed,self.database_quick_check,self.event_persisted_after_reopen,self.state_digest_stable_after_reopen,self.learning_chain_valid,self.live_order_denied,self.private_to_market_denied,not self.external_effects_enabled,bool(self.receipt_digest)))
    def validate_digest(self) -> bool:
        return stable_sha256(self.payload()) == self.receipt_digest

class ProviderCanary:
    """Harmless A1 runtime canary; it never provisions or promotes a provider."""
    def __init__(self, *, store_factory=SqliteStateStore, release_verify:Callable[[],dict[str,object]]|None=None, authority_factory=AuthorityGuard) -> None:
        if release_verify is None:
            from .verify_rc2 import verify as release_verify
        self.store_factory=store_factory; self.release_verify=release_verify; self.authority_factory=authority_factory
    def run(self,spec:ProviderCanarySpec)->ProviderCanaryReceipt:
        spec.validate(); path=Path(spec.db_path)
        if path.exists() and path.stat().st_size>0: raise FileExistsError("provider canary requires a fresh isolated database path")
        path.parent.mkdir(parents=True,exist_ok=True)
        release=self.release_verify(); release_passed=bool(release.get("passed")); release_name=str(release.get("release","UNKNOWN"))
        event=Event("PROVIDER_CANARY","CIOS_PROVIDER_CANARY","runtime",{"source_sha":spec.runtime_source_sha,"runtime_identity":spec.runtime_identity},Domain.GOVERNANCE,InformationClass.PUBLIC,0.1,event_id=f"provider-canary-{spec.runtime_source_sha[:12]}",occurred_at="2026-08-11T22:00:00+00:00")
        store=self.store_factory(spec.db_path)
        try:
            inserted=bool(store.append_event(spec.tenant_id,event)); store.append_learning(spec.tenant_id,"SUCCESS","PROVIDER_CANARY",{"source_sha":spec.runtime_source_sha,"runtime_identity":spec.runtime_identity}); quick=bool(store.quick_check()); before=store.tenant_state_digest(spec.tenant_id)
        finally: store.close()
        reopened=self.store_factory(spec.db_path)
        try:
            persisted=any(e.event_id==event.event_id for e in reopened.load_events(spec.tenant_id)); after=reopened.tenant_state_digest(spec.tenant_id); chain=bool(reopened.verify_learning_chain(spec.tenant_id)); quick=quick and bool(reopened.quick_check())
        finally: reopened.close()
        guard=self.authority_factory(); live=guard.evaluate(ActionRequest("LIVE_ORDER",Domain.PUBLIC_MARKETS,Domain.PUBLIC_MARKETS,InformationClass.PUBLIC,financial_effect=True,requested_authority=AuthorityLevel.A5_SOVEREIGN_AUTHORITY)); private_market=guard.evaluate(ActionRequest("RESEARCH_EXPORT",Domain.PRIVATE_MNA,Domain.PUBLIC_MARKETS,InformationClass.CONFIDENTIAL))
        receipt=ProviderCanaryReceipt(spec.runtime_source_sha,spec.runtime_identity,spec.tenant_id,release_name,release_passed,quick,inserted and persisted,before==after,chain,live.disposition==ActionDisposition.DENY,private_market.disposition==ActionDisposition.DENY,False)
        return replace(receipt,receipt_digest=stable_sha256(receipt.payload()))
