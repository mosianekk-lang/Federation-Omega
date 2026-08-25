"""Secure, read-only official-source refresher for the benchmark fabric."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable

from .engine import canonical_json, digest, instant_text


class SourceRefreshError(RuntimeError):
    """A fail-closed official-source refresh constraint."""


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "svg", "noscript"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "svg", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            value = " ".join(data.split())
            if value:
                self._chunks.append(value)

    def text(self) -> str:
        return "\n".join(self._chunks)


def normalized_text(raw: bytes, content_type: str) -> str:
    decoded = raw.decode("utf-8", errors="replace")
    if "html" not in content_type.lower():
        return "\n".join(line.strip() for line in decoded.splitlines() if line.strip())
    parser = _TextExtractor()
    parser.feed(decoded)
    return parser.text()


def _default_resolver(host: str) -> list[str]:
    return sorted({row[4][0] for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})


def validate_public_https_url(
    url: str,
    allowed_hosts: set[str],
    *,
    resolver: Callable[[str], list[str]] = _default_resolver,
) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https":
        raise SourceRefreshError("SOURCE_URL_NOT_HTTPS")
    if parsed.username or parsed.password:
        raise SourceRefreshError("SOURCE_URL_CREDENTIALS_FORBIDDEN")
    if parsed.port not in (None, 443):
        raise SourceRefreshError("SOURCE_URL_PORT_FORBIDDEN")
    host = (parsed.hostname or "").lower().rstrip(".")
    if host not in allowed_hosts:
        raise SourceRefreshError(f"SOURCE_HOST_NOT_ALLOWLISTED:{host}")
    addresses = resolver(host)
    if not addresses:
        raise SourceRefreshError(f"SOURCE_DNS_EMPTY:{host}")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise SourceRefreshError(f"SOURCE_DNS_NONPUBLIC:{host}:{address}")
    return host


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: set[str], resolver: Callable[[str], list[str]]) -> None:
        super().__init__()
        self.allowed_hosts = allowed_hosts
        self.resolver = resolver
        self.redirect_count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        self.redirect_count += 1
        if self.redirect_count > 5:
            raise SourceRefreshError("SOURCE_REDIRECT_LIMIT_EXCEEDED")
        validate_public_https_url(newurl, self.allowed_hosts, resolver=self.resolver)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_one(
    source: dict[str, Any],
    allowed_hosts: set[str],
    *,
    fetched_at: datetime | None = None,
    resolver: Callable[[str], list[str]] = _default_resolver,
    opener: Any | None = None,
) -> tuple[dict[str, Any], str]:
    """Fetch one source with no credentials and return metadata plus normalized text."""

    now = (fetched_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    validate_public_https_url(str(source["url"]), allowed_hosts, resolver=resolver)
    maximum = min(int(source.get("maxBytes") or 1_500_000), 2_000_000)
    timeout = min(int(source.get("timeoutSeconds") or 20), 30)
    handler = _SafeRedirectHandler(allowed_hosts, resolver)
    client = opener or urllib.request.build_opener(handler)
    request = urllib.request.Request(
        str(source["url"]),
        headers={
            "Accept": "text/html,application/json,text/plain;q=0.9,*/*;q=0.1",
            "User-Agent": "FederationOmegaFrontierBenchmark/1.0 (+read-only official-source audit)",
        },
        method="GET",
    )
    try:
        response = client.open(request, timeout=timeout)
        try:
            final_url = response.geturl()
            validate_public_https_url(final_url, allowed_hosts, resolver=resolver)
            status = int(getattr(response, "status", 200))
            if status != 200:
                raise SourceRefreshError(f"SOURCE_HTTP_STATUS:{status}")
            content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0].lower()
            allowed_types = set(source.get("allowedContentTypes") or ["text/html", "application/json", "text/plain"])
            if content_type not in allowed_types:
                raise SourceRefreshError(f"SOURCE_CONTENT_TYPE_FORBIDDEN:{content_type or 'missing'}")
            raw = response.read(maximum + 1)
            if len(raw) > maximum:
                raise SourceRefreshError(f"SOURCE_BODY_TOO_LARGE:{len(raw)}")
            text = normalized_text(raw, content_type)
            if len(text) < int(source.get("minimumTextCharacters") or 100):
                raise SourceRefreshError("SOURCE_TEXT_TOO_SHORT")
            metadata = {
                "sourceId": source["id"],
                "fetchedAt": instant_text(now),
                "requestedUrl": source["url"],
                "finalUrl": final_url,
                "httpStatus": status,
                "contentType": content_type,
                "contentBytes": len(raw),
                "rawSha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
                "normalizedTextSha256": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "etag": response.headers.get("ETag"),
                "lastModified": response.headers.get("Last-Modified"),
                "watchSignals": {
                    term: text.lower().count(term.lower()) for term in source.get("watchTerms") or []
                },
                "retainedInSourceRepository": False,
            }
            metadata["snapshotSha256"] = digest(metadata)
            return metadata, text
        finally:
            response.close()
    except SourceRefreshError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SourceRefreshError(f"SOURCE_FETCH_FAILED:{type(exc).__name__}") from exc


def refresh_all(
    sources_payload: dict[str, Any],
    output_dir: str | Path,
    *,
    fetched_at: datetime | None = None,
    fetch: Callable[..., tuple[dict[str, Any], str]] = fetch_one,
) -> dict[str, Any]:
    """Refresh every reviewed source and emit immutable review inputs.

    Raw text is written only to the run output directory.  It is never written
    back to the source repository by this module.
    """

    now = (fetched_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    root = Path(output_dir)
    snapshot_dir = root / "knowledgebase" / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    allowed_hosts = set(sources_payload.get("allowedHosts") or [])
    rows: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []

    for source in sorted(sources_payload.get("sources") or [], key=lambda item: item["id"]):
        source_id = str(source["id"])
        try:
            metadata, text = fetch(source, allowed_hosts, fetched_at=now)
            reviewed_hash = source.get("reviewedNormalizedTextSha256")
            observed_hash = metadata["normalizedTextSha256"]
            if not reviewed_hash:
                state = "BASELINE_CAPTURE_REVIEW_REQUIRED"
            elif reviewed_hash == observed_hash:
                state = "UNCHANGED"
            else:
                state = "CHANGED_REVIEW_REQUIRED"
            metadata["refreshState"] = state
            (snapshot_dir / f"{source_id}.json").write_text(
                json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            (snapshot_dir / f"{source_id}.txt").write_text(text + "\n", encoding="utf-8")
            rows.append({
                "sourceId": source_id,
                "state": state,
                "snapshotSha256": metadata["snapshotSha256"],
                "normalizedTextSha256": observed_hash,
            })
            if state != "UNCHANGED":
                proposals.append({
                    "sourceId": source_id,
                    "state": state,
                    "reviewedNormalizedTextSha256": reviewed_hash,
                    "candidateNormalizedTextSha256": observed_hash,
                    "affectedControlIds": source.get("controlIds") or [],
                    "decision": "HUMAN_REVIEW_REQUIRED",
                    "automaticControlPromotion": False,
                    "automaticRepositoryMutation": False,
                })
        except Exception as exc:  # fail each source closed while preserving the whole run receipt
            rows.append({
                "sourceId": source_id,
                "state": "CONSTRAINT",
                "error": str(exc),
            })

    constraints = [row for row in rows if row["state"] == "CONSTRAINT"]
    manifest: dict[str, Any] = {
        "schema": "FEDOMEGA-FRONTIER-KNOWLEDGEBASE-REFRESH-1",
        "generatedAt": instant_text(now),
        "terminalState": "SUCCESS" if not constraints else "CONSTRAINT",
        "sourceCount": len(rows),
        "successfulSourceCount": len(rows) - len(constraints),
        "constraintCount": len(constraints),
        "repositoryMutationAttempted": False,
        "automaticBenchmarkPromotionAttempted": False,
        "sources": rows,
    }
    manifest["manifestSha256"] = digest(manifest)
    (root / "knowledgebase" / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    proposal_payload = {
        "schema": "FEDOMEGA-FRONTIER-REVIEW-PROPOSALS-1",
        "generatedAt": instant_text(now),
        "proposalCount": len(proposals),
        "proposals": proposals,
    }
    proposal_payload["proposalsSha256"] = digest(proposal_payload)
    (root / "knowledgebase" / "review-proposals.json").write_text(
        json.dumps(proposal_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest

