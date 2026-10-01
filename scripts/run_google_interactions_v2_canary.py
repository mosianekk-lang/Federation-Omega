from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


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


def _http_json(url: str, token: str, payload: dict) -> tuple[int, Any, dict[str, str]]:
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


def _event_text(row: dict[str, Any]) -> str | None:
    delta = row.get("delta")
    if isinstance(delta, dict) and delta.get("type") == "text":
        return str(delta.get("text") or "")
    return None


def _normalize_interaction_response(body: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Normalize only provider shapes that can be verified without guessing.

    Google documents a synchronous Interaction object. A bounded list is
    accepted only when it is either a singleton Interaction object or a
    recognizable sequence of Interaction SSE-style event objects from which
    terminal interaction identity and model text can be reconstructed.
    """
    shape: dict[str, Any] = {
        "top_level_type": type(body).__name__,
        "normalization": "UNSUPPORTED",
        "list_length": len(body) if isinstance(body, list) else None,
        "event_types": [],
        "dict_element_count": 0,
    }
    if isinstance(body, dict):
        shape["normalization"] = "DIRECT_INTERACTION_OBJECT"
        return dict(body), shape

    if not isinstance(body, list):
        return {}, shape

    rows = [row for row in body if isinstance(row, dict)]
    shape["dict_element_count"] = len(rows)
    shape["event_types"] = sorted(
        {
            str(row.get("event_type"))
            for row in rows
            if row.get("event_type")
        }
    )

    if len(body) == 1 and len(rows) == 1:
        row = rows[0]
        if row.get("id") and row.get("status"):
            shape["normalization"] = "SINGLETON_INTERACTION_LIST"
            return dict(row), shape

    direct = [
        row
        for row in rows
        if row.get("id") and row.get("status") and isinstance(row.get("steps"), list)
    ]
    if len(direct) == 1:
        shape["normalization"] = "DIRECT_INTERACTION_IN_EVENT_LIST"
        return dict(direct[0]), shape

    interaction: dict[str, Any] = {}
    text_chunks: list[str] = []
    for row in rows:
        nested = row.get("interaction")
        if isinstance(nested, dict):
            for key in ("id", "status", "model", "usage", "created", "updated", "object"):
                if nested.get(key) is not None:
                    interaction[key] = nested.get(key)
            if isinstance(nested.get("steps"), list):
                interaction["steps"] = nested.get("steps")

        event_type = str(row.get("event_type") or "")
        if event_type == "interaction.status_update" and row.get("status"):
            interaction["status"] = row.get("status")
        chunk = _event_text(row)
        if event_type == "step.delta" and chunk is not None:
            text_chunks.append(chunk)

    if interaction.get("id") and interaction.get("status"):
        if text_chunks and not isinstance(interaction.get("steps"), list):
            interaction["steps"] = [
                {
                    "type": "model_output",
                    "content": [{"type": "text", "text": "".join(text_chunks)}],
                }
            ]
        shape["normalization"] = "INTERACTION_EVENT_LIST"
        return interaction, shape

    return {}, shape


def _extract_output(interaction: dict[str, Any]) -> str:
    texts: list[str] = []
    steps = interaction.get("steps")
    if not isinstance(steps, list):
        return ""
    for step in steps:
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        content = step.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(str(part.get("text") or ""))
    return "".join(texts).strip()


def main() -> int:
    project = os.environ.get("PROJECT_ID", "sov-hybrid-suite")
    project_number = os.environ.get("PROJECT_NUMBER", "257649435135")
    location = os.environ.get("VERTEX_LOCATION", "global")
    model = os.environ.get("INTERACTIONS_MODEL", "gemini-3.8-flash")
    out_dir = Path(os.environ.get("INTERACTIONS_OUT", "/tmp/fuse-google-interactions-v2"))
    out = out_dir / "INTERACTIONS_V2_SEMANTIC_RECEIPT.json"

    token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
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

    started = time.perf_counter()
    status, raw_body, headers = _http_json(endpoint, token, payload)
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    interaction, response_shape = _normalize_interaction_response(raw_body)
    output = _extract_output(interaction)
    interaction_id = interaction.get("id")
    interaction_status = interaction.get("status")
    usage = interaction.get("usage") if isinstance(interaction.get("usage"), dict) else {}
    exact = bool(
        status == 200
        and interaction_status == "completed"
        and interaction_id
        and output == expected
    )

    provider_model = interaction.get("model")
    receipt = {
        "schema": "FUSE_GOOGLE_INTERACTIONS_V2_SEMANTIC_RECEIPT_V2",
        "source_sha": os.environ.get("GITHUB_SHA"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "project_id": project,
        "project_number": project_number,
        "provider_identity": "GOOGLE_VERTEX_AI",
        "protocol": "VERTEX_AI_INTERACTIONS_REST",
        "requested_model": model,
        "provider_model_identity_observed": provider_model,
        "model_identity": provider_model or model,
        "model_identity_source": "PROVIDER_RESPONSE" if provider_model else "BOUND_REQUEST",
        "credential_mode": "GITHUB_WIF_ADC",
        "http_status": status,
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
    print(json.dumps(receipt, sort_keys=True))
    return 0 if exact else 1


if __name__ == "__main__":
    raise SystemExit(main())
