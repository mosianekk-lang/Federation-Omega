from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable, Mapping
import re

class EvidenceState(str, Enum):
    VERIFIED="VERIFIED"
    UNVERIFIED="UNVERIFIED"
    FAILED="FAILED"
    EXPIRED="EXPIRED"

@dataclass(frozen=True)
class ProviderEvidence:
    control_id: str
    state: EvidenceState
    provider: str
    artifact_ref: str
    observed_at: str
    details: Mapping[str, object] = field(default_factory=dict)
    def validate(self) -> None:
        if not self.control_id or not self.provider or not self.artifact_ref:
            raise ValueError("control_id, provider and artifact_ref are required")
        if re.search(r"(sk-[A-Za-z0-9_-]{16,}|-----BEGIN [A-Z ]+PRIVATE KEY-----)", self.artifact_ref):
            raise ValueError("secret-like material must never appear in evidence references")
        datetime.fromisoformat(self.observed_at.replace("Z","+00:00"))

@dataclass(frozen=True)
class DeploymentIntent:
    environment: str
    region: str
    private_mna_enabled: bool = True
    market_intelligence_enabled: bool = True
    live_financial_effects_enabled: bool = False
    destructive_actions_enabled: bool = False
    enterprise_idp_required: bool = True
    def validate(self) -> None:
        if self.environment not in {"STAGING","PRODUCTION"}: raise ValueError("environment must be STAGING or PRODUCTION")
        if not self.region: raise ValueError("region is required")
        if self.live_financial_effects_enabled or self.destructive_actions_enabled:
            raise PermissionError("CIOS production intent cannot enable consequential financial or destructive authority")

@dataclass(frozen=True)
class QualificationDecision:
    qualified: bool
    maturity: str
    missing_controls: tuple[str,...]
    failed_controls: tuple[str,...]
    expired_controls: tuple[str,...]
    evidence_controls: tuple[str,...]

class ProductionQualificationGate:
    BASE_CONTROLS=(
        "SOURCE_ADMISSION","PROVIDER_RUNTIME_IDENTITY","ENTERPRISE_IDP_MFA","TENANT_ISOLATION",
        "ENCRYPTION_AT_REST_AND_TRANSIT","KMS_KEY_MANAGEMENT","MALWARE_SCANNING","DLP_AND_REDACTION",
        "IMMUTABLE_AUDIT_LOG","HEALTH_READBACK","PERSISTENCE_READBACK","ROLLBACK_PROOF","BACKUP_RESTORE_PROOF",
        "OBSERVABILITY_ALERTING","VULNERABILITY_SCAN","RATE_LIMIT_AND_ABUSE_CONTROL","INCIDENT_RESPONSE_AND_DR",
    )
    MARKET_CONTROL="MARKET_DATA_ENTITLEMENT_AND_FRESHNESS"
    PRIVATE_MNA_CONTROL="PRIVATE_DATA_RESIDENCY_AND_RETENTION"
    def __init__(self, *, max_age_days:int=30)->None:
        if max_age_days<=0: raise ValueError("max_age_days must be positive")
        self.max_age_days=max_age_days
    def required_controls(self,intent:DeploymentIntent)->tuple[str,...]:
        intent.validate();controls=list(self.BASE_CONTROLS)
        if intent.market_intelligence_enabled:controls.append(self.MARKET_CONTROL)
        if intent.private_mna_enabled:controls.append(self.PRIVATE_MNA_CONTROL)
        return tuple(controls)
    def evaluate(self,intent:DeploymentIntent,evidence:Iterable[ProviderEvidence],*,now:datetime|None=None)->QualificationDecision:
        required=self.required_controls(intent);now=now or datetime.now(timezone.utc);by={}
        rank={EvidenceState.VERIFIED:4,EvidenceState.EXPIRED:3,EvidenceState.FAILED:2,EvidenceState.UNVERIFIED:1}
        for item in evidence:
            item.validate()
            if item.control_id not in required:continue
            obs=datetime.fromisoformat(item.observed_at.replace("Z","+00:00"));state=item.state
            if state==EvidenceState.VERIFIED and (now-obs).total_seconds()>self.max_age_days*86400:state=EvidenceState.EXPIRED
            if item.control_id not in by or rank[state]>rank[by[item.control_id]]:by[item.control_id]=state
        missing=tuple(sorted({c for c in required if c not in by}|{c for c,s in by.items() if s==EvidenceState.UNVERIFIED}))
        failed=tuple(sorted(c for c,s in by.items() if s==EvidenceState.FAILED));expired=tuple(sorted(c for c,s in by.items() if s==EvidenceState.EXPIRED))
        qualified=not missing and not failed and not expired and all(by.get(c)==EvidenceState.VERIFIED for c in required)
        maturity="PRODUCTION_VERIFIED" if qualified and intent.environment=="PRODUCTION" else "STAGING_VERIFIED" if qualified else "PROVIDER_QUALIFICATION_REQUIRED"
        return QualificationDecision(qualified,maturity,missing,failed,expired,tuple(sorted(by)))
