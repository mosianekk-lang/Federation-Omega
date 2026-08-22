#!/usr/bin/env python3
"""Run a zero-effect GitHub OIDC -> Google STS identity diagnostic.

The diagnostic never prints or persists OIDC/access tokens, never impersonates a
service account, and never calls a model endpoint. A classified identity failure
is a successful diagnostic result and is represented in the receipt, not by a
misleading workflow failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping


SCHEMA = "SOVARA_WIF_IDENTITY_DIAGNOSTIC_V1"
OPERATION = "ZERO_EFFECT_STS_EXCHANGE"
STS_URL = "https://sts.googleapis.com/v1/token"
_PROVIDER_RE = re.compile(
    r"^projects/(?P<project_number>[1-9][0-9]*)/locations/global/"
    r"workloadIdentityPools/(?P<pool>[A-Za-z0-9][A-Za-z0-9._-]*)/"
    r"providers/(?P<provider>[A-Za-z0-9][A-Za-z0-9._-]*)$"
)
_SAFE_ERROR_CODES = {
    "invalid_target",
    "permission_denied",
    "unauthorized_client",
    "invalid_grant",
    "invalid_subject_token",
    "invalid_request",
    "network_error",
    "oidc_http_error",
    "oidc_response_invalid",
    "sts_response_invalid",
}


def parse_provider_resource(value: str) -> dict[str, str] | None:
    """Return parsed components only for a complete provider resource name."""
    match = _PROVIDER_RE.fullmatch(value.strip())
    return match.groupdict() if match else None


def service_account_matches_project(service_account: str, project_id: str) -> bool:
    return bool(
        service_account
        and project_id
        and service_account.endswith(f"@{project_id}.iam.gserviceaccount.com")
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_error_code(value: Any, fallback: str = "sts_error") -> str:
    candidate = str(value or "").strip().lower()
    return candidate if candidate in _SAFE_ERROR_CODES else fallback


def classify_sts(status: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Map an STS response to a stable, non-secret readiness classification."""
    if status == 200 and isinstance(payload.get("access_token"), str):
        return {
            "error_code": None,
            "classification": "STS_EXCHANGE_SUCCEEDED",
            "current_level": "R1",
            "next_gate": "R2_PROVIDER_AND_SERVICE_ACCOUNT_READBACK",
        }

    code = _safe_error_code(payload.get("error"))
    if code == "invalid_target":
        classification = "WIF_TARGET_UNAVAILABLE_OR_DISABLED"
        next_gate = "R2_PROVIDER_EXISTS_ENABLED_AND_AUDIENCE_READBACK"
    elif code in {"permission_denied", "unauthorized_client", "invalid_grant"}:
        classification = "WIF_SUBJECT_OR_ATTRIBUTE_DENIED"
        next_gate = "R2_ISSUER_ATTRIBUTE_MAPPING_CONDITION_AND_SUBJECT_READBACK"
    elif code == "invalid_subject_token":
        classification = "WIF_SUBJECT_TOKEN_REJECTED"
        next_gate = "R2_GITHUB_OIDC_CLAIMS_AND_PROVIDER_MAPPING_READBACK"
    else:
        classification = "STS_EXCHANGE_FAILED_CLASSIFIED"
        next_gate = "R2_STS_ERROR_CLASS_AND_PROVIDER_CONFIGURATION_READBACK"
    return {
        "error_code": code,
        "classification": classification,
        "current_level": "R1",
        "next_gate": next_gate,
    }


def make_base_receipt(
    provider_resource: str,
    project_id: str,
    service_account: str,
    environment: Mapping[str, str],
) -> dict[str, Any]:
    parsed = parse_provider_resource(provider_resource)
    sts_audience = f"//iam.googleapis.com/{provider_resource}" if parsed else ""
    return {
        "schema": SCHEMA,
        "operation": OPERATION,
        "repository": environment.get("GITHUB_REPOSITORY", "unknown"),
        "ref": environment.get("GITHUB_REF", "unknown"),
        "head_sha": environment.get("GITHUB_SHA", "unknown"),
        "provider_resource_syntax_valid": parsed is not None,
        "github_oidc_audience_sha256": _sha256(provider_resource) if parsed else None,
        "sts_audience_sha256": _sha256(sts_audience) if parsed else None,
        "service_account_project_match": service_account_matches_project(
            service_account, project_id
        ),
        "oidc_token_requested": False,
        "google_sts_invoked": False,
        "sts_http_status": None,
        "error_code": None,
        "classification": "PENDING",
        "current_level": "R1",
        "next_gate": "R2_CONFIGURATION_VALIDATION",
        "model_provider_invoked": False,
        "service_account_impersonated": False,
        "credential_value_exposed": False,
        "mutation_performed": False,
    }


def apply_sts_result(
    receipt: Mapping[str, Any], status: int, payload: Mapping[str, Any]
) -> dict[str, Any]:
    result = dict(receipt)
    result["google_sts_invoked"] = True
    result["sts_http_status"] = status
    result.update(classify_sts(status, payload))
    return result


def render_receipt(receipt: Mapping[str, Any]) -> str:
    """Render only the explicitly sanitized receipt fields."""
    return json.dumps(dict(receipt), indent=2, sort_keys=True) + "\n"


def _request_json(request: urllib.request.Request) -> tuple[int, dict[str, Any]]:
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = int(response.status)
            raw = response.read(1_000_000)
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        raw = exc.read(1_000_000)
    except (urllib.error.URLError, TimeoutError):
        return 0, {"error": "network_error"}

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return status, {"error": "sts_response_invalid"}
    return status, payload if isinstance(payload, dict) else {"error": "sts_response_invalid"}


def _github_oidc_url(base_url: str, audience: str) -> str:
    parts = urllib.parse.urlsplit(base_url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query.append(("audience", audience))
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), parts.fragment)
    )


def run_diagnostic(
    provider_resource: str,
    project_id: str,
    service_account: str,
    environment: Mapping[str, str],
) -> dict[str, Any]:
    receipt = make_base_receipt(
        provider_resource, project_id, service_account, environment
    )
    if not receipt["provider_resource_syntax_valid"]:
        receipt.update(
            classification="WIF_CONFIGURATION_INVALID",
            error_code="invalid_request",
            next_gate="R1_CORRECT_PROVIDER_RESOURCE_SYNTAX",
        )
        return receipt
    if not receipt["service_account_project_match"]:
        receipt.update(
            classification="WIF_SERVICE_ACCOUNT_PROJECT_MISMATCH",
            error_code="invalid_request",
            next_gate="R1_ALIGN_PROJECT_AND_SERVICE_ACCOUNT_IDENTITIES",
        )
        return receipt

    request_url = environment.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    request_token = environment.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    if not request_url or not request_token:
        receipt.update(
            classification="GITHUB_OIDC_UNAVAILABLE",
            error_code="invalid_request",
            next_gate="R1_ENABLE_ID_TOKEN_WRITE_IN_GITHUB_ACTIONS",
        )
        return receipt

    receipt["oidc_token_requested"] = True
    oidc_request = urllib.request.Request(
        _github_oidc_url(request_url, provider_resource),
        headers={"Authorization": f"Bearer {request_token}"},
        method="GET",
    )
    oidc_status, oidc_payload = _request_json(oidc_request)
    subject_token = oidc_payload.get("value")
    if oidc_status != 200 or not isinstance(subject_token, str) or not subject_token:
        receipt.update(
            classification="GITHUB_OIDC_REQUEST_FAILED",
            error_code=("network_error" if oidc_status == 0 else "oidc_http_error"),
            next_gate="R1_GITHUB_OIDC_TOKEN_ISSUANCE",
        )
        return receipt

    sts_audience = f"//iam.googleapis.com/{provider_resource}"
    form = urllib.parse.urlencode(
        {
            "audience": sts_audience,
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "requested_token_type": "urn:ietf:params:oauth:token-type:access_token",
            "scope": "https://www.googleapis.com/auth/cloud-platform",
            "subject_token": subject_token,
            "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
        }
    ).encode("ascii")
    sts_request = urllib.request.Request(
        STS_URL,
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    status, payload = _request_json(sts_request)
    return apply_sts_result(receipt, status, payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default=os.getenv("WIF_PROVIDER", ""))
    parser.add_argument("--project-id", default=os.getenv("PROJECT_ID", ""))
    parser.add_argument(
        "--service-account", default=os.getenv("WIF_SERVICE_ACCOUNT", "")
    )
    parser.add_argument(
        "--output", default="sovara_wif_identity_diagnostic_receipt.json"
    )
    args = parser.parse_args()

    receipt = run_diagnostic(
        args.provider, args.project_id, args.service_account, os.environ
    )
    output_path = pathlib.Path(args.output)
    output_path.write_text(render_receipt(receipt), encoding="utf-8")
    print(f"SOVARA_WIF_DIAGNOSTIC_CLASSIFICATION={receipt['classification']}")
    print(f"SOVARA_WIF_DIAGNOSTIC_LEVEL={receipt['current_level']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
