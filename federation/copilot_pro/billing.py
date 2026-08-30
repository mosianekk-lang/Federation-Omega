from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re
from typing import Any, Mapping

_GITHUB_USER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_REFERENCE_RE = re.compile(r"^[A-Z0-9][A-Z0-9._:-]{2,127}$")
API_VERSION = "2026-03-10"
REQUIRED_PERMISSION = "Plan:read"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _finite_nonnegative(value: object, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must be finite and non-negative")
    return number


@dataclass(frozen=True)
class CopilotBillingUsageRequest:
    schema: str
    username: str
    year: int
    month: int
    endpoint_path: str
    method: str
    api_version: str
    accept: str
    credential_reference_id: str
    required_permission: str
    credential_value_included: bool
    billing_mutation_allowed: bool
    copilot_dispatch_allowed: bool
    request_sha256: str


@dataclass(frozen=True)
class CopilotBillingUsageSnapshot:
    schema: str
    username: str
    year: int
    month: int
    product: str
    unit_type: str
    gross_credits: float
    discounted_credits: float
    net_credits: float
    gross_amount_usd: float
    discount_amount_usd: float
    net_amount_usd: float
    model_count: int
    models: tuple[str, ...]
    response_semantic_verified: bool
    provider_call_was_read_only: bool
    credential_value_exposed: bool
    snapshot_sha256: str


def build_ai_credit_usage_request(
    *,
    username: str,
    year: int,
    month: int,
    credential_reference_id: str,
) -> CopilotBillingUsageRequest:
    """Build a value-free request plan for GitHub's personal AI-credit usage API.

    This function never accepts a token value. A separately authorised trusted
    runtime may resolve ``credential_reference_id`` transiently, but only if it
    independently proves GitHub user ``Plan: read`` permission.
    """

    username = str(username).strip()
    if not _GITHUB_USER_RE.fullmatch(username):
        raise ValueError("invalid GitHub username")
    if not 2000 <= int(year) <= 2100:
        raise ValueError("year is out of supported range")
    if not 1 <= int(month) <= 12:
        raise ValueError("month must be in 1..12")
    reference = str(credential_reference_id).strip().upper()
    if not _REFERENCE_RE.fullmatch(reference):
        raise ValueError("credential_reference_id must be an opaque reference")

    body = {
        "schema": "FCX_COPILOT_BILLING_USAGE_REQUEST_V1",
        "username": username,
        "year": int(year),
        "month": int(month),
        "endpoint_path": f"/users/{username}/settings/billing/ai_credit/usage?year={int(year)}&month={int(month)}",
        "method": "GET",
        "api_version": API_VERSION,
        "accept": "application/vnd.github+json",
        "credential_reference_id": reference,
        "required_permission": REQUIRED_PERMISSION,
        "credential_value_included": False,
        "billing_mutation_allowed": False,
        "copilot_dispatch_allowed": False,
    }
    return CopilotBillingUsageRequest(request_sha256=_digest(body), **body)


def parse_ai_credit_usage_response(
    *,
    request: CopilotBillingUsageRequest,
    status_code: int,
    payload: Mapping[str, Any],
    plan_read_permission_verified: bool,
    credential_value_exposed: bool = False,
) -> CopilotBillingUsageSnapshot:
    """Semantically verify and aggregate one provider-native usage response.

    It accepts only an HTTP 200 response whose user/time-period and Copilot AI
    Credit units match the request. It intentionally proves *usage*, not the
    subscription's included-credit allowance or additional-usage budget.
    """

    if request.method != "GET" or request.billing_mutation_allowed:
        raise ValueError("request is not read-only")
    if not plan_read_permission_verified:
        raise ValueError("GitHub user Plan:read permission is unverified")
    if credential_value_exposed:
        raise ValueError("credential values must never enter the usage snapshot")
    if int(status_code) != 200:
        raise ValueError(f"provider usage request failed with HTTP {status_code}")

    user = str(payload.get("user", "")).strip()
    if user.lower() != request.username.lower():
        raise ValueError("provider response user does not match request")
    period = payload.get("timePeriod")
    if not isinstance(period, Mapping):
        raise ValueError("provider response missing timePeriod")
    if int(period.get("year", -1)) != request.year:
        raise ValueError("provider response year mismatch")
    if "month" in period and int(period["month"]) != request.month:
        raise ValueError("provider response month mismatch")

    items = payload.get("usageItems")
    if not isinstance(items, list):
        raise ValueError("provider response missing usageItems")

    gross_credits = discount_credits = net_credits = 0.0
    gross_amount = discount_amount = net_amount = 0.0
    models: set[str] = set()
    matched_items = 0

    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("usageItems must contain objects")
        product = str(item.get("product", "")).strip()
        unit_type = str(item.get("unitType", "")).strip().lower()
        if product.lower() != "copilot ai credits" or unit_type != "ai-credits":
            continue
        matched_items += 1
        gross_credits += _finite_nonnegative(item.get("grossQuantity", 0), "grossQuantity")
        discount_credits += _finite_nonnegative(item.get("discountQuantity", 0), "discountQuantity")
        net_credits += _finite_nonnegative(item.get("netQuantity", 0), "netQuantity")
        gross_amount += _finite_nonnegative(item.get("grossAmount", 0), "grossAmount")
        discount_amount += _finite_nonnegative(item.get("discountAmount", 0), "discountAmount")
        net_amount += _finite_nonnegative(item.get("netAmount", 0), "netAmount")
        model = str(item.get("model", "")).strip()
        if model:
            models.add(model)

    # A valid zero-usage month may return an empty usageItems list. That is still
    # a semantic success if user/time binding is exact.
    body = {
        "schema": "FCX_COPILOT_BILLING_USAGE_SNAPSHOT_V1",
        "username": request.username,
        "year": request.year,
        "month": request.month,
        "product": "Copilot AI Credits",
        "unit_type": "ai-credits",
        "gross_credits": round(gross_credits, 6),
        "discounted_credits": round(discount_credits, 6),
        "net_credits": round(net_credits, 6),
        "gross_amount_usd": round(gross_amount, 6),
        "discount_amount_usd": round(discount_amount, 6),
        "net_amount_usd": round(net_amount, 6),
        "model_count": len(models),
        "models": tuple(sorted(models)),
        "response_semantic_verified": True,
        "provider_call_was_read_only": True,
        "credential_value_exposed": False,
    }
    return CopilotBillingUsageSnapshot(snapshot_sha256=_digest(body), **body)


__all__ = [
    "API_VERSION",
    "REQUIRED_PERMISSION",
    "CopilotBillingUsageRequest",
    "CopilotBillingUsageSnapshot",
    "build_ai_credit_usage_request",
    "parse_ai_credit_usage_response",
]
