from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Mapping
import re

from .production_gate import EvidenceState, ProviderEvidence

_SECRET_RE = re.compile(r"(?:[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|-----BEGIN [A-Z ]+PRIVATE KEY-----)")

@dataclass(frozen=True)
class IdentityClaims:
    subject: str
    tenant_id: str
    roles: tuple[str,...]
    issuer: str
    mfa: bool
    observed_at: str
    def validate(self, expected_tenant: str) -> None:
        if not self.subject.strip() or not self.issuer.strip():
            raise PermissionError("authenticated subject and issuer required")
        if self.tenant_id != expected_tenant:
            raise PermissionError("identity tenant mismatch")
        if not self.mfa:
            raise PermissionError("enterprise MFA required")
        datetime.fromisoformat(self.observed_at.replace("Z","+00:00"))

@dataclass(frozen=True)
class AdapterProbe:
    adapter_id: str
    provider: str
    healthy: bool
    control_ids: tuple[str,...]
    evidence_ref: str
    observed_at: str
    details: Mapping[str,object] = field(default_factory=dict)
    def validate(self, *, now:datetime|None=None, max_age_days:int=30) -> None:
        if not self.adapter_id.strip() or not self.provider.strip() or not self.control_ids:
            raise ValueError("adapter_id, provider and control_ids are required")
        if not self.evidence_ref.strip() or _SECRET_RE.search(self.evidence_ref):
            raise ValueError("evidence_ref must be non-secret")
        obs=datetime.fromisoformat(self.observed_at.replace("Z","+00:00"))
        now=now or datetime.now(timezone.utc)
        if obs.tzinfo is None: raise ValueError("observed_at must be timezone-aware")
        if (now-obs).total_seconds()>max_age_days*86400:
            raise ValueError("adapter probe evidence is stale")

@dataclass(frozen=True)
class ProductionBindingIntent:
    tenant_id: str
    private_mna_enabled: bool = True
    market_intelligence_enabled: bool = True
    def validate(self)->None:
        if not self.tenant_id.strip(): raise ValueError("tenant_id is required")

@dataclass(frozen=True)
class DataPlaneBindingReport:
    ready: bool
    missing_controls: tuple[str,...]
    failed_adapters: tuple[str,...]
    provider_evidence: tuple[ProviderEvidence,...]

class ProductionDataPlanePreflight:
    ALWAYS_REQUIRED=(
        "PROVIDER_RUNTIME_IDENTITY","ENTERPRISE_IDP_MFA","TENANT_ISOLATION",
        "ENCRYPTION_AT_REST_AND_TRANSIT","KMS_KEY_MANAGEMENT","MALWARE_SCANNING",
        "DLP_AND_REDACTION","IMMUTABLE_AUDIT_LOG","OBSERVABILITY_ALERTING",
        "RATE_LIMIT_AND_ABUSE_CONTROL",
    )
    MARKET_CONTROL="MARKET_DATA_ENTITLEMENT_AND_FRESHNESS"
    PRIVATE_CONTROL="PRIVATE_DATA_RESIDENCY_AND_RETENTION"
    def required_controls(self,intent:ProductionBindingIntent)->tuple[str,...]:
        intent.validate(); controls=list(self.ALWAYS_REQUIRED)
        if intent.private_mna_enabled: controls.append(self.PRIVATE_CONTROL)
        if intent.market_intelligence_enabled: controls.append(self.MARKET_CONTROL)
        return tuple(controls)
    def evaluate(self,intent:ProductionBindingIntent,claims:IdentityClaims,probes:Iterable[AdapterProbe],*,now:datetime|None=None,max_age_days:int=30)->DataPlaneBindingReport:
        intent.validate(); claims.validate(intent.tenant_id)
        now=now or datetime.now(timezone.utc)
        required=set(self.required_controls(intent)); covered=set(); evidence=[]; failed=[]
        for probe in probes:
            try:
                probe.validate(now=now,max_age_days=max_age_days)
            except Exception:
                failed.append(probe.adapter_id); continue
            if not probe.healthy:
                failed.append(probe.adapter_id); continue
            compiled=[]
            try:
                for control in probe.control_ids:
                    if control in required:
                        item=ProviderEvidence(control,EvidenceState.VERIFIED,probe.provider,probe.evidence_ref,probe.observed_at,dict(probe.details))
                        item.validate()
                        compiled.append((control,item))
            except Exception:
                failed.append(probe.adapter_id)
                continue
            for control,item in compiled:
                covered.add(control)
                evidence.append(item)
        missing=tuple(sorted(required-covered))
        return DataPlaneBindingReport(not missing and not failed,missing,tuple(sorted(set(failed))),tuple(evidence))
