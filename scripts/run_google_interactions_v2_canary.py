from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _seal_receipt(receipt: dict, path: Path) -> None:
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _http_json(url: str, token: str, payload: dict) -> tuple[int, object, dict[str, str]]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read().decode("utf-8", "replace")
            return (
                int(response.status),
                json.loads(raw) if raw else {},
                {k.lower(): v for k, v in response.headers.items()},
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            body = {"raw_sha256": _sha256_text(raw)}
        return int(exc.code), body, {k.lower(): v for k, v in exc.headers.items()}



def _normalize_interaction_response(body: object) -> tuple[dict, dict]:
    """Normalize documented and observed Interactions transport shapes.

    Returns (interaction, structural_metadata). Ambiguous list/envelope shapes
    fail closed by returning an empty interaction while preserving only
    non-sensitive structural metadata for diagnostics.
    """
    meta: dict = {
        "top_level_type": type(body).__name__,
        "top_level_length": len(body) if isinstance(body, list) else None,
        "wrapper": None,
    }

    if isinstance(body, dict):
        if isinstance(body.get("interaction"), dict):
            meta["wrapper"] = "interaction"
            return dict(body["interaction"]), meta
        return dict(body), meta

    if isinstance(body, list):
        # Some Vertex transports may return event/envelope lists. Accept only
        # an unambiguous Interaction object or one explicitly nested as
        # {"interaction": {...}}. Never infer completion from arbitrary rows.
        candidates: list[dict] = []
        for row in body:
            if not isinstance(row, dict):
                continue
            nested = row.get("interaction")
            if isinstance(nested, dict):
                candidates.append(dict(nested))
                continue
            if any(k in row for k in ("id", "status", "steps", "model", "usage")):
                candidates.append(dict(row))

        # Prefer a single completed/current Interaction if exactly one is
        # structurally identifiable after de-duplicating by id/body digest.
        unique: dict[str, dict] = {}
        for row in candidates:
            key = str(row.get("id") or hashlib.sha256(
                json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest())
            unique[key] = row

        rows = list(unique.values())
        if len(rows) == 1:
            meta["wrapper"] = "list_single_interaction"
            return rows[0], meta

        completed = [row for row in rows if row.get("status") == "completed" and row.get("id")]
        if len(completed) == 1:
            meta["wrapper"] = "list_completed_interaction"
            return completed[0], meta

        meta["candidate_count"] = len(rows)
        meta["wrapper"] = "ambiguous_list"
        return {}, meta

    meta["wrapper"] = "unsupported"
    return {}, meta


def _extract_provider_error(body: object) -> dict[str, object]:
    rows = body if isinstance(body, list) else [body]
    for row in rows:
        if not isinstance(row, dict):
            continue
        error = row.get("error")
        if not isinstance(error, dict) and any(k in row for k in ("code", "status", "message")):
            error = row
        if not isinstance(error, dict):
            continue
        message = str(error.get("message") or "")
        permissions = sorted(set(re.findall(r"aiplatform\\.[A-Za-z0-9_.]+", message)))
        return {
            "code": error.get("code"),
            "status": error.get("status"),
            "message_sha256": _sha256_text(message) if message else None,
            "permission_refs": permissions,
        }
    return {
        "code": None,
        "status": None,
        "message_sha256": None,
        "permission_refs": [],
    }


def _test_permissions(project: str, token: str) -> tuple[int, tuple[str, ...]]:
    required = (
        "aiplatform.interactions.create",
        "aiplatform.endpoints.predict",
    )
    status, body, _ = _http_json(
        f"https://cloudresourcemanager.googleapis.com/v1/projects/{project}:testIamPermissions",
        token,
        {"permissions": list(required)},
    )
    granted = ()
    if status == 200 and isinstance(body, dict):
        granted = tuple(sorted(str(x) for x in (body.get("permissions") or [])))
    return status, granted

def main() -> int:
    project = os.environ.get("PROJECT_ID", "sov-hybrid-suite")
    project_number = os.environ.get("PROJECT_NUMBER", "257649435135")
    location = os.environ.get("VERTEX_LOCATION", "global")
    model = os.environ.get("INTERACTIONS_MODEL", "gemini-3.8-flash")
    out_dir = Path(os.environ.get("INTERACTIONS_OUT", "/tmp/fuse-google-interactions-v2"))
    out = out_dir / "INTERACTIONS_V2_SEMANTIC_RECEIPT.json"

    token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
    permission_test_http_status, granted_permissions = _test_permissions(project, token)
    required_interaction_permission = "aiplatform.interactions.create"
    interaction_permission_verified = required_interaction_permission in granted_permissions
    nonce = (
        f"FUSE-V2-{os.environ.get('GITHUB_RUN_ID', 'local')}-"
        f"{os.environ.get('GITHUB_RUN_ATTEMPT', '0')}-"
        f"{str(os.environ.get('GITHUB_SHA', ''))[:12]}"
    )
    expected = f"FUSE_INTERACTIONS_V2_VERIFIED:{nonce}"
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Return exactly this text and nothing else: {expected}",
                    }
                ],
            }
        ],
        "store": False,
    }
    endpoint = (
        "https://aiplatform.googleapis.com/v1beta1/projects/"
        f"{project}/locations/{location}/interactions"
    )

    if not interaction_permission_verified:
        receipt = {
            "schema": "FUSE_GOOGLE_INTERACTIONS_V2_PERMISSION_RECEIPT_V1",
            "source_sha": os.environ.get("GITHUB_SHA"),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "project_id": project,
            "project_number": project_number,
            "provider_identity": "GOOGLE_VERTEX_AI",
            "protocol": "VERTEX_AI_INTERACTIONS_REST",
            "requested_model": model,
            "credential_mode": "GITHUB_WIF_ADC",
            "permission_test_http_status": permission_test_http_status,
            "required_interaction_permission": required_interaction_permission,
            "granted_permissions": list(granted_permissions),
            "interaction_permission_verified": False,
            "provider_call_attempted": False,
            "semantic_verified": False,
            "store": False,
            "case_data_processed": False,
            "provider_mutation_performed": False,
            "iam_mutation_performed": False,
            "secret_value_recorded": False,
            "deployment_performed": False,
            "traffic_change_performed": False,
            "external_communication_performed": False,
        }
        _seal_receipt(receipt, out)
        print(json.dumps(receipt, sort_keys=True))
        return 2

    started = time.perf_counter()
    status, raw_body, headers = _http_json(endpoint, token, payload)
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    body, response_shape = _normalize_interaction_response(raw_body)
    provider_error = _extract_provider_error(raw_body)

    texts: list[str] = []
    for step in body.get("steps") or []:
        if step.get("type") != "model_output":
            continue
        for part in step.get("content") or []:
            if part.get("type") == "text":
                texts.append(str(part.get("text") or ""))
    output = "".join(texts).strip()
    interaction_id = body.get("id")
    interaction_status = body.get("status")
    usage = body.get("usage") or {}
    exact = bool(
        status == 200
        and interaction_status == "completed"
        and interaction_id
        and output == expected
    )

    receipt = {
        "schema": "FUSE_GOOGLE_INTERACTIONS_V2_SEMANTIC_RECEIPT_V1",
        "source_sha": os.environ.get("GITHUB_SHA"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "project_id": project,
        "project_number": project_number,
        "provider_identity": "GOOGLE_VERTEX_AI",
        "protocol": "VERTEX_AI_INTERACTIONS_REST",
        "requested_model": model,
        "provider_model_identity_observed": body.get("model"),
        "model_identity": body.get("model") or model,
        "model_identity_source": "PROVIDER_RESPONSE" if body.get("model") else "BOUND_REQUEST",
        "credential_mode": "GITHUB_WIF_ADC",
        "http_status": status,
        "permission_test_http_status": permission_test_http_status,
        "required_interaction_permission": required_interaction_permission,
        "granted_permissions": list(granted_permissions),
        "interaction_permission_verified": interaction_permission_verified,
        "provider_call_attempted": True,
        "provider_error": provider_error,
        "interaction_id": interaction_id,
        "interaction_status": interaction_status,
        "provider_request_id": (
            interaction_id
            or headers.get("x-request-id")
            or headers.get("x-goog-request-id")
        ),
        "semantic_nonce_sha256": _sha256_text(nonce),
        "expected_output_sha256": _sha256_text(expected),
        "response_text_sha256": _sha256_text(output) if output else None,
        "response_digest": hashlib.sha256(
            json.dumps(raw_body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "response_shape": response_shape,
        "semantic_verified": exact,
        "store": False,
        "usage": {
            "total_tokens": usage.get("total_tokens"),
            "total_input_tokens": usage.get("total_input_tokens"),
            "total_output_tokens": usage.get("total_output_tokens"),
        },
        "latency_ms": latency_ms,
        "case_data_processed": False,
        "provider_mutation_performed": False,
        "iam_mutation_performed": False,
        "secret_value_recorded": False,
        "deployment_performed": False,
        "traffic_change_performed": False,
        "external_communication_performed": False,
    }
    _seal_receipt(receipt, out)
    if not exact:
        print(json.dumps(receipt, sort_keys=True))
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
