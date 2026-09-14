from __future__ import annotations

import json
import re
import threading
from typing import Any, Protocol
from urllib import error, parse, request

from .util import canonical_json, parse_utc, require_nonempty


class TrustedAnchorStore(Protocol):
    def read(self, store_id: str) -> dict[str, Any] | None:
        ...

    def commit(self, store_id: str, anchor: dict[str, Any]) -> None:
        ...


def _validate_anchor(anchor: dict[str, Any]) -> None:
    required = {
        "checkpoint_id", "event_count", "event_chain_root", "state_root",
        "observed_at", "authority_id",
    }
    if set(anchor) != required:
        raise ValueError("trusted anchor fields invalid")
    if isinstance(anchor["checkpoint_id"], bool) or not isinstance(anchor["checkpoint_id"], int):
        raise ValueError("trusted anchor checkpoint_id invalid")
    if anchor["checkpoint_id"] < 1:
        raise ValueError("trusted anchor checkpoint_id invalid")
    if isinstance(anchor["event_count"], bool) or not isinstance(anchor["event_count"], int):
        raise ValueError("trusted anchor event_count invalid")
    if anchor["event_count"] < 0:
        raise ValueError("trusted anchor event_count invalid")
    for field in ("event_chain_root", "state_root"):
        if not isinstance(anchor[field], str) or not re.fullmatch(r"[0-9a-f]{64}", anchor[field]):
            raise ValueError(f"trusted anchor {field} invalid")
    parse_utc(str(anchor["observed_at"]))
    require_nonempty(anchor["authority_id"], "trusted anchor authority_id")


class MemoryTrustedAnchorStore:
    """Independent monotonic anchor for tests and single-process control planes."""

    def __init__(self):
        self._records: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def read(self, store_id: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._records.get(store_id)
            return dict(value) if value else None

    def commit(self, store_id: str, anchor: dict[str, Any]) -> None:
        _validate_anchor(anchor)
        with self._lock:
            current = self._records.get(store_id)
            if current and anchor["checkpoint_id"] < current["checkpoint_id"]:
                raise ValueError("trusted anchor rollback prohibited")
            if current and anchor["checkpoint_id"] == current["checkpoint_id"]:
                if current != anchor:
                    raise ValueError("trusted anchor collision")
                return
            self._records[store_id] = dict(anchor)


class _NoRedirectHandler(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HttpCasTrustedAnchorStore:
    """HTTPS client for an independently durable, atomic compare-and-swap anchor."""

    def __init__(self, base_url: str, *, bearer_token: str, timeout_seconds: float = 5.0):
        value = str(require_nonempty(base_url, "anchor base_url")).rstrip("/")
        parsed = parse.urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("trusted anchor endpoint must be an HTTPS origin without userinfo")
        token = str(require_nonempty(bearer_token, "anchor bearer token"))
        if len(token) < 16:
            raise ValueError("anchor bearer token is too short")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            raise ValueError("anchor timeout must be numeric")
        if timeout_seconds <= 0 or timeout_seconds > 30:
            raise ValueError("anchor timeout must be between 0 and 30 seconds")
        self.base_url = value
        self._bearer_token = token
        self._timeout_seconds = float(timeout_seconds)
        self._opener = request.build_opener(_NoRedirectHandler())

    def _request(
        self, method: str, store_id: str, body: dict[str, Any] | None = None
    ) -> tuple[int, dict[str, Any] | None]:
        store_id = str(require_nonempty(store_id, "store_id"))
        url = self.base_url + "/anchors/" + parse.quote(store_id, safe="")
        data = canonical_json(body).encode("utf-8") if body is not None else None
        headers = {
            "Accept": "application/json",
            "Authorization": "Bearer " + self._bearer_token,
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        call = request.Request(url, data=data, headers=headers, method=method)
        try:
            with self._opener.open(call, timeout=self._timeout_seconds) as response:
                raw = response.read(1_048_577)
                if len(raw) > 1_048_576:
                    raise ValueError("trusted anchor response exceeds size limit")
                value = json.loads(raw) if raw else None
                if value is not None and not isinstance(value, dict):
                    raise ValueError("trusted anchor response must be an object")
                return int(response.status), value
        except error.HTTPError as exc:
            if exc.code == 404 and method == "GET":
                return 404, None
            if exc.code == 409:
                raise ValueError("trusted anchor compare-and-swap conflict") from exc
            if 300 <= exc.code < 400:
                raise ConnectionError("trusted anchor redirects are prohibited") from exc
            raise ConnectionError(f"trusted anchor HTTP failure: {exc.code}") from exc
        except error.URLError as exc:
            raise ConnectionError("trusted anchor transport failure") from exc

    def read(self, store_id: str) -> dict[str, Any] | None:
        status, value = self._request("GET", store_id)
        if status == 404:
            return None
        if status != 200 or value is None:
            raise ValueError("trusted anchor read response invalid")
        anchor = value.get("anchor")
        if not isinstance(anchor, dict):
            raise ValueError("trusted anchor read payload invalid")
        _validate_anchor(anchor)
        return dict(anchor)

    def commit(self, store_id: str, anchor: dict[str, Any]) -> None:
        _validate_anchor(anchor)
        current = self.read(store_id)
        if current and anchor["checkpoint_id"] < current["checkpoint_id"]:
            raise ValueError("trusted anchor rollback prohibited")
        if current and anchor["checkpoint_id"] == current["checkpoint_id"]:
            if current != anchor:
                raise ValueError("trusted anchor collision")
            return
        expected_checkpoint_id = current["checkpoint_id"] if current else 0
        status, value = self._request(
            "PUT",
            store_id,
            {
                "schema": "CFBE-ACF-ANCHOR-CAS-V1",
                "expected_checkpoint_id": expected_checkpoint_id,
                "anchor": anchor,
            },
        )
        if status not in {200, 201} or value is None or value.get("anchor") != anchor:
            raise ValueError("trusted anchor commit readback mismatch")
