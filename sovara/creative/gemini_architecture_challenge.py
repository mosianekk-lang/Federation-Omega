from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-3.1-pro-preview"
MAX_OUTPUT_TOKENS_CEILING = 6000


@dataclass(frozen=True, slots=True)
class ChallengeSpec:
    challenge_id: str
    model: str
    proposal_count: int
    max_output_tokens: int
    temperature: float
    system_prompt: str
    user_prompt: str
    sanitized: bool
    case_data_allowed: bool
    external_effect_allowed: bool


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: str | bytes) -> str:
    raw = value if isinstance(value, bytes) else value.encode("utf-8")
    return sha256(raw).hexdigest()


def load_spec(path: str | Path) -> ChallengeSpec:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != "SOVARA_CREATIVE_GEMINI_ARCHITECTURE_CHALLENGE_V1":
        raise ValueError("unexpected challenge schema")

    challenge_id = str(payload.get("challenge_id", "")).strip()
    model = str(payload.get("model", "")).strip()
    proposal_count = int(payload.get("proposal_count", 0))
    max_output_tokens = int(payload.get("max_output_tokens", 0))
    temperature = float(payload.get("temperature", 0.0))
    system_prompt = str(payload.get("system_prompt", "")).strip()
    user_prompt = str(payload.get("user_prompt", "")).strip()
    sanitized = payload.get("sanitized") is True
    case_data_allowed = payload.get("case_data_allowed") is True
    external_effect_allowed = payload.get("external_effect_allowed") is True

    if not challenge_id:
        raise ValueError("challenge_id is required")
    if not model.startswith("google/gemini-"):
        raise ValueError("G2 challenge must use an explicit Google Gemini model slug")
    if not 12 <= proposal_count <= 20:
        raise ValueError("proposal_count must be between 12 and 20")
    if not 1 <= max_output_tokens <= MAX_OUTPUT_TOKENS_CEILING:
        raise ValueError("max_output_tokens exceeds bounded G2 ceiling")
    if not 0.0 <= temperature <= 1.2:
        raise ValueError("temperature outside bounded G2 range")
    if not system_prompt or not user_prompt:
        raise ValueError("system_prompt and user_prompt are required")
    if not sanitized:
        raise ValueError("G2 challenge requires sanitized=true")
    if case_data_allowed:
        raise ValueError("G2 challenge forbids case data")
    if external_effect_allowed:
        raise ValueError("G2 challenge forbids external effects")

    return ChallengeSpec(
        challenge_id=challenge_id,
        model=model,
        proposal_count=proposal_count,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        sanitized=sanitized,
        case_data_allowed=case_data_allowed,
        external_effect_allowed=external_effect_allowed,
    )


def response_schema(spec: ChallengeSpec) -> dict[str, Any]:
    proposal = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "proposal_id": {"type": "string"},
            "name": {"type": "string"},
            "problem": {"type": "string"},
            "functionality": {"type": "string"},
            "why_existing_architecture_is_insufficient": {"type": "string"},
            "reuse_strategy": {
                "type": "string",
                "enum": ["REUSE", "EXTEND", "COMPOSE", "NEW_LAST"],
            },
            "dependencies": {"type": "array", "items": {"type": "string"}},
            "owner_burden_reduction": {"type": "string"},
            "operational_value": {"type": "string"},
            "commercial_value": {"type": "string"},
            "proof_gate": {"type": "string"},
            "risks": {"type": "array", "items": {"type": "string"}},
            "priority": {"type": "string", "enum": ["P0", "P1", "P2"]},
        },
        "required": [
            "proposal_id",
            "name",
            "problem",
            "functionality",
            "why_existing_architecture_is_insufficient",
            "reuse_strategy",
            "dependencies",
            "owner_burden_reduction",
            "operational_value",
            "commercial_value",
            "proof_gate",
            "risks",
            "priority",
        ],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "challenge_id": {"type": "string", "const": spec.challenge_id},
            "system_level_thesis": {"type": "string"},
            "elite_studio_gaps": {"type": "array", "items": {"type": "string"}},
            "proposals": {
                "type": "array",
                "minItems": spec.proposal_count,
                "maxItems": spec.proposal_count,
                "items": proposal,
            },
            "top_three": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {"type": "string"},
            },
            "anti_bloat_warning": {"type": "string"},
        },
        "required": [
            "challenge_id",
            "system_level_thesis",
            "elite_studio_gaps",
            "proposals",
            "top_three",
            "anti_bloat_warning",
        ],
    }


def build_request(spec: ChallengeSpec) -> dict[str, Any]:
    schema = response_schema(spec)
    return {
        "model": spec.model,
        "messages": [
            {"role": "system", "content": spec.system_prompt},
            {"role": "user", "content": spec.user_prompt},
        ],
        "temperature": spec.temperature,
        "max_tokens": spec.max_output_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "sovara_creative_architecture_challenge",
                "strict": True,
                "schema": schema,
            },
        },
        "provider": {
            "data_collection": "deny",
            "zdr": True,
            "allow_fallbacks": True,
        },
    }


def _extract_content(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError("provider response has no choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text = "".join(
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict)
        )
        if text:
            return text
    raise RuntimeError("provider response has no textual content")


def execute_challenge(
    *,
    spec: ChallengeSpec,
    api_key: str,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout_seconds: int = 180,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not api_key.strip():
        raise RuntimeError("OPENROUTER_API_KEY is not bound")

    payload = build_request(spec)
    request_bytes = _stable_json(payload).encode("utf-8")
    request = Request(
        endpoint,
        data=request_bytes,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/mosianekk-lang/Federation-Omega",
            "X-Title": "SOVARA Creative Gemini Architecture Challenge",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as result:
            response_bytes = result.read()
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"OpenRouter HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"OpenRouter transport failure: {exc.reason}") from exc

    response = json.loads(response_bytes.decode("utf-8"))
    content = _extract_content(response)
    output = json.loads(content)
    if output.get("challenge_id") != spec.challenge_id:
        raise RuntimeError("Gemini response did not return the exact challenge_id")
    proposals = output.get("proposals") or []
    if len(proposals) != spec.proposal_count:
        raise RuntimeError("Gemini response proposal count does not match challenge contract")

    response_id = str(response.get("id", "")).strip()
    model_returned = str(response.get("model", "")).strip()
    provider = str(response.get("provider", "")).strip()
    if not response_id:
        raise RuntimeError("provider response id is missing")
    if "gemini" not in model_returned.lower():
        raise RuntimeError(f"unexpected returned model: {model_returned!r}")

    receipt: dict[str, Any] = {
        "schema": "SOVARA_CREATIVE_GEMINI_ARCHITECTURE_CHALLENGE_RECEIPT_V1",
        "status": "VERIFIED",
        "challenge_id": spec.challenge_id,
        "transport": "OPENROUTER",
        "model_requested": spec.model,
        "model_returned": model_returned,
        "provider": provider,
        "provider_request_id": response_id,
        "semantic_verified": True,
        "prompt_sha256": _sha(spec.system_prompt + "\n" + spec.user_prompt),
        "request_sha256": _sha(request_bytes),
        "response_sha256": _sha(response_bytes),
        "output_sha256": _sha(_stable_json(output)),
        "proposal_count": len(proposals),
        "usage": response.get("usage") if isinstance(response.get("usage"), dict) else {},
        "sanitized": spec.sanitized,
        "case_data_processed": False,
        "external_effect_performed": False,
        "credential_value_recorded": False,
        "proposal_authority_only": True,
        "provider_native_readback": True,
    }
    receipt["receipt_sha256"] = _sha(_stable_json(receipt))
    return output, receipt


def _vertex_fallback(spec: ChallengeSpec) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        from .gemini_vertex_architecture_challenge import execute_vertex_challenge
    except ImportError:
        from gemini_vertex_architecture_challenge import execute_vertex_challenge

    token = subprocess.check_output(
        ["gcloud", "auth", "print-access-token"],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()
    active_account = subprocess.check_output(
        ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip().splitlines()[0]
    output, vertex = execute_vertex_challenge(
        spec=spec,
        access_token=token,
        active_account=active_account,
    )
    receipt: dict[str, Any] = {
        "schema": "SOVARA_CREATIVE_GEMINI_ARCHITECTURE_CHALLENGE_RECEIPT_V1",
        "status": vertex.get("status"),
        "challenge_id": vertex.get("challenge_id"),
        "transport": vertex.get("transport"),
        "project": vertex.get("project"),
        "location": vertex.get("location"),
        "active_account": vertex.get("active_account"),
        "model_requested": spec.model,
        "model_returned": vertex.get("model_returned"),
        "provider": "GOOGLE_VERTEX_AI",
        "provider_request_id": vertex.get("provider_request_id"),
        "semantic_verified": vertex.get("semantic_verified") is True,
        "prompt_sha256": vertex.get("prompt_sha256"),
        "request_sha256": vertex.get("request_sha256"),
        "response_sha256": vertex.get("response_sha256"),
        "output_sha256": vertex.get("output_sha256"),
        "proposal_count": vertex.get("proposal_count"),
        "usage": vertex.get("usage") if isinstance(vertex.get("usage"), dict) else {},
        "sanitized": spec.sanitized,
        "case_data_processed": False,
        "provider_mutation_performed": False,
        "external_effect_performed": False,
        "credential_value_recorded": False,
        "proposal_authority_only": True,
        "provider_native_readback": vertex.get("provider_native_readback") is True,
        "fallback_reason": "OPENROUTER_CREDENTIAL_UNBOUND",
    }
    receipt["receipt_sha256"] = _sha(_stable_json(receipt))
    return output, receipt


def write_outputs(
    *,
    output_dir: str | Path,
    output: dict[str, Any] | None,
    receipt: dict[str, Any],
) -> None:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    if output is not None:
        (directory / "GEMINI_CREATIVE_ARCHITECTURE_CHALLENGE_OUTPUT.json").write_text(
            json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    (directory / "GEMINI_CREATIVE_ARCHITECTURE_CHALLENGE_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_failure(output_dir: str | Path, spec: ChallengeSpec, exc: Exception) -> None:
    receipt: dict[str, Any] = {
        "schema": "SOVARA_CREATIVE_GEMINI_ARCHITECTURE_CHALLENGE_RECEIPT_V1",
        "status": "FAILED",
        "challenge_id": spec.challenge_id,
        "transport": "OPENROUTER_THEN_VERTEX_WIF",
        "model_requested": spec.model,
        "model_returned": None,
        "provider": None,
        "provider_request_id": None,
        "semantic_verified": False,
        "proposal_count": 0,
        "sanitized": spec.sanitized,
        "case_data_processed": False,
        "provider_mutation_performed": False,
        "external_effect_performed": False,
        "credential_value_recorded": False,
        "proposal_authority_only": True,
        "error_class": type(exc).__name__,
        "error_detail": str(exc)[:500],
    }
    receipt["receipt_sha256"] = _sha(_stable_json(receipt))
    write_outputs(output_dir=output_dir, output=None, receipt=receipt)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    args = parser.parse_args(argv)

    spec = load_spec(args.spec)
    try:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if api_key.strip():
            output, receipt = execute_challenge(
                spec=spec,
                api_key=api_key,
                endpoint=args.endpoint,
            )
        else:
            output, receipt = _vertex_fallback(spec)
        write_outputs(output_dir=args.output_dir, output=output, receipt=receipt)
        print(json.dumps(receipt, sort_keys=True))
        return 0
    except Exception as exc:
        _write_failure(args.output_dir, spec, exc)
        print(f"SOVARA_GEMINI_G2_FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
