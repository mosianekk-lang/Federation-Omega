from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from .gemini_architecture_challenge import ChallengeSpec, load_spec
except ImportError:  # direct file-path execution inside the trusted workflow
    from gemini_architecture_challenge import ChallengeSpec, load_spec


DEFAULT_PROJECT = "sov-hybrid-suite"
DEFAULT_LOCATION = "global"
DEFAULT_MODEL = "gemini-3.1-pro-preview"


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: str | bytes) -> str:
    raw = value if isinstance(value, bytes) else value.encode("utf-8")
    return sha256(raw).hexdigest()


def vertex_endpoint(*, project: str, location: str, model: str) -> str:
    return (
        "https://aiplatform.googleapis.com/v1/"
        f"projects/{project}/locations/{location}/publishers/google/models/{model}:generateContent"
    )


def build_vertex_request(spec: ChallengeSpec) -> dict[str, Any]:
    return {
        "systemInstruction": {
            "parts": [{"text": spec.system_prompt}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": spec.user_prompt}],
            }
        ],
        "generationConfig": {
            "temperature": spec.temperature,
            "maxOutputTokens": spec.max_output_tokens,
            "responseMimeType": "application/json",
        },
    }


def _candidate_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates") or []
    if not candidates:
        raise RuntimeError("Vertex response has no candidates")
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    text = "".join(
        str(part.get("text", ""))
        for part in parts
        if isinstance(part, dict)
    )
    if not text.strip():
        raise RuntimeError("Vertex response has no candidate text")
    return text


def _validate_output(spec: ChallengeSpec, output: dict[str, Any]) -> None:
    if output.get("challenge_id") != spec.challenge_id:
        raise RuntimeError("Gemini response did not return the exact challenge_id")
    proposals = output.get("proposals") or []
    if not isinstance(proposals, list) or len(proposals) != spec.proposal_count:
        raise RuntimeError("Gemini response proposal count does not match challenge contract")
    top_three = output.get("top_three") or []
    if not isinstance(top_three, list) or len(top_three) != 3:
        raise RuntimeError("Gemini response top_three must contain exactly three items")
    for required in ("system_level_thesis", "elite_studio_gaps", "anti_bloat_warning"):
        if not output.get(required):
            raise RuntimeError(f"Gemini response missing {required}")
    required_proposal_fields = {
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
    }
    seen: set[str] = set()
    for proposal in proposals:
        if not isinstance(proposal, dict):
            raise RuntimeError("proposal is not an object")
        missing = required_proposal_fields - set(proposal)
        if missing:
            raise RuntimeError(f"proposal missing fields: {sorted(missing)}")
        pid = str(proposal.get("proposal_id", "")).strip()
        if not pid or pid in seen:
            raise RuntimeError("proposal_id is empty or duplicated")
        seen.add(pid)
        if proposal.get("reuse_strategy") not in {"REUSE", "EXTEND", "COMPOSE", "NEW_LAST"}:
            raise RuntimeError(f"invalid reuse_strategy for {pid}")
        if proposal.get("priority") not in {"P0", "P1", "P2"}:
            raise RuntimeError(f"invalid priority for {pid}")


def _failure_receipt(
    *,
    spec: ChallengeSpec,
    endpoint: str,
    active_account: str,
    error_class: str,
    http_status: int | None,
    error_body: bytes | None,
    detail: str,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema": "SOVARA_CREATIVE_GEMINI_VERTEX_CHALLENGE_RECEIPT_V1",
        "status": "FAILED",
        "challenge_id": spec.challenge_id,
        "transport": "VERTEX_AI_WIF_DIRECT",
        "project": DEFAULT_PROJECT,
        "location": DEFAULT_LOCATION,
        "model_requested": DEFAULT_MODEL,
        "active_account": active_account,
        "endpoint_sha256": _sha(endpoint),
        "error_class": error_class,
        "http_status": http_status,
        "error_body_sha256": _sha(error_body) if error_body is not None else None,
        "detail": detail[:500],
        "case_data_processed": False,
        "provider_mutation_performed": False,
        "external_effect_performed": False,
        "credential_value_recorded": False,
        "proposal_authority_only": True,
    }
    receipt["receipt_sha256"] = _sha(_stable_json(receipt))
    return receipt


def execute_vertex_challenge(
    *,
    spec: ChallengeSpec,
    access_token: str,
    active_account: str,
    project: str = DEFAULT_PROJECT,
    location: str = DEFAULT_LOCATION,
    model: str = DEFAULT_MODEL,
    timeout_seconds: int = 240,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not access_token.strip():
        raise RuntimeError("VERTEX_ACCESS_TOKEN is not bound")
    if project != DEFAULT_PROJECT or location != DEFAULT_LOCATION or model != DEFAULT_MODEL:
        raise RuntimeError("G3 route is pinned to the admitted project/location/model")

    endpoint = vertex_endpoint(project=project, location=location, model=model)
    payload = build_vertex_request(spec)
    request_bytes = _stable_json(payload).encode("utf-8")
    request = Request(
        endpoint,
        data=request_bytes,
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as result:
            http_status = int(getattr(result, "status", 200))
            response_bytes = result.read()
    except HTTPError as exc:
        body = exc.read()
        detail = body.decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            detail = str((parsed.get("error") or {}).get("message") or detail)
        except Exception:
            pass
        raise VertexChallengeHTTPError(exc.code, body, detail) from exc
    except URLError as exc:
        raise RuntimeError(f"Vertex transport failure: {exc.reason}") from exc

    response = json.loads(response_bytes.decode("utf-8"))
    text = _candidate_text(response)
    output = json.loads(text)
    _validate_output(spec, output)

    response_id = str(response.get("responseId", "")).strip()
    model_version = str(response.get("modelVersion", "")).strip()
    if not response_id:
        raise RuntimeError("Vertex responseId is missing")
    if "gemini" not in model_version.lower():
        raise RuntimeError(f"unexpected Vertex modelVersion: {model_version!r}")

    receipt: dict[str, Any] = {
        "schema": "SOVARA_CREATIVE_GEMINI_VERTEX_CHALLENGE_RECEIPT_V1",
        "status": "VERIFIED",
        "challenge_id": spec.challenge_id,
        "transport": "VERTEX_AI_WIF_DIRECT",
        "project": project,
        "location": location,
        "active_account": active_account,
        "model_requested": model,
        "model_returned": model_version,
        "provider_request_id": response_id,
        "http_status": http_status,
        "semantic_verified": True,
        "prompt_sha256": _sha(spec.system_prompt + "\n" + spec.user_prompt),
        "request_sha256": _sha(request_bytes),
        "response_sha256": _sha(response_bytes),
        "output_sha256": _sha(_stable_json(output)),
        "proposal_count": len(output.get("proposals") or []),
        "usage": response.get("usageMetadata") if isinstance(response.get("usageMetadata"), dict) else {},
        "case_data_processed": False,
        "provider_mutation_performed": False,
        "external_effect_performed": False,
        "credential_value_recorded": False,
        "proposal_authority_only": True,
        "provider_native_readback": True,
    }
    receipt["receipt_sha256"] = _sha(_stable_json(receipt))
    return output, receipt


class VertexChallengeHTTPError(RuntimeError):
    def __init__(self, status: int, body: bytes, detail: str) -> None:
        super().__init__(f"Vertex HTTP {status}: {detail[:500]}")
        self.status = int(status)
        self.body = body
        self.detail = detail


def write_outputs(
    *,
    output_dir: str | Path,
    output: dict[str, Any] | None,
    receipt: dict[str, Any],
) -> None:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    if output is not None:
        (directory / "GEMINI_VERTEX_CREATIVE_ARCHITECTURE_CHALLENGE_OUTPUT.json").write_text(
            json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    (directory / "GEMINI_VERTEX_CREATIVE_ARCHITECTURE_CHALLENGE_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    spec = load_spec(args.spec)
    token = os.environ.get("VERTEX_ACCESS_TOKEN", "")
    active_account = os.environ.get("VERTEX_ACTIVE_ACCOUNT", "").strip()
    endpoint = vertex_endpoint(project=DEFAULT_PROJECT, location=DEFAULT_LOCATION, model=DEFAULT_MODEL)
    try:
        output, receipt = execute_vertex_challenge(
            spec=spec,
            access_token=token,
            active_account=active_account,
        )
        write_outputs(output_dir=args.output_dir, output=output, receipt=receipt)
        print(json.dumps(receipt, sort_keys=True))
        return 0
    except VertexChallengeHTTPError as exc:
        receipt = _failure_receipt(
            spec=spec,
            endpoint=endpoint,
            active_account=active_account,
            error_class="VERTEX_HTTP_ERROR",
            http_status=exc.status,
            error_body=exc.body,
            detail=exc.detail,
        )
        write_outputs(output_dir=args.output_dir, output=None, receipt=receipt)
        print(json.dumps(receipt, sort_keys=True), file=sys.stderr)
        return 1
    except Exception as exc:
        receipt = _failure_receipt(
            spec=spec,
            endpoint=endpoint,
            active_account=active_account,
            error_class=type(exc).__name__,
            http_status=None,
            error_body=None,
            detail=str(exc),
        )
        write_outputs(output_dir=args.output_dir, output=None, receipt=receipt)
        print(json.dumps(receipt, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
