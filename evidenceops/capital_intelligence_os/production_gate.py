from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Iterable, Mapping
import re


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}|-----BEGIN [A-Z ]+PRIVATE KEY-----)"
)


class EvidenceState(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class EvidenceBinding:
    """Exact deployment target to which every production receipt must bind."""

    provider: str
    project: str
    region: str
    environment: str
    service: str
    tenant_id: str
    source_sha: str
    image_digest: str

    def validate(self) -> None:
        required = (
            self.provider,
            self.project,
            self.region,
            self.service,
            self.tenant_id,
        )
        if any(not value.strip() for value in required):
            raise ValueError("provider target fields are required")
        if self.environment not in {"STAGING", "PRODUCTION"}:
            raise ValueError("target environment must be STAGING or PRODUCTION")
        if not _SHA_RE.fullmatch(self.source_sha):
            raise ValueError("target source_sha must be a lowercase Git SHA")
        if not _DIGEST_RE.fullmatch(self.image_digest):
            raise ValueError("target image_digest must be SHA-256")


@dataclass(frozen=True)
class ProviderEvidence:
    control_id: str
    state: EvidenceState
    provider: str
    artifact_ref: str
    observed_at: str
    details: Mapping[str, object] = field(default_factory=dict)
    binding: EvidenceBinding | None = None
    attestation: str = ""
    attestor_id: str = ""
    executor_id: str = ""

    def observation_time(self) -> datetime:
        observed = datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        return observed.astimezone(timezone.utc)

    def validate(
        self,
        *,
        now: datetime | None = None,
        expected_binding: EvidenceBinding | None = None,
        require_attestation: bool = False,
        future_tolerance: timedelta = timedelta(minutes=5),
    ) -> None:
        if not self.control_id or not self.provider or not self.artifact_ref:
            raise ValueError("control_id, provider and artifact_ref are required")
        if _SECRET_RE.search(self.artifact_ref):
            raise ValueError("secret-like material must never appear in evidence references")
        observed = self.observation_time()
        reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if observed > reference + future_tolerance:
            raise ValueError("future-dated provider evidence is not admissible")
        if expected_binding is not None:
            expected_binding.validate()
            if self.binding != expected_binding:
                raise ValueError("provider evidence target binding mismatch")
            if self.provider != expected_binding.provider:
                raise ValueError("provider evidence provider mismatch")
        if require_attestation:
            if self.binding is None:
                raise ValueError("provider evidence binding is required")
            self.binding.validate()
            if not self.attestation.strip() or not self.attestor_id.strip() or not self.executor_id.strip():
                raise ValueError("independent provider attestation fields are required")
            if self.attestor_id == self.executor_id:
                raise ValueError("provider evidence cannot be self-attested")


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
        if self.environment not in {"STAGING", "PRODUCTION"}:
            raise ValueError("environment must be STAGING or PRODUCTION")
        if not self.region:
            raise ValueError("region is required")
        if self.live_financial_effects_enabled or self.destructive_actions_enabled:
            raise PermissionError(
                "CIOS production intent cannot enable consequential financial or destructive authority"
            )


@dataclass(frozen=True)
class QualificationDecision:
    qualified: bool
    maturity: str
    missing_controls: tuple[str, ...]
    failed_controls: tuple[str, ...]
    expired_controls: tuple[str, ...]
    evidence_controls: tuple[str, ...]


AttestationVerifier = Callable[[ProviderEvidence], bool]


class ProductionQualificationGate:
    BASE_CONTROLS = (
        "SOURCE_ADMISSION",
        "PROVIDER_RUNTIME_IDENTITY",
        "ENTERPRISE_IDP_MFA",
        "TENANT_ISOLATION",
        "ENCRYPTION_AT_REST_AND_TRANSIT",
        "KMS_KEY_MANAGEMENT",
        "MALWARE_SCANNING",
        "DLP_AND_REDACTION",
        "IMMUTABLE_AUDIT_LOG",
        "HEALTH_READBACK",
        "PERSISTENCE_READBACK",
        "ROLLBACK_PROOF",
        "BACKUP_RESTORE_PROOF",
        "OBSERVABILITY_ALERTING",
        "VULNERABILITY_SCAN",
        "RATE_LIMIT_AND_ABUSE_CONTROL",
        "INCIDENT_RESPONSE_AND_DR",
    )
    MARKET_CONTROL = "MARKET_DATA_ENTITLEMENT_AND_FRESHNESS"
    PRIVATE_MNA_CONTROL = "PRIVATE_DATA_RESIDENCY_AND_RETENTION"

    def __init__(
        self,
        *,
        max_age_days: int = 30,
        expected_binding: EvidenceBinding | None = None,
        attestation_verifier: AttestationVerifier | None = None,
    ) -> None:
        if max_age_days <= 0:
            raise ValueError("max_age_days must be positive")
        self.max_age_days = max_age_days
        self.expected_binding = expected_binding
        self.attestation_verifier = attestation_verifier

    def required_controls(self, intent: DeploymentIntent) -> tuple[str, ...]:
        intent.validate()
        controls = list(self.BASE_CONTROLS)
        if intent.market_intelligence_enabled:
            controls.append(self.MARKET_CONTROL)
        if intent.private_mna_enabled:
            controls.append(self.PRIVATE_MNA_CONTROL)
        return tuple(controls)

    def _admit(
        self,
        item: ProviderEvidence,
        *,
        intent: DeploymentIntent,
        now: datetime,
    ) -> tuple[EvidenceState, datetime]:
        production = intent.environment == "PRODUCTION"
        item.validate(
            now=now,
            expected_binding=self.expected_binding if production else None,
            require_attestation=production,
        )
        observed = item.observation_time()
        if production:
            if self.expected_binding is None or self.attestation_verifier is None:
                raise ValueError("production evidence verifier and exact target binding are required")
            if self.expected_binding.environment != intent.environment:
                raise ValueError("deployment intent and evidence environment mismatch")
            if self.expected_binding.region != intent.region:
                raise ValueError("deployment intent and evidence region mismatch")
            if not self.attestation_verifier(item):
                raise ValueError("provider attestation verification failed")
        state = item.state
        if state == EvidenceState.VERIFIED:
            age = (now - observed).total_seconds()
            if age > self.max_age_days * 86400:
                state = EvidenceState.EXPIRED
        return state, observed

    def evaluate(
        self,
        intent: DeploymentIntent,
        evidence: Iterable[ProviderEvidence],
        *,
        now: datetime | None = None,
    ) -> QualificationDecision:
        required = self.required_controls(intent)
        reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        admitted: dict[str, list[tuple[EvidenceState, datetime]]] = {}
        invalid: set[str] = set()

        for item in evidence:
            if item.control_id not in required:
                continue
            try:
                state, observed = self._admit(item, intent=intent, now=reference)
            except (TypeError, ValueError):
                invalid.add(item.control_id)
                continue
            admitted.setdefault(item.control_id, []).append((state, observed))

        by_control: dict[str, EvidenceState] = {}
        for control, observations in admitted.items():
            states = {state for state, _ in observations}
            # A failure is an unresolved contradiction and always vetoes promotion.
            if EvidenceState.FAILED in states:
                by_control[control] = EvidenceState.FAILED
                continue
            latest_state, _ = max(observations, key=lambda item: item[1])
            by_control[control] = latest_state

        failed_set = {control for control, state in by_control.items() if state == EvidenceState.FAILED}
        failed_set.update(invalid)
        expired = tuple(
            sorted(control for control, state in by_control.items() if state == EvidenceState.EXPIRED)
        )
        missing = tuple(
            sorted(
                {control for control in required if control not in by_control and control not in invalid}
                | {
                    control
                    for control, state in by_control.items()
                    if state == EvidenceState.UNVERIFIED
                }
            )
        )
        failed = tuple(sorted(failed_set))
        qualified = (
            not missing
            and not failed
            and not expired
            and all(by_control.get(control) == EvidenceState.VERIFIED for control in required)
        )
        if qualified and intent.environment == "PRODUCTION":
            maturity = "PRODUCTION_VERIFIED"
        elif qualified:
            maturity = "STAGING_VERIFIED"
        else:
            maturity = "PROVIDER_QUALIFICATION_REQUIRED"
        return QualificationDecision(
            qualified,
            maturity,
            missing,
            failed,
            expired,
            tuple(sorted(by_control)),
        )
