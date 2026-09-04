"""Authenticated, synthetic, zero-cost SEB OpenRouter proof.

Emits hashes and provider metadata only; never emits the key, prompt, or output.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.request

from seb.engine import SovereignEngine
from seb.ledger import JsonlLedger
from seb.models import Budget, MissionIR, MissionState
from seb.policy import PolicyEngine
from seb.providers import OpenRouterProvider
from seb.router import ProviderRouter


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
    mission = MissionIR(
        mission_id="seb-openrouter-zero-cost-canary",
        objective="Return the exact synthetic structured marker with no external mutation",
        requirements=("exact marker", "zero provider cost", "native generation readback"),
        acceptance_tests=("marker exact",),
        authority_class="A0",
        data_class="public",
        allowed_tools=("openrouter",),
        budget=Budget(money_usd=0, max_tokens=32, time_seconds=120),
    )
    schema = {
        "type": "object",
        "properties": {"marker": {"type": "string", "const": marker}},
        "required": ["marker"],
        "additionalProperties": False,
    }
    with tempfile.TemporaryDirectory() as directory:
        engine = SovereignEngine(
            JsonlLedger(Path(directory) / "events.jsonl"),
            PolicyEngine(max_authority="A2", allow_external_effects=False),
            ProviderRouter([OpenRouterProvider(require_zero_cost=True)]),
        )
        execution = engine.execute(
            mission,
            f'Return JSON {{"marker":"{marker}"}}.',
            schema,
            lambda value: value == {"marker": marker},
            requested_model=model,
        )
        if execution.state != MissionState.COMPLETED or execution.output != {"marker": marker}:
            raise RuntimeError(f"SEB engine did not complete semantic canary: {execution.state}")
        if not engine.ledger.verify():
            raise RuntimeError("SEB ledger verification failed")

    metadata = execution.provider_metadata
    generation_id = metadata.get("generation_id")
    resolved_model = metadata.get("resolved_model")
    provider = metadata.get("downstream_provider")
    if not all(isinstance(v, str) and v.strip() for v in (generation_id, resolved_model, provider)):
        raise RuntimeError("completion metadata is incomplete")
    if metadata.get("cost_usd") != 0:
        raise RuntimeError("SEB engine observed non-zero or missing provider cost")
    content = json.dumps(execution.output, sort_keys=True, separators=(",", ":"))

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
        "execution_path": "SovereignEngine->ProviderRouter->OpenRouterProvider",
        "ledger_verified": True,
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
