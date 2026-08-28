from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
import re
from typing import Sequence

from .canary import CreativeCanarySpec

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CanaryAuthorityState(str, Enum):
    HOLD_ROUTE_CATALOG = "HOLD_ROUTE_CATALOG"
    HOLD_PROVIDER_CAPABILITY = "HOLD_PROVIDER_CAPABILITY"
    HOLD_ZERO_COST_VERIFICATION = "HOLD_ZERO_COST_VERIFICATION"
    HOLD_CREDENTIAL = "HOLD_CREDENTIAL"
    HOLD_RUNTIME_BINDING = "HOLD_RUNTIME_BINDING"
    HOLD_FINITE_SPEND_AUTHORITY = "HOLD_FINITE_SPEND_AUTHORITY"
    HOLD_EFFECT_AUTHORITY = "HOLD_EFFECT_AUTHORITY"
    READY_FOR_ONE_CANARY = "READY_FOR_ONE_CANARY"


@dataclass(frozen=True, slots=True)
class ImageRouteCatalogEvidence:
    snapshot_id: str
    checked_at: str
    expires_at: str
    model_id: str
    endpoint: str
    output_modalities: tuple[str, ...]
    unit_price_usd: float | None
    pricing_unit: str
    provider_native_readback_supported: bool
    source_urls: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.snapshot_id.strip() or not self.model_id.strip():
            raise ValueError("snapshot_id and model_id are required")
        if not self.endpoint.startswith("https://"):
            raise ValueError("endpoint must be HTTPS")
        checked = _parse_timestamp(self.checked_at)
        expires = _parse_timestamp(self.expires_at)
        if expires <= checked:
            raise ValueError("expires_at must be later than checked_at")
        if not self.output_modalities:
            raise ValueError("output_modalities are required")
        if self.unit_price_usd is not None:
            price = float(self.unit_price_usd)
            if not isfinite(price) or price < 0:
                raise ValueError("unit_price_usd must be finite and non-negative")
        if not self.pricing_unit.strip():
            raise ValueError("pricing_unit is required")
        if not self.source_urls or any(not item.startswith("https://") for item in self.source_urls):
            raise ValueError("current HTTPS source_urls are required")

    def is_current(self, at: datetime) -> bool:
        point = at if at.tzinfo is not None else at.replace(tzinfo=timezone.utc)
        point = point.astimezone(timezone.utc)
        return _parse_timestamp(self.checked_at) <= point < _parse_timestamp(self.expires_at)

    @property
    def zero_cost_verified(self) -> bool:
        return self.unit_price_usd is not None and float(self.unit_price_usd) == 0.0


@dataclass(frozen=True, slots=True)
class CanaryExecutionBinding:
    credential_reference: str
    credential_bound: bool
    runtime_identity: str
    exact_request_sha256: str
    privacy_eligible: bool
    provider_effect_authority_bound: bool
    finite_spend_authorized: bool

    def __post_init__(self) -> None:
        if self.credential_bound and not self.credential_reference.strip():
            raise ValueError("bound credential requires a non-secret credential reference")
        if self.exact_request_sha256 and not _SHA256.fullmatch(self.exact_request_sha256.strip().lower()):
            raise ValueError("exact_request_sha256 must be a 64-character lowercase hex digest")


@dataclass(frozen=True, slots=True)
class CanaryAuthorityDecision:
    state: CanaryAuthorityState
    ready: bool
    zero_cost_route: bool
    next_gate: str
    reasons: tuple[str, ...]
    truth_boundary: str


_TRUTH_BOUNDARY = (
    "READY_FOR_ONE_CANARY proves only that current route-catalog, credential, runtime, privacy, spend and "
    "effect-authority preconditions are bound for one bounded public-synthetic image canary. It does not prove "
    "provider execution, asset generation, semantic quality, asset hash readback, rollback, repeated success, "
    "commercial value, publishing or production readiness."
)


def _parse_timestamp(value: str) -> datetime:
    candidate = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        raise ValueError("catalog timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def _decision(state: CanaryAuthorityState, *, zero_cost_route: bool, next_gate: str, reasons: Sequence[str]) -> CanaryAuthorityDecision:
    return CanaryAuthorityDecision(
        state=state,
        ready=state is CanaryAuthorityState.READY_FOR_ONE_CANARY,
        zero_cost_route=zero_cost_route,
        next_gate=next_gate,
        reasons=tuple(reasons),
        truth_boundary=_TRUTH_BOUNDARY,
    )


def evaluate_image_canary_authority(
    spec: CreativeCanarySpec,
    catalog: ImageRouteCatalogEvidence | None,
    binding: CanaryExecutionBinding,
    *,
    evaluated_at: datetime,
) -> CanaryAuthorityDecision:
    """Evaluate one image-canary execution boundary without granting authority."""

    if spec.provider_effect_authorized or float(spec.max_source_spend) != 0.0:
        raise ValueError("source canary must remain effect-disabled with zero source-authorized spend")

    if catalog is None or not catalog.is_current(evaluated_at):
        return _decision(
            CanaryAuthorityState.HOLD_ROUTE_CATALOG,
            zero_cost_route=False,
            next_gate="CAPTURE_CURRENT_PROVIDER_API_CATALOG_AND_PRICE_READBACK",
            reasons=("CURRENT_CATALOG_READBACK_REQUIRED",),
        )

    modalities = {item.strip().lower() for item in catalog.output_modalities if item.strip()}
    if "image" not in modalities or not catalog.endpoint.rstrip("/").endswith("/images"):
        return _decision(
            CanaryAuthorityState.HOLD_PROVIDER_CAPABILITY,
            zero_cost_route=catalog.zero_cost_verified,
            next_gate="SELECT_IMAGE_OUTPUT_ROUTE_WITH_EXACT_IMAGES_ENDPOINT",
            reasons=("IMAGE_OUTPUT_CAPABILITY_OR_ENDPOINT_UNVERIFIED",),
        )

    if not catalog.provider_native_readback_supported:
        return _decision(
            CanaryAuthorityState.HOLD_PROVIDER_CAPABILITY,
            zero_cost_route=catalog.zero_cost_verified,
            next_gate="SELECT_ROUTE_WITH_PROVIDER_NATIVE_REQUEST_AND_USAGE_READBACK",
            reasons=("PROVIDER_NATIVE_READBACK_REQUIRED",),
        )

    if catalog.unit_price_usd is None:
        return _decision(
            CanaryAuthorityState.HOLD_ZERO_COST_VERIFICATION,
            zero_cost_route=False,
            next_gate="READ_BACK_EXACT_CURRENT_UNIT_PRICE_FROM_PROVIDER_API_CATALOG",
            reasons=("UNIT_PRICE_UNVERIFIED",),
        )

    zero_cost = catalog.zero_cost_verified

    if not binding.credential_bound or not binding.credential_reference.strip():
        return _decision(
            CanaryAuthorityState.HOLD_CREDENTIAL,
            zero_cost_route=zero_cost,
            next_gate="BIND_NON_SECRET_OPENROUTER_CREDENTIAL_REFERENCE",
            reasons=("RUNTIME_CREDENTIAL_UNBOUND",),
        )

    if not binding.runtime_identity.strip() or not binding.exact_request_sha256.strip() or not binding.privacy_eligible:
        return _decision(
            CanaryAuthorityState.HOLD_RUNTIME_BINDING,
            zero_cost_route=zero_cost,
            next_gate="BIND_RUNTIME_IDENTITY_EXACT_REQUEST_HASH_AND_PUBLIC_SYNTHETIC_PRIVACY_ELIGIBILITY",
            reasons=("RUNTIME_REQUEST_OR_PRIVACY_BINDING_INCOMPLETE",),
        )

    if not zero_cost and not binding.finite_spend_authorized:
        return _decision(
            CanaryAuthorityState.HOLD_FINITE_SPEND_AUTHORITY,
            zero_cost_route=False,
            next_gate="BIND_EXPLICIT_FINITE_SPEND_CEILING_FOR_ONE_IMAGE",
            reasons=("PAID_ROUTE_REQUIRES_SEPARATE_FINITE_SPEND_AUTHORITY",),
        )

    if not binding.provider_effect_authority_bound:
        return _decision(
            CanaryAuthorityState.HOLD_EFFECT_AUTHORITY,
            zero_cost_route=zero_cost,
            next_gate="BIND_EXPLICIT_ONE_CALL_PROVIDER_EFFECT_AUTHORITY",
            reasons=("PROVIDER_EFFECT_AUTHORITY_NOT_BOUND",),
        )

    return _decision(
        CanaryAuthorityState.READY_FOR_ONE_CANARY,
        zero_cost_route=zero_cost,
        next_gate="EXECUTE_ONE_BOUND_PUBLIC_SYNTHETIC_IMAGE_CANARY_AND_CAPTURE_PROVIDER_ASSET_ROLLBACK_PROOF",
        reasons=(
            "CURRENT_CATALOG_VERIFIED",
            "IMAGE_ROUTE_CAPABILITY_VERIFIED",
            "CREDENTIAL_REFERENCE_BOUND",
            "RUNTIME_AND_REQUEST_BOUND",
            "PRIVACY_ELIGIBLE",
            "ZERO_COST_VERIFIED" if zero_cost else "FINITE_SPEND_AUTHORITY_BOUND",
            "ONE_CALL_EFFECT_AUTHORITY_BOUND",
        ),
    )
