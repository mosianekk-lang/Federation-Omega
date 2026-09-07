#!/usr/bin/env python3
"""Run the bounded SOVARA Gemini semantic canary through preferred Vertex and fallback AI Studio routes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping


CommandRunner = Callable[[list[str]], dict[str, Any]]
HttpCaller = Callable[[str, str, dict[str, Any] | None], tuple[int, dict[str, Any], dict[str, str]]]


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _seal_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return receipt


def run_command(args: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(args, text=True, capture_output=True)
    except OSError as exc:
        return {
            "ok": False,
            "code": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
        }
    return {
        "ok": result.returncode == 0,
        "code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def make_http_caller(headers: Mapping[str, str]) -> HttpCaller:
    def caller(
        url: str, method: str, payload: dict[str, Any] | None = None
    ) -> tuple[int, dict[str, Any], dict[str, str]]:
        data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        request = urllib.request.Request(
            url,
            data=data,
            headers=dict(headers),
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode("utf-8", "replace")
                body = json.loads(raw) if raw else {}
                return int(response.status), body, {k.lower(): v for k, v in response.headers.items()}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                body = json.loads(raw) if raw else {}
            except Exception:
                body = {"raw_sha256": _sha256_text(raw)}
            return int(exc.code), body, {k.lower(): v for k, v in exc.headers.items()}

    return caller


def make_api_key_http_caller(api_key: str) -> HttpCaller:
    return make_http_caller({"Content-Type": "application/json", "x-goog-api-key": api_key})


def make_bearer_http_caller(access_token: str) -> HttpCaller:
    return make_http_caller({"Content-Type": "application/json", "Authorization": "Bearer " + access_token})


def select_model(
    models: list[dict[str, Any]], request_contract: Mapping[str, Any]
) -> tuple[dict[str, Any] | None, str | None, int]:
    rejected_terms = tuple(
        str(value).lower() for value in request_contract["model_policy"].get("reject_model_classes") or []
    )
    available: list[dict[str, Any]] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        short = name.split("/", 1)[-1]
        methods = set(item.get("supportedGenerationMethods") or [])
        if not name.startswith("models/gemini-") or "generateContent" not in methods:
            continue
        if any(term in short.lower() for term in rejected_terms):
            continue
        available.append(
            {
                "name": name,
                "short": short,
                "display_name": item.get("displayName"),
                "methods": sorted(methods),
            }
        )

    preferred = [str(value) for value in request_contract["model_policy"].get("preferred_models") or []]
    available_by_short = {item["short"]: item for item in available}
    for candidate in preferred:
        if candidate in available_by_short:
            return available_by_short[candidate], "PREFERRED_PROVIDER_DISCOVERED", len(available)

    def version_score(short: str) -> tuple[int, int, tuple[int, ...], int, str]:
        numbers = tuple(int(value) for value in re.findall(r"\d+", short)[:3])
        stable_bonus = 0 if any(tag in short.lower() for tag in ("preview", "exp", "experimental")) else 1
        flash_bonus = 1 if "-flash" in short else 0
        latest_bonus = 1 if short.endswith("-latest") else 0
        return (stable_bonus, flash_bonus, numbers, latest_bonus, short)

    if available and request_contract["model_policy"].get("allow_dynamic_fallback"):
        return max(available, key=lambda item: version_score(item["short"])), "DYNAMIC_PROVIDER_DISCOVERY", len(available)

    return None, None, len(available)


def _provider_request_id(body: Mapping[str, Any], headers: Mapping[str, str]) -> str | None:
    return (
        body.get("responseId")
        or body.get("response_id")
        or headers.get("x-request-id")
        or headers.get("x-guploader-uploadid")
    )


def _route_receipt(
    *,
    route: str,
    provider: str,
    transport: str,
    credential_mode: str,
    credential_reference: str,
) -> dict[str, Any]:
    return {
        "route": route,
        "provider": provider,
        "transport": transport,
        "credential_mode": credential_mode,
        "credential_reference": credential_reference,
        "attempted": False,
        "semantic_request_performed": False,
        "semantic_verified": False,
        "provider_mutation_performed": False,
        "case_data_processed": False,
        "secret_value_recorded": False,
        "credential_value_recorded": False,
        "credential_value_hashed": False,
        "selected_model": None,
        "selected_model_source": None,
        "provider_model_version": None,
        "provider_request_id_or_equivalent": None,
        "provider_error_status": None,
        "provider_error_code": None,
        "provider_error_message_sha256": None,
        "generate_http_status": None,
        "nonce_sha256": None,
        "response_text_sha256": None,
        "usage_metadata": {},
    }


def _vertex_model_url(project_id: str, location: str, model: str, suffix: str = "") -> str:
    base = "https://aiplatform.googleapis.com" if location == "global" else f"https://{urllib.parse.quote(location)}-aiplatform.googleapis.com"
    return (
        f"{base}/v1/projects/{urllib.parse.quote(project_id)}/locations/{urllib.parse.quote(location)}"
        f"/publishers/google/models/{urllib.parse.quote(model)}{suffix}"
    )


def _extract_text(body: Mapping[str, Any]) -> str:
    parts = ((((body.get("candidates") or [{}])[0].get("content") or {}).get("parts")) or [])
    return "".join(str(part.get("text", "")) for part in parts).strip()


def _copy_selected_route(receipt: dict[str, Any], route_key: str, route_result: Mapping[str, Any]) -> dict[str, Any]:
    receipt.update(
        {
            "selected_route": route_key,
            "state": route_result.get("state"),
            "semantic_verified": route_result.get("semantic_verified", False),
            "selected_model": route_result.get("selected_model"),
            "selected_model_source": route_result.get("selected_model_source"),
            "provider_model_version": route_result.get("provider_model_version"),
            "provider_request_id_or_equivalent": route_result.get("provider_request_id_or_equivalent"),
            "provider_error_status": route_result.get("provider_error_status"),
            "provider_error_code": route_result.get("provider_error_code"),
            "provider_error_message_sha256": route_result.get("provider_error_message_sha256"),
            "generate_http_status": route_result.get("generate_http_status"),
            "nonce_sha256": route_result.get("nonce_sha256"),
            "response_text_sha256": route_result.get("response_text_sha256"),
            "usage_metadata": route_result.get("usage_metadata") or {},
        }
    )
    return receipt


def run_vertex_oauth_challenger(
    request_contract: Mapping[str, Any],
    *,
    env: Mapping[str, str],
    access_token: str,
    http_caller_factory: Callable[[str], HttpCaller] = make_bearer_http_caller,
) -> dict[str, Any]:
    config = request_contract.get("vertex_oauth_challenger") or {}
    project_id = str(request_contract["project_id"])
    location = str(config.get("location") or "global")
    route = _route_receipt(
        route="VERTEX_OAUTH_ADC",
        provider="GOOGLE_VERTEX_AI_GEMINI",
        transport="VERTEX_PUBLISHER_MODEL_OAUTH",
        credential_mode=str(config.get("credential_mode") or "GOOGLE_WIF_OAUTH_ACCESS_TOKEN"),
        credential_reference="gcloud:auth:print-access-token",
    )
    route["attempted"] = True
    route["provider_mutation_performed"] = False
    route["service_state"] = None
    route["service_usage_permissions_checked"] = list(config.get("service_usage_permissions_required") or [])
    route["service_usage_permissions_granted"] = []
    route["service_usage_missing_permissions"] = []
    route["vertex_permissions_checked"] = list(config.get("vertex_permissions_required") or [])
    route["vertex_permissions_granted"] = []
    route["vertex_missing_permissions"] = []
    route["candidate_models_tested"] = []

    if not access_token:
        route["state"] = "AUTH_UNAVAILABLE"
        return route

    http = http_caller_factory(access_token)
    service_url = f"https://serviceusage.googleapis.com/v1/projects/{urllib.parse.quote(project_id)}/services/aiplatform.googleapis.com"
    status, body, _headers = http(
        f"{service_url}:testIamPermissions",
        "POST",
        {"permissions": route["service_usage_permissions_checked"]},
    )
    if status != 200:
        error = (body.get("error") or {}) if isinstance(body, dict) else {}
        message = str(error.get("message") or "")
        route["state"] = "VERTEX_SERVICEUSAGE_PERMISSION_HELD"
        route["provider_error_status"] = error.get("status")
        route["provider_error_code"] = error.get("code")
        route["provider_error_message_sha256"] = _sha256_text(message) if message else None
        return route

    granted_service = [str(value) for value in (body.get("permissions") or [])]
    route["service_usage_permissions_granted"] = granted_service
    route["service_usage_missing_permissions"] = [
        permission for permission in route["service_usage_permissions_checked"] if permission not in granted_service
    ]
    if route["service_usage_missing_permissions"]:
        route["state"] = "VERTEX_SERVICEUSAGE_PERMISSION_HELD"
        return route

    status, body, _headers = http(service_url, "GET", None)
    route["service_state"] = body.get("state") if isinstance(body, dict) else None
    if status != 200:
        error = (body.get("error") or {}) if isinstance(body, dict) else {}
        message = str(error.get("message") or "")
        route["state"] = "VERTEX_SERVICE_READ_HELD"
        route["provider_error_status"] = error.get("status")
        route["provider_error_code"] = error.get("code")
        route["provider_error_message_sha256"] = _sha256_text(message) if message else None
        return route
    if route["service_state"] != "ENABLED":
        route["state"] = "VERTEX_API_DISABLED"
        return route

    selected_body: dict[str, Any] | None = None
    selected_model: str | None = None
    for candidate in config.get("preferred_models") or []:
        candidate = str(candidate)
        route["candidate_models_tested"].append(candidate)
        perm_url = _vertex_model_url(project_id, location, candidate, ":testIamPermissions")
        status, body, _headers = http(perm_url, "POST", {"permissions": route["vertex_permissions_checked"]})
        route["selected_model"] = candidate
        if status != 200:
            error = (body.get("error") or {}) if isinstance(body, dict) else {}
            message = str(error.get("message") or "")
            route["state"] = "VERTEX_PERMISSION_HELD"
            route["provider_error_status"] = error.get("status")
            route["provider_error_code"] = error.get("code")
            route["provider_error_message_sha256"] = _sha256_text(message) if message else None
            return route
        granted_vertex = [str(value) for value in (body.get("permissions") or [])]
        route["vertex_permissions_granted"] = granted_vertex
        route["vertex_missing_permissions"] = [
            permission for permission in route["vertex_permissions_checked"] if permission not in granted_vertex
        ]
        if route["vertex_missing_permissions"]:
            route["state"] = "VERTEX_PERMISSION_HELD"
            return route

        status, body, _headers = http(_vertex_model_url(project_id, location, candidate), "GET", None)
        if status != 200:
            error = (body.get("error") or {}) if isinstance(body, dict) else {}
            message = str(error.get("message") or "")
            route["provider_error_status"] = error.get("status")
            route["provider_error_code"] = error.get("code")
            route["provider_error_message_sha256"] = _sha256_text(message) if message else None
            continue

        supported_actions = [str(value) for value in (body.get("supportedActions") or [])]
        if "generateContent" not in supported_actions:
            continue

        selected_model = candidate
        selected_body = body
        route["selected_model_source"] = "PREFERRED_VERTEX_MODEL_READBACK"
        route["vertex_model_readback"] = {
            "name": body.get("name"),
            "versionId": body.get("versionId"),
            "displayName": body.get("displayName"),
            "launchStage": body.get("launchStage"),
            "supportedActions": supported_actions,
        }
        break

    if selected_model is None or selected_body is None:
        route["state"] = "VERTEX_MODEL_DISCOVERY_HELD"
        return route

    nonce = "SOVARA-VERTEX-{run_id}-{run_attempt}-{sha}".format(
        run_id=env.get("GITHUB_RUN_ID", "local"),
        run_attempt=env.get("GITHUB_RUN_ATTEMPT", "0"),
        sha=str(env.get("GITHUB_SHA", ""))[:12],
    )
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": f"Return exactly this token and nothing else: {nonce}"}]}
        ],
        "generationConfig": {
            "candidateCount": 1,
            "temperature": request_contract["semantic_canary"]["temperature"],
            "maxOutputTokens": request_contract["semantic_canary"]["max_output_tokens"],
        },
    }
    status, body, headers = http(_vertex_model_url(project_id, location, selected_model, ":generateContent"), "POST", payload)
    text = _extract_text(body if isinstance(body, dict) else {})
    error = (body.get("error") or {}) if isinstance(body, dict) else {}
    message = str(error.get("message") or "")
    usage = (body.get("usageMetadata") or {}) if isinstance(body, dict) else {}
    route["semantic_request_performed"] = True
    route["generate_http_status"] = status
    route["provider_error_status"] = error.get("status")
    route["provider_error_code"] = error.get("code")
    route["provider_error_message_sha256"] = _sha256_text(message) if message else None
    route["provider_model_version"] = (
        body.get("modelVersion") if isinstance(body, dict) else None
    ) or route.get("vertex_model_readback", {}).get("versionId")
    route["provider_request_id_or_equivalent"] = _provider_request_id(body if isinstance(body, dict) else {}, headers)
    route["nonce_sha256"] = _sha256_text(nonce)
    route["response_text_sha256"] = _sha256_text(text) if text else None
    route["usage_metadata"] = {
        key: usage.get(key)
        for key in ("promptTokenCount", "candidatesTokenCount", "totalTokenCount", "cachedContentTokenCount")
        if key in usage
    }
    route["semantic_verified"] = status == 200 and text == nonce
    route["state"] = "VERIFIED_SCOPED" if route["semantic_verified"] else "PROVIDER_SEMANTIC_HELD"
    return route


def run_developer_api_secret_manager_fallback(
    request_contract: Mapping[str, Any],
    *,
    env: Mapping[str, str],
    project_id: str,
    command_runner: CommandRunner = run_command,
    http_caller_factory: Callable[[str], HttpCaller] = make_api_key_http_caller,
) -> dict[str, Any]:
    config = request_contract.get("developer_api_secret_manager_fallback") or {}
    secret_name = str(config.get("credential_secret_name") or request_contract["credential_secret_name"])
    route = _route_receipt(
        route="DEVELOPER_API_SECRET_MANAGER",
        provider="GOOGLE_GEMINI_DEVELOPER_API",
        transport="DIRECT_GENERATIVELANGUAGE_API_AUTH_KEY_VIA_WIF_SECRET_MANAGER",
        credential_mode=str(config.get("credential_mode") or request_contract["credential_mode"]),
        credential_reference=str(config.get("credential_reference") or request_contract["credential_reference"]),
    )
    route["attempted"] = True
    route["credential_secret_name"] = secret_name
    route["secret_metadata_readable"] = False
    route["enabled_secret_version_visible"] = False
    route["secret_access_attempted"] = False
    route["credential_present"] = False
    route["models_list_http_status"] = None
    route["models_visible_count"] = 0

    describe = command_runner(
        ["gcloud", "secrets", "describe", secret_name, "--project", project_id, "--format=json(name,createTime,replication)"]
    )
    versions = command_runner(
        [
            "gcloud",
            "secrets",
            "versions",
            "list",
            secret_name,
            "--project",
            project_id,
            "--filter=state=ENABLED",
            "--limit=1",
            "--format=json(name,state,createTime)",
        ]
    )
    route["secret_metadata_readable"] = bool(describe.get("ok"))
    if versions.get("ok"):
        try:
            visible_versions = json.loads(str(versions.get("stdout") or "[]"))
        except Exception:
            visible_versions = []
        route["enabled_secret_version_visible"] = isinstance(visible_versions, list) and len(visible_versions) > 0

    access = command_runner(
        ["gcloud", "secrets", "versions", "access", "latest", f"--secret={secret_name}", f"--project={project_id}"]
    )
    route["secret_access_attempted"] = True
    api_key = str(access.get("stdout") or "").strip()
    route["credential_present"] = bool(access.get("ok") and api_key)
    if not route["credential_present"]:
        stderr = str(access.get("stderr") or "").strip()
        route["state"] = "CREDENTIAL_PERMISSION_UNAVAILABLE"
        route["secret_access_error_code"] = access.get("code")
        route["secret_access_error_sha256"] = _sha256_text(stderr) if stderr else None
        return route

    http = http_caller_factory(api_key)
    models: list[dict[str, Any]] = []
    page_token = None
    list_error: dict[str, Any] = {}
    for _ in range(5):
        query = {"pageSize": "1000"}
        if page_token:
            query["pageToken"] = page_token
        status, body, _headers = http(
            "https://generativelanguage.googleapis.com/v1beta/models?" + urllib.parse.urlencode(query),
            "GET",
            None,
        )
        route["models_list_http_status"] = status
        if status != 200:
            list_error = (body.get("error") or {}) if isinstance(body, dict) else {}
            break
        models.extend(body.get("models") or [])
        page_token = body.get("nextPageToken")
        if not page_token:
            break

    selected, selected_source, visible_count = select_model(models, request_contract)
    route["models_visible_count"] = visible_count
    if selected is not None:
        route["selected_model"] = selected["short"]
        route["selected_model_source"] = selected_source

    if route["models_list_http_status"] != 200 or selected is None:
        message = str(list_error.get("message") or "")
        route["state"] = "MODEL_DISCOVERY_HELD"
        route["provider_error_status"] = list_error.get("status")
        route["provider_error_code"] = list_error.get("code")
        route["provider_error_message_sha256"] = _sha256_text(message) if message else None
        return route

    nonce = "SOVARA-AISTUDIO-{run_id}-{run_attempt}-{sha}".format(
        run_id=env.get("GITHUB_RUN_ID", "local"),
        run_attempt=env.get("GITHUB_RUN_ATTEMPT", "0"),
        sha=str(env.get("GITHUB_SHA", ""))[:12],
    )
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": f"Return exactly this token and nothing else: {nonce}"}]}
        ],
        "generationConfig": {
            "temperature": request_contract["semantic_canary"]["temperature"],
            "maxOutputTokens": request_contract["semantic_canary"]["max_output_tokens"],
        },
    }
    status, body, headers = http(
        f"https://generativelanguage.googleapis.com/v1beta/models/{selected['short']}:generateContent",
        "POST",
        payload,
    )
    text = _extract_text(body if isinstance(body, dict) else {})
    error = (body.get("error") or {}) if isinstance(body, dict) else {}
    message = str(error.get("message") or "")
    usage = (body.get("usageMetadata") or {}) if isinstance(body, dict) else {}
    route["semantic_request_performed"] = True
    route["generate_http_status"] = status
    route["provider_error_status"] = error.get("status")
    route["provider_error_code"] = error.get("code")
    route["provider_error_message_sha256"] = _sha256_text(message) if message else None
    route["provider_model_version"] = body.get("modelVersion") if isinstance(body, dict) else None
    route["provider_request_id_or_equivalent"] = _provider_request_id(body if isinstance(body, dict) else {}, headers)
    route["nonce_sha256"] = _sha256_text(nonce)
    route["response_text_sha256"] = _sha256_text(text) if text else None
    route["usage_metadata"] = {
        key: usage.get(key)
        for key in ("promptTokenCount", "candidatesTokenCount", "totalTokenCount", "cachedContentTokenCount")
        if key in usage
    }
    route["semantic_verified"] = status == 200 and text == nonce
    route["state"] = "VERIFIED_SCOPED" if route["semantic_verified"] else "PROVIDER_SEMANTIC_HELD"
    return route


def execute_semantic_canary(
    request_contract: Mapping[str, Any],
    *,
    env: Mapping[str, str],
    command_runner: CommandRunner = run_command,
    api_key_http_caller_factory: Callable[[str], HttpCaller] = make_api_key_http_caller,
    bearer_http_caller_factory: Callable[[str], HttpCaller] = make_bearer_http_caller,
) -> dict[str, Any]:
    project_id = str(request_contract["project_id"])
    project_number = str(request_contract["project_number"])
    base = {
        "schema": "SOVARA_AI_STUDIO_DIRECT_SEMANTIC_RECEIPT_V6",
        "provider": "GOOGLE_GEMINI_MULTI_ROUTE_CANARY",
        "transport": "VERTEX_OAUTH_ADC_THEN_DEVELOPER_API_SECRET_MANAGER_FALLBACK",
        "project_id": project_id,
        "project_number": project_number,
        "source_sha": env.get("GITHUB_SHA"),
        "run_id": env.get("GITHUB_RUN_ID"),
        "run_attempt": env.get("GITHUB_RUN_ATTEMPT"),
        "wif_provider": request_contract.get("workload_identity_provider"),
        "service_account": request_contract.get("service_account"),
        "credential_value_recorded": False,
        "credential_value_hashed": False,
        "secret_value_recorded": False,
        "case_data_processed": False,
        "provider_mutation_performed": False,
        "iam_mutation_performed": False,
        "secret_mutation_performed": False,
        "deployment_performed": False,
        "traffic_change_performed": False,
        "selected_route": None,
        "selected_model": None,
        "selected_model_source": None,
        "provider_model_version": None,
        "provider_request_id_or_equivalent": None,
        "provider_error_status": None,
        "provider_error_code": None,
        "provider_error_message_sha256": None,
        "generate_http_status": None,
        "nonce_sha256": None,
        "response_text_sha256": None,
        "usage_metadata": {},
    }

    active_account = command_runner(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
    access_token = command_runner(["gcloud", "auth", "print-access-token"])
    access_token_value = str(access_token.get("stdout") or "").strip()
    auth_verified = bool(
        active_account.get("ok")
        and str(active_account.get("stdout") or "").strip()
        and access_token.get("ok")
        and access_token_value
    )
    receipt = {
        **base,
        "wif_identity_verified": auth_verified,
        "active_account": str(active_account.get("stdout") or "").strip() or None,
        "semantic_verified": False,
    }

    if not auth_verified:
        receipt["state"] = "AUTH_UNAVAILABLE"
        receipt["vertex_oauth_adc_challenger"] = _route_receipt(
            route="VERTEX_OAUTH_ADC",
            provider="GOOGLE_VERTEX_AI_GEMINI",
            transport="VERTEX_PUBLISHER_MODEL_OAUTH",
            credential_mode="GOOGLE_WIF_OAUTH_ACCESS_TOKEN",
            credential_reference="gcloud:auth:print-access-token",
        )
        receipt["vertex_oauth_adc_challenger"]["state"] = "AUTH_UNAVAILABLE"
        receipt["developer_api_secret_manager_fallback"] = _route_receipt(
            route="DEVELOPER_API_SECRET_MANAGER",
            provider="GOOGLE_GEMINI_DEVELOPER_API",
            transport="DIRECT_GENERATIVELANGUAGE_API_AUTH_KEY_VIA_WIF_SECRET_MANAGER",
            credential_mode=str(request_contract["credential_mode"]),
            credential_reference=str(request_contract["credential_reference"]),
        )
        receipt["developer_api_secret_manager_fallback"]["state"] = "SKIPPED_AUTH_UNAVAILABLE"
        return _seal_receipt(receipt)

    vertex = run_vertex_oauth_challenger(
        request_contract,
        env=env,
        access_token=access_token_value,
        http_caller_factory=bearer_http_caller_factory,
    )
    receipt["vertex_oauth_adc_challenger"] = vertex
    if vertex.get("semantic_verified"):
        receipt["developer_api_secret_manager_fallback"] = _route_receipt(
            route="DEVELOPER_API_SECRET_MANAGER",
            provider="GOOGLE_GEMINI_DEVELOPER_API",
            transport="DIRECT_GENERATIVELANGUAGE_API_AUTH_KEY_VIA_WIF_SECRET_MANAGER",
            credential_mode=str(request_contract["credential_mode"]),
            credential_reference=str(request_contract["credential_reference"]),
        )
        receipt["developer_api_secret_manager_fallback"]["state"] = "SKIPPED_PREFERRED_ROUTE_VERIFIED"
        return _seal_receipt(_copy_selected_route(receipt, "VERTEX_OAUTH_ADC", vertex))

    if vertex.get("semantic_request_performed"):
        receipt["developer_api_secret_manager_fallback"] = _route_receipt(
            route="DEVELOPER_API_SECRET_MANAGER",
            provider="GOOGLE_GEMINI_DEVELOPER_API",
            transport="DIRECT_GENERATIVELANGUAGE_API_AUTH_KEY_VIA_WIF_SECRET_MANAGER",
            credential_mode=str(request_contract["credential_mode"]),
            credential_reference=str(request_contract["credential_reference"]),
        )
        receipt["developer_api_secret_manager_fallback"]["state"] = "SKIPPED_VERTEX_ROUTE_ATTEMPTED"
        return _seal_receipt(_copy_selected_route(receipt, "VERTEX_OAUTH_ADC", vertex))

    developer = run_developer_api_secret_manager_fallback(
        request_contract,
        env=env,
        project_id=project_id,
        command_runner=command_runner,
        http_caller_factory=api_key_http_caller_factory,
    )
    receipt["developer_api_secret_manager_fallback"] = developer
    if developer.get("semantic_verified"):
        return _seal_receipt(_copy_selected_route(receipt, "DEVELOPER_API_SECRET_MANAGER", developer))

    receipt["state"] = developer.get("state") or vertex.get("state") or "NO_ROUTE_VERIFIED"
    if receipt["state"] == "SKIPPED_PREFERRED_ROUTE_VERIFIED":
        receipt["state"] = vertex.get("state") or "NO_ROUTE_VERIFIED"
    if developer.get("attempted"):
        receipt["selected_route"] = "DEVELOPER_API_SECRET_MANAGER"
    else:
        receipt["selected_route"] = "VERTEX_OAUTH_ADC"
    return _seal_receipt(receipt)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args(argv)

    request_contract = json.loads(Path(args.request).read_text(encoding="utf-8"))
    receipt = execute_semantic_canary(request_contract, env=os.environ)
    Path(args.receipt).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: receipt[key]
                for key in (
                    "state",
                    "selected_route",
                    "semantic_verified",
                    "wif_identity_verified",
                    "selected_model",
                    "selected_model_source",
                    "generate_http_status",
                    "provider_model_version",
                    "provider_request_id_or_equivalent",
                    "receipt_sha256",
                )
            },
            sort_keys=True,
        )
    )
    return 0 if receipt["state"] == "VERIFIED_SCOPED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
