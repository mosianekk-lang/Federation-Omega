from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Iterable, Mapping
import re

from .production_gate import EvidenceBinding, EvidenceState, ProviderEvidence


_SECRET_RE = re.compile(
    r"(?:[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|"
    r"-----BEGIN [A-Z ]+PRIVATE KEY-----|sk-[A-Za-z0-9_-]{16,})"
)


@dataclass(frozen=True)
class IdentityClaims:
    subject: str
    tenant_id: str
    roles: tuple[str, ...]
    issuer: str
    mfa: bool
    observed_at: str

    def validate(self, expected_tenant: str, *, now: datetime | None = None) -> None:
        if not self.subject.strip() or not self.issuer.strip():
            raise PermissionError("authenticated subject and issuer required")
        if self.tenant_id != expected_tenant:
            raise PermissionError("identity tenant mismatch")
        if not self.mfa:
            raise PermissionError("enterprise MFA required")
        observed = datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise PermissionError("identity observation must be timezone-aware")
        reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if observed.astimezone(timezone.utc) > reference:
            raise PermissionError("future identity observation rejected")


@dataclass(frozen=True)
class ProviderAdapterRegistration:
    adapter_id: str
    provider: str
    control_id: str
    binding: EvidenceBinding
    attestor_id: str

    def validate(self) -> None:
        if not self.adapter_id.strip() or not self.provider.strip() or not self.control_id.strip():
            raise ValueError("adapter registration identity is required")
        if not self.attestor_id.strip():
            raise ValueError("registered independent attestor is required")
        self.binding.validate()
        if self.binding.provider != self.provider:
            raise ValueError("adapter provider and target provider mismatch")


@dataclass(frozen=True)
class AdapterProbe:
    adapter_id: str
    provider: str
    healthy: bool
    control_ids: tuple[str, ...]
    evidence_ref: str
    observed_at: str
    details: Mapping[str, object] = field(default_factory=dict)
    binding: EvidenceBinding | None = None
    attestation: str = ""
    attestor_id: str = ""
    executor_id: str = ""

    def validate(self, *, now: datetime | None = None, max_age_days: int = 30) -> None:
        if not self.adapter_id.strip() or not self.provider.strip():
            raise ValueError("adapter_id and provider are required")
        if len(self.control_ids) != 1:
            raise ValueError("each registered provider adapter may attest exactly one control")
        if not self.evidence_ref.strip() or _SECRET_RE.search(self.evidence_ref):
            raise ValueError("evidence_ref must be non-secret")
        observed = datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        observed = observed.astimezone(timezone.utc)
        if observed > reference:
            raise ValueError("future adapter probe evidence rejected")
        if (reference - observed).total_seconds() > max_age_days * 86400:
            raise ValueError("adapter probe evidence is stale")
        if self.binding is None:
            raise ValueError("adapter probe target binding is required")
        self.binding.validate()
        if not self.attestation.strip() or not self.attestor_id.strip() or not self.executor_id.strip():
            raise ValueError("adapter probe attestation fields are required")
        if self.attestor_id == self.executor_id:
            raise ValueError("adapter probe cannot be self-attested")


@dataclass(frozen=True)
class ProductionBindingIntent:
    tenant_id: str
    private_mna_enabled: bool = True
    market_intelligence_enabled: bool = True

    def validate(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("tenant_id is required")


@dataclass(frozen=True)
class DataPlaneBindingReport:
    ready: bool
    missing_controls: tuple[str, ...]
    failed_adapters: tuple[str, ...]
    provider_evidence: tuple[ProviderEvidence, ...]


ProbeAttestationVerifier = Callable[[AdapterProbe], bool]


class ProductionDataPlanePreflight:
    ALWAYS_REQUIRED = (
        "PROVIDER_RUNTIME_IDENTITY",
        "ENTERPRISE_IDP_MFA",
        "TENANT_ISOLATION",
        "ENCRYPTION_AT_REST_AND_TRANSIT",
        "KMS_KEY_MANAGEMENT",
        "MALWARE_SCANNING",
        "DLP_AND_REDACTION",
        "IMMUTABLE_AUDIT_LOG",
        "OBSERVABILITY_ALERTING",
        "RATE_LIMIT_AND_ABUSE_CONTROL",
    )
    MARKET_CONTROL = "MARKET_DATA_ENTITLEMENT_AND_FRESHNESS"
    PRIVATE_CONTROL = "PRIVATE_DATA_RESIDENCY_AND_RETENTION"

    def __init__(
        self,
        registrations: Iterable[ProviderAdapterRegistration] = (),
        *,
        attestation_verifier: ProbeAttestationVerifier | None = None,
    ) -> None:
        self.registrations: dict[str, ProviderAdapterRegistration] = {}
        for registration in registrations:
            registration.validate()
            if registration.adapter_id in self.registrations:
                raise ValueError("duplicate provider adapter registration")
            self.registrations[registration.adapter_id] = registration
        self.attestation_verifier = attestation_verifier

    def required_controls(self, intent: ProductionBindingIntent) -> tuple[str, ...]:
        intent.validate()
        controls = list(self.ALWAYS_REQUIRED)
        if intent.private_mna_enabled:
            controls.append(self.PRIVATE_CONTROL)
        if intent.market_intelligence_enabled:
            controls.append(self.MARKET_CONTROL)
        return tuple(controls)

    def evaluate(
        self,
        intent: ProductionBindingIntent,
        claims: IdentityClaims,
        probes: Iterable[AdapterProbe],
        *,
        now: datetime | None = None,
        max_age_days: int = 30,
    ) -> DataPlaneBindingReport:
        intent.validate()
        reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        claims.validate(intent.tenant_id, now=reference)
        required = set(self.required_controls(intent))
        covered: set[str] = set()
        evidence: list[ProviderEvidence] = []
        failed: list[str] = []

        for probe in probes:
            try:
                probe.validate(now=reference, max_age_days=max_age_days)
                registration = self.registrations[probe.adapter_id]
                registration.validate()
                control = probe.control_ids[0]
                if control not in required:
                    raise ValueError("adapter control is not required for this intent")
                if registration.control_id != control:
                    raise ValueError("adapter is not registered for the claimed control")
                if registration.provider != probe.provider:
                    raise ValueError("adapter provider mismatch")
                if registration.binding != probe.binding:
                    raise ValueError("adapter target binding mismatch")
                if registration.binding.tenant_id != intent.tenant_id:
                    raise ValueError("adapter tenant binding mismatch")
                if registration.attestor_id != probe.attestor_id:
                    raise ValueError("adapter attestor mismatch")
                if self.attestation_verifier is None or not self.attestation_verifier(probe):
                    raise ValueError("adapter attestation verification failed")
                item = ProviderEvidence(
                    control,
                    EvidenceState.VERIFIED,
                    probe.provider,
                    probe.evidence_ref,
                    probe.observed_at,
                    dict(probe.details),
                    probe.binding,
                    probe.attestation,
                    probe.attestor_id,
                    probe.executor_id,
                )
                item.validate(
                    now=reference,
                    expected_binding=registration.binding,
                    require_attestation=True,
                )
            except (KeyError, PermissionError, TypeError, ValueError):
                failed.append(probe.adapter_id)
                continue
            if not probe.healthy:
                failed.append(probe.adapter_id)
                continue
            covered.add(control)
            evidence.append(item)

        missing = tuple(sorted(required - covered))
        return DataPlaneBindingReport(
            not missing and not failed,
            missing,
            tuple(sorted(set(failed))),
            tuple(evidence),
        )
