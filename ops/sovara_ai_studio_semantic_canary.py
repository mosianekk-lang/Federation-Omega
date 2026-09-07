#!/usr/bin/env python3
"""Run the bounded SOVARA AI Studio semantic canary through WIF + Secret Manager."""

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


def make_http_caller(api_key: str) -> HttpCaller:
    def caller(
        url: str, method: str, payload: dict[str, Any] | None = None
    ) -> tuple[int, dict[str, Any], dict[str, str]]:
        data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
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


def execute_semantic_canary(
    request_contract: Mapping[str, Any],
    *,
    env: Mapping[str, str],
    command_runner: CommandRunner = run_command,
    http_caller_factory: Callable[[str], HttpCaller] = make_http_caller,
) -> dict[str, Any]:
    project_id = str(request_contract["project_id"])
    project_number = str(request_contract["project_number"])
    secret_name = str(request_contract["credential_secret_name"])
    base = {
        "schema": "SOVARA_AI_STUDIO_DIRECT_SEMANTIC_RECEIPT_V5",
        "provider": "GOOGLE_GEMINI_DEVELOPER_API",
        "transport": "DIRECT_GENERATIVELANGUAGE_API_AUTH_KEY_VIA_WIF_SECRET_MANAGER",
        "project_id": project_id,
        "project_number": project_number,
        "credential_mode": request_contract["credential_mode"],
        "credential_reference": request_contract["credential_reference"],
        "credential_secret_name": secret_name,
        "resolution_surface": request_contract["resolution_surface"],
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
        "secret_access_attempted": False,
    }

    active_account = command_runner(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
    access_token = command_runner(["gcloud", "auth", "print-access-token"])
    auth_verified = bool(
        active_account.get("ok")
        and str(active_account.get("stdout") or "").strip()
        and access_token.get("ok")
        and str(access_token.get("stdout") or "").strip()
    )
    receipt = {
        **base,
        "wif_identity_verified": auth_verified,
        "active_account": str(active_account.get("stdout") or "").strip() or None,
        "secret_metadata_readable": False,
        "enabled_secret_version_visible": False,
        "credential_present": False,
        "models_list_http_status": None,
        "models_visible_count": 0,
        "selected_model": None,
        "selected_model_source": None,
        "generate_http_status": None,
        "provider_model_version": None,
        "provider_request_id_or_equivalent": None,
        "provider_error_status": None,
        "provider_error_code": None,
        "provider_error_message_sha256": None,
        "nonce_sha256": None,
        "response_text_sha256": None,
        "usage_metadata": {},
    }

    if not auth_verified:
        receipt["state"] = "AUTH_UNAVAILABLE"
        receipt["semantic_verified"] = False
        return _seal_receipt(receipt)

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
    receipt["secret_metadata_readable"] = bool(describe.get("ok"))
    if versions.get("ok"):
        try:
            visible_versions = json.loads(str(versions.get("stdout") or "[]"))
        except Exception:
            visible_versions = []
        receipt["enabled_secret_version_visible"] = isinstance(visible_versions, list) and len(visible_versions) > 0

    access = command_runner(
        ["gcloud", "secrets", "versions", "access", "latest", f"--secret={secret_name}", f"--project={project_id}"]
    )
    receipt["secret_access_attempted"] = True
    api_key = str(access.get("stdout") or "").strip()
    receipt["credential_present"] = bool(access.get("ok") and api_key)
    if not receipt["credential_present"]:
        stderr = str(access.get("stderr") or "").strip()
        receipt["state"] = "CREDENTIAL_PERMISSION_UNAVAILABLE"
        receipt["semantic_verified"] = False
        receipt["secret_access_error_code"] = access.get("code")
        receipt["secret_access_error_sha256"] = _sha256_text(stderr) if stderr else None
        return _seal_receipt(receipt)

    http_caller = http_caller_factory(api_key)
    models: list[dict[str, Any]] = []
    page_token = None
    list_error: dict[str, Any] = {}
    for _ in range(5):
        query = {"pageSize": "1000"}
        if page_token:
            query["pageToken"] = page_token
        status, body, _headers = http_caller(
            "https://generativelanguage.googleapis.com/v1beta/models?" + urllib.parse.urlencode(query),
            "GET",
            None,
        )
        receipt["models_list_http_status"] = status
        if status != 200:
            list_error = (body.get("error") or {}) if isinstance(body, dict) else {}
            break
        models.extend(body.get("models") or [])
        page_token = body.get("nextPageToken")
        if not page_token:
            break

    selected, selected_source, visible_count = select_model(models, request_contract)
    receipt["models_visible_count"] = visible_count
    if selected is not None:
        receipt["selected_model"] = selected["short"]
        receipt["selected_model_source"] = selected_source

    if receipt["models_list_http_status"] != 200 or selected is None:
        error_message = str(list_error.get("message") or "")
        receipt["state"] = "MODEL_DISCOVERY_HELD"
        receipt["semantic_verified"] = False
        receipt["provider_error_status"] = list_error.get("status")
        receipt["provider_error_code"] = list_error.get("code")
        receipt["provider_error_message_sha256"] = _sha256_text(error_message) if error_message else None
        return _seal_receipt(receipt)

    nonce = "SOVARA-AISTUDIO-{run_id}-{run_attempt}-{sha}".format(
        run_id=env.get("GITHUB_RUN_ID", "local"),
        run_attempt=env.get("GITHUB_RUN_ATTEMPT", "0"),
        sha=str(env.get("GITHUB_SHA", ""))[:12],
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"Return exactly this token and nothing else: {nonce}"}],
            }
        ],
        "generationConfig": {
            "temperature": request_contract["semantic_canary"]["temperature"],
            "maxOutputTokens": request_contract["semantic_canary"]["max_output_tokens"],
        },
    }
    status, body, headers = http_caller(
        f"https://generativelanguage.googleapis.com/v1beta/models/{selected['short']}:generateContent",
        "POST",
        payload,
    )
    parts = ((((body.get("candidates") or [{}])[0].get("content") or {}).get("parts")) or []) if isinstance(body, dict) else []
    text = "".join(str(part.get("text", "")) for part in parts).strip()
    error = (body.get("error") or {}) if isinstance(body, dict) else {}
    error_message = str(error.get("message") or "")
    usage = (body.get("usageMetadata") or {}) if isinstance(body, dict) else {}
    request_id = (
        (body.get("responseId") if isinstance(body, dict) else None)
        or (body.get("response_id") if isinstance(body, dict) else None)
        or headers.get("x-request-id")
        or headers.get("x-guploader-uploadid")
    )
    exact = status == 200 and text == nonce
    receipt.update(
        {
            "state": "VERIFIED_SCOPED" if exact else "PROVIDER_SEMANTIC_HELD",
            "semantic_verified": exact,
            "generate_http_status": status,
            "provider_error_status": error.get("status"),
            "provider_error_code": error.get("code"),
            "provider_error_message_sha256": _sha256_text(error_message) if error_message else None,
            "provider_model_version": body.get("modelVersion") if isinstance(body, dict) else None,
            "provider_request_id_or_equivalent": request_id,
            "nonce_sha256": _sha256_text(nonce),
            "response_text_sha256": _sha256_text(text) if text else None,
            "usage_metadata": {
                key: usage.get(key)
                for key in (
                    "promptTokenCount",
                    "candidatesTokenCount",
                    "totalTokenCount",
                    "cachedContentTokenCount",
                )
                if key in usage
            },
        }
    )
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
                    "semantic_verified",
                    "wif_identity_verified",
                    "secret_metadata_readable",
                    "enabled_secret_version_visible",
                    "credential_present",
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
