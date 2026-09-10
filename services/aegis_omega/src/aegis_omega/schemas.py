from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator

class PrivacyTier(str, Enum):
    MINIMIZED = "minimized"
    RESTRICTED = "restricted"

class EventClass(str, Enum):
    DEVICE_INTEGRITY = "device_integrity"
    APP_RISK = "app_risk"
    NETWORK_RISK = "network_risk"
    IDENTITY_RISK = "identity_risk"
    FORENSIC_ARTIFACT = "forensic_artifact"
    PLATFORM_ALERT = "platform_alert"
    CONTROL_STATE = "control_state"

class SecurityEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=3, max_length=128)
    device_id: str = Field(min_length=3, max_length=256)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_class: EventClass
    severity: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    attributes: dict[str, Any] = Field(default_factory=dict)
    source: str = Field(min_length=2, max_length=128)
    privacy_tier: PrivacyTier = PrivacyTier.MINIMIZED
    consent: bool = True

    @field_validator("attributes")
    @classmethod
    def bound_attributes(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 64:
            raise ValueError("AEGIS event attributes exceed 64 keys")
        try:
            size = len(json.dumps(value, default=str, ensure_ascii=False).encode("utf-8"))
        except Exception as exc:
            raise ValueError("AEGIS event attributes are not safely serializable") from exc
        if size > 32768:
            raise ValueError("AEGIS event attributes exceed 32 KiB")
        return value

class SealedEvent(BaseModel):
    event: SecurityEvent
    digest_sha256: str
    signature_hmac_sha256: str
    provenance_key_id: str = Field(default="default", min_length=1, max_length=128)
    normalized_at: datetime

class Signal(BaseModel):
    name: str
    score: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)

class Assessment(BaseModel):
    case_id: str
    risk_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    disposition: Literal["observe", "investigate", "containment_recommended"]
    signals: list[Signal]
    requires_human_approval: bool = True
    rationale: list[str] = Field(default_factory=list)

class CandidateMetrics(BaseModel):
    candidate_id: str
    unseen_family_recall: float = Field(ge=0, le=1)
    false_positive_rate: float = Field(ge=0, le=1)
    privacy_leakage: float = Field(ge=0, le=1)
    poisoning_resilience: float = Field(ge=0, le=1)
    drift_resilience: float = Field(ge=0, le=1)
    adversarial_resilience: float = Field(ge=0, le=1)
    calibration_error: float = Field(ge=0, le=1)
    rollback_test_passed: bool
    provenance_test_passed: bool
    shadow_test_passed: bool
    canary_test_passed: bool

class CertificationResult(BaseModel):
    candidate_id: str
    certified: bool
    failed_gates: list[str]
    promotion: Literal["reject", "eligible_for_signed_human_promotion"]
