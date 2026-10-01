"""Stateless Vertex Interactions client for the private SOVARA Gemini gateway.

This module uses only the gateway runtime service-account ADC supplied by the
caller. It never reads API keys, service-account keys, or provider-native
conversation state.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CANONICAL_PROJECT_ID = "sov-hybrid-suite"
DEFAULT_LOCATION = "global"
DEFAULT_MODEL = "gemini-3.8-flash"
USER_AGENT = "sovara-gemini-gateway/interactions-v2"


class InteractionsError(RuntimeError):
    def __init__(self, code: str, detail: str = "", *, http_status: int = 502) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code
        self.http_status = http_status


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(value: Any) -> str:
    if not isinstance(value, str):
        value = canonical_json(value)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _default_fetch(request: Request) -> tuple[int, object]:
    try:
        with urlopen(request, timeout=90.0) as response:
            raw = response.read().decode("utf-8", "replace")
            return int(getattr(response, "status", response.getcode())), json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload: object = json.loads(raw) if raw else {}
        except Exception:
            payload = {"raw_sha256": sha256(raw)}
        raise InteractionsError(
            "INTERACTIONS_UPSTREAM_HTTP_ERROR",
            f"HTTP {exc.code}: response_sha256={sha256(payload)}",
            http_status=502,
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise InteractionsError("INTERACTIONS_UPSTREAM_TRANSPORT_ERROR", str(exc), http_status=502) from exc


def normalize_interaction_response(payload: object) -> dict[str, Any]:
    """Return one unambiguous Interaction object or fail closed."""
    if isinstance(payload, dict):
        nested = payload.get("interaction")
        if isinstance(nested, dict):
            return dict(nested)
        return dict(payload)

    if isinstance(payload, list):
        candidates: dict[str, dict[str, Any]] = {}
        for row in payload:
            if not isinstance(row, dict):
                continue
            nested = row.get("interaction")
            candidate = nested if isinstance(nested, dict) else row
            if not any(key in candidate for key in ("id", "status", "steps", "usage", "object")):
                continue
            key = str(candidate.get("id") or sha256(candidate))
            candidates[key] = dict(candidate)

        rows = list(candidates.values())
        if len(rows) == 1:
            return rows[0]

        completed = [
            row for row in rows
            if row.get("status") == "completed" and row.get("id")
        ]
        if len(completed) == 1:
            return completed[0]

        raise InteractionsError(
            "INTERACTIONS_RESPONSE_AMBIGUOUS",
            f"candidate_count={len(rows)}",
        )

    raise InteractionsError(
        "INTERACTIONS_RESPONSE_TYPE_INVALID",
        type(payload).__name__,
    )


def extract_output_text(interaction: dict[str, Any]) -> str:
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


class VertexInteractionsClient:
    def __init__(
        self,
        identity: Any,
        *,
        location: str = DEFAULT_LOCATION,
        model: str = DEFAULT_MODEL,
        fetch_json: Callable[[Request], tuple[int, object]] | None = None,
    ) -> None:
        self.identity = identity
        self.location = str(location).strip()
        self.model = str(model).strip()
        self._fetch_json = fetch_json or _default_fetch
        if self.location != "global":
            raise InteractionsError(
                "INTERACTIONS_NON_CANONICAL_LOCATION",
                self.location,
                http_status=503,
            )
        if not self.model or "/" in self.model or ":" in self.model:
            raise InteractionsError(
                "INTERACTIONS_MODEL_ID_INVALID",
                self.model,
                http_status=503,
            )

    @property
    def endpoint(self) -> str:
        return (
            "https://aiplatform.googleapis.com/v1beta1/projects/"
            f"{CANONICAL_PROJECT_ID}/locations/{self.location}/interactions"
        )

    def interact(self, *, prompt: str) -> dict[str, Any]:
        prompt = str(prompt)
        if not prompt.strip():
            raise InteractionsError("INTERACTIONS_PROMPT_REQUIRED", http_status=400)
        identity = self.identity.snapshot()
        token = self.identity.access_token()
        body = {
            "model": self.model,
            "input": prompt,
            "store": False,
        }
        request = Request(
            self.endpoint,
            data=canonical_json(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        started = time.monotonic()
        status, raw_payload = self._fetch_json(request)
        latency_ms = int((time.monotonic() - started) * 1000)
        if not 200 <= int(status) < 300:
            raise InteractionsError(
                "INTERACTIONS_HTTP_ERROR",
                f"HTTP {status}",
            )

        interaction = normalize_interaction_response(raw_payload)
        interaction_id = str(interaction.get("id") or "")
        interaction_status = str(interaction.get("status") or "")
        usage = interaction.get("usage")
        text = extract_output_text(interaction)
        if (
            not interaction_id
            or interaction_status != "completed"
            or not isinstance(usage, dict)
            or not text
        ):
            raise InteractionsError(
                "INTERACTIONS_PROVIDER_IDENTITY_INCOMPLETE",
                canonical_json({
                    "interaction_id": bool(interaction_id),
                    "interaction_status": interaction_status,
                    "usage": isinstance(usage, dict),
                    "text": bool(text),
                }),
            )

        return {
            "provider": "GOOGLE_VERTEX_AI_INTERACTIONS",
            "protocol": "VERTEX_AI_INTERACTIONS_REST",
            "provider_request_id": interaction_id,
            "interaction_id": interaction_id,
            "interaction_status": interaction_status,
            "model_identity": str(interaction.get("model") or self.model),
            "model_identity_source": "PROVIDER_RESPONSE" if interaction.get("model") else "BOUND_REQUEST",
            "configured_model": self.model,
            "finish_state": interaction_status,
            "usage": usage,
            "latency_ms": latency_ms,
            "provider_identity": identity,
            "request_sha256": sha256(body),
            "response_sha256": sha256(raw_payload),
            "store": False,
            "text": text,
        }
