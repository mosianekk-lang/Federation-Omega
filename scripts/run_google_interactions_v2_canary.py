from __future__ import annotations

import hashlib
import json
import os
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


def _http_json(url: str, token: str, payload: dict) -> tuple[int, dict, dict[str, str]]:
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
    status, body, headers = _http_json(endpoint, token, payload)
    latency_ms = round((time.perf_counter() - started) * 1000, 3)

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
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
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
