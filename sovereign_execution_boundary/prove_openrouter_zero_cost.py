"""Authenticated, synthetic, zero-cost SEB OpenRouter proof.

Emits hashes and provider metadata only; never emits the key, prompt, or output.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
import urllib.request


BASE = "https://openrouter.ai/api/v1"


def _call(key: str, method: str, path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as response:
        if response.status != 200:
            raise RuntimeError(f"unexpected OpenRouter HTTP status {response.status}")
        value = json.loads(response.read())
    if not isinstance(value, dict):
        raise RuntimeError("OpenRouter response is not an object")
    return value


def _decimal(value: object, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RuntimeError(f"{label} is missing or invalid") from exc
    if not result.is_finite() or result < 0:
        raise RuntimeError(f"{label} is invalid")
    return result


def run() -> dict:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("SEB_OPENROUTER_MODEL", "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not bound")
    if not model or not (model == "openrouter/free" or model.endswith(":free")):
        raise RuntimeError("SEB_OPENROUTER_MODEL must explicitly select a free route")

    before = (_call(key, "GET", "/key").get("data") or {})
    before_usage = _decimal(before.get("usage"), "pre-key usage")
    marker = "SEB_OPENROUTER_ZERO_COST_OK"
    response = _call(key, "POST", "/chat/completions", {
        "model": model,
        "messages": [{"role": "user", "content": f'Return JSON {{"marker":"{marker}"}}.'}],
        "response_format": {"type": "json_object"},
        "max_tokens": 32,
        "temperature": 0,
    })
    generation_id = response.get("id")
    resolved_model = response.get("model")
    provider = response.get("provider")
    if not all(isinstance(v, str) and v.strip() for v in (generation_id, resolved_model, provider)):
        raise RuntimeError("completion metadata is incomplete")
    content = (((response.get("choices") or [{}])[0].get("message") or {}).get("content"))
    try:
        semantic = json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("completion is not JSON") from exc
    if semantic != {"marker": marker}:
        raise RuntimeError("semantic marker mismatch")

    generation = (_call(key, "GET", "/generation?id=" + generation_id).get("data") or {})
    if generation.get("id", generation_id) != generation_id:
        raise RuntimeError("generation readback identity mismatch")
    generation_cost = _decimal(generation.get("total_cost", generation.get("usage")), "generation cost")
    after = (_call(key, "GET", "/key").get("data") or {})
    after_usage = _decimal(after.get("usage"), "post-key usage")
    if generation_cost != 0 or after_usage != before_usage:
        raise RuntimeError("zero-cost invariant failed")

    return {
        "schema": "SEB_OPENROUTER_ZERO_COST_PROOF_V1",
        "state": "AUTHENTICATED_ZERO_COST_SEMANTIC_VERIFIED",
        "requested_model": model,
        "resolved_model": resolved_model,
        "downstream_provider": provider,
        "generation_id_sha256": hashlib.sha256(generation_id.encode()).hexdigest(),
        "output_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "generation_cost_usd": "0",
        "key_usage_delta_usd": "0",
        "secret_exposed": False,
        "synthetic_public_data_only": True,
        "external_mutation": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, separators=(",", ":")))
