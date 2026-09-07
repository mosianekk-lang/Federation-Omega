"""Strategic FUSE direct WIF/ADC Vertex A0 read v1.

This adapter closes only the no-effect provider-read predicate for GAP-STRATFUSE-002.
It uses the already-authenticated GitHub Actions WIF principal to perform GET-only
Service Usage and Vertex publisher-model reads. It never calls generateContent,
reads a Gemini secret, mutates IAM/provider state, deploys Cloud Run, shifts traffic,
or authorizes spend.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Mapping
import urllib.error
import urllib.request

SCHEMA = "STRATEGIC-FUSE-VERTEX-DIRECT-WIF-A0-V1"
VERSION = "1.0.0"
ACTION = "READ_GEMINI_VERTEX_CAPABILITY"
EXECUTOR_ROUTE = "GITHUB_ACTIONS_WIF_ADC_DIRECT_PROVIDER_READ"
TARGET = {
    "project": "sov-hybrid-suite",
    "location": "global",
    "model": "gemini-2.5-flash",
    "tenantId": "federation-omega",
}
SERVICE_URL = (
    "https://serviceusage.googleapis.com/v1/projects/"
    f"{TARGET['project']}/services/aiplatform.googleapis.com"
)
MODEL_URL = (
    "https://aiplatform.googleapis.com/v1/projects/"
    f"{TARGET['project']}/locations/{TARGET['location']}/publishers/google/models/{TARGET['model']}"
)


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


def _safe_error(value: object) -> str:
    text = " ".join(str(value).split())[:900]
    text = re.sub(r"(?i)(bearer|authorization|access[_ -]?token)\s*[:=]?\s*[^ ,;]+", r"\1=[REDACTED]", text)
    return text


def _default_token() -> str:
    proc = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        text=True,
        capture_output=True,
        check=False,
        timeout=25,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(proc.stderr.strip() or "WIF_ACCESS_TOKEN_UNAVAILABLE")
    return proc.stdout.strip()


def _default_principal() -> str:
    proc = subprocess.run(
        ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    return proc.stdout.strip().splitlines()[0] if proc.returncode == 0 and proc.stdout.strip() else ""


def _default_get(url: str, token: str) -> tuple[int, Mapping[str, Any]]:
    request = urllib.request.Request(
        url,
        headers={"accept": "application/json", "authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            raw = response.read().decode("utf-8", "replace")
            try:
                body = json.loads(raw) if raw else {}
            except Exception:
                body = {"raw_sha256": sha256(raw.encode()).hexdigest()}
            return int(response.status), body if isinstance(body, Mapping) else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            body = {"raw_sha256": sha256(raw.encode()).hexdigest()}
        return int(exc.code), body if isinstance(body, Mapping) else {}


def run_direct_wif_a0(
    *,
    source_ref: str,
    token_fn: Callable[[], str] = _default_token,
    principal_fn: Callable[[], str] = _default_principal,
    get_fn: Callable[[str, str], tuple[int, Mapping[str, Any]]] = _default_get,
) -> dict[str, Any]:
    source_ref = str(source_ref).strip()
    if not source_ref:
        raise ValueError("SOURCE_REF_REQUIRED")

    principal = principal_fn()
    token = ""
    service_status: int | None = None
    model_status: int | None = None
    service_state = "UNKNOWN"
    model_name: str | None = None
    model_version: str | None = None
    model_display_name: str | None = None
    model_launch_stage: str | None = None
    model_actions: object = None
    failure = ""
    failure_fingerprint = ""
    provider_authenticated = False
    service_verified = False
    model_verified = False

    try:
        token = token_fn().strip()
        if not token:
            raise RuntimeError("WIF_ACCESS_TOKEN_EMPTY")
        service_status, service = get_fn(SERVICE_URL, token)
        provider_authenticated = service_status not in {401, 403}
        service_state = str(service.get("state") or "UNKNOWN")
        service_verified = service_status == 200 and service_state == "ENABLED"
        if service_verified:
            model_status, model = get_fn(MODEL_URL, token)
            provider_authenticated = provider_authenticated and model_status not in {401, 403}
            model_name = str(model.get("name") or "") or None
            model_version = str(model.get("versionId") or "") or None
            model_display_name = str(model.get("displayName") or "") or None
            model_launch_stage = str(model.get("launchStage") or "") or None
            model_actions = model.get("supportedActions")
            expected_suffix = (
                f"projects/{TARGET['project']}/locations/{TARGET['location']}/"
                f"publishers/google/models/{TARGET['model']}"
            )
            model_verified = bool(
                model_status == 200
                and model_name
                and (model_name == expected_suffix or model_name.endswith("/" + expected_suffix))
            )
    except Exception as exc:
        failure = _safe_error(exc)

    verified = service_verified and model_verified and provider_authenticated
    if verified:
        state = "VERTEX_A0_DIRECT_WIF_READBACK_VERIFIED"
    elif not token:
        state = "HELD_WIF_ACCESS_TOKEN_UNAVAILABLE"
    elif service_status in {401, 403} or model_status in {401, 403}:
        state = "HELD_DIRECT_WIF_PROVIDER_AUTHORITY"
    elif not service_verified:
        state = "HELD_VERTEX_SERVICE_READBACK"
    else:
        state = "HELD_VERTEX_MODEL_READBACK"

    if not verified and not failure:
        failure = (
            f"serviceHttp={service_status};serviceState={service_state};"
            f"modelHttp={model_status};modelName={model_name};providerAuthenticated={provider_authenticated}"
        )
    if failure:
        failure_fingerprint = _digest({"state": state, "detail": failure})

    material: dict[str, Any] = {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "action": ACTION,
        "executor_route": EXECUTOR_ROUTE,
        "source_ref": source_ref,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "principal": principal or None,
        "target": dict(TARGET),
        "service_url": SERVICE_URL,
        "model_url": MODEL_URL,
        "provider_authenticated": provider_authenticated,
        "service_http_status": service_status,
        "service_state": service_state,
        "model_http_status": model_status,
        "model_readback": {
            "name": model_name,
            "versionId": model_version,
            "displayName": model_display_name,
            "launchStage": model_launch_stage,
            "supportedActions": model_actions,
        },
        "provider_native_capability_readback_verified": verified,
        "semantic_execution_attempted": False,
        "generate_content_called": False,
        "incremental_cost": 0,
        "silent_fallback": False,
        "provider_mutation_attempted": False,
        "iam_mutation_attempted": False,
        "deployment_attempted": False,
        "traffic_change_attempted": False,
        "secret_payload_accessed": False,
        "credential_value_recorded": False,
        "authority_delta": "NONE",
        "failure_detail": failure,
        "failure_fingerprint": failure_fingerprint,
        "truth_boundary": (
            "Success proves only an authenticated GET-only WIF/ADC read of the enabled Vertex AI service "
            "and the exact publisher model metadata for the Strategic FUSE A0 target. It does not prove "
            "Gemini inference, FSED binding, runtime autonomy, provider mutation, production promotion or COMPLETE_VERIFIED."
        ),
    }
    material["receipt_sha256"] = _digest({k: v for k, v in material.items() if k not in {"recorded_at"}})
    return material


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Strategic FUSE direct WIF Vertex A0 provider read")
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_direct_wif_a0(source_ref=args.source_ref)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "schema": receipt["schema"],
        "state": receipt["state"],
        "provider_authenticated": receipt["provider_authenticated"],
        "service_state": receipt["service_state"],
        "model_http_status": receipt["model_http_status"],
        "receipt_sha256": receipt["receipt_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
