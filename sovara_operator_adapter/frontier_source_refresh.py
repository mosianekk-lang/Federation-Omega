#!/usr/bin/env python3
"""Observe official benchmark sources and open semantic review work on change.

The watcher stores fingerprints and metadata, not copied page bodies. A source
change never promotes a score automatically; it creates a review item that must
pass the same evidence and non-regression gates as any other benchmark change.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from frontier_benchmark_engine import canonical_sha256, load_knowledgebase


OBSERVATION_CONTRACT = "SOVARA_FRONTIER_SOURCE_OBSERVATION_V2"
SOURCE_REPOSITORY_CONTRACT = "SOVARA_FRONTIER_SOURCE_REPOSITORY_V2"
MAX_SOURCE_BYTES = 4 * 1024 * 1024


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def normalized_text_digest(body: bytes, content_type: str) -> tuple[str, int]:
    text = body.decode("utf-8", errors="replace")
    if "html" in content_type.lower() or "<html" in text[:1000].lower():
        parser = _TextExtractor()
        parser.feed(text)
        text = " ".join(parser.parts)
    normalized = re.sub(r"\s+", " ", text).strip()
    return canonical_sha256(normalized), len(normalized)


def _default_fetch(url: str, timeout: float) -> tuple[int, Mapping[str, str], bytes]:
    request = Request(
        url,
        headers={
            "User-Agent": "SOVARA-Frontier-Benchmark/2.0 (+evidence-change-monitor)",
            "Accept": "text/html,application/json,text/plain;q=0.9,*/*;q=0.5",
        },
    )
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - URLs are validated HTTPS evidence sources
        body = response.read(MAX_SOURCE_BYTES + 1)
        if len(body) > MAX_SOURCE_BYTES:
            raise ValueError("SOURCE_TOO_LARGE")
        return int(response.status), dict(response.headers.items()), body


def observe_sources(
    knowledgebase: Mapping[str, Any],
    *,
    observed_at: datetime,
    prior: Mapping[str, Any] | None = None,
    fetcher: Callable[[str, float], tuple[int, Mapping[str, str], bytes]] = _default_fetch,
    timeout: float = 20.0,
) -> dict[str, Any]:
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    observed_at = observed_at.astimezone(timezone.utc)
    prior_by_id = {
        item["sourceId"]: item for item in (prior or {}).get("sources", [])
    }
    results: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    for source in knowledgebase["sources"]:
        source_id = source["id"]
        if not source["url"].startswith("https://"):
            results.append(
                {
                    "sourceId": source_id,
                    "url": source["url"],
                    "state": "LOCAL_EVIDENCE_NOT_NETWORK_FETCHED",
                    "observedAt": observed_at.isoformat().replace("+00:00", "Z"),
                    "semanticDigest": None,
                    "byteCount": None,
                }
            )
            continue
        try:
            status, headers, body = fetcher(source["url"], timeout)
            content_type = str(headers.get("Content-Type") or headers.get("content-type") or "")
            digest, text_length = normalized_text_digest(body, content_type)
            prior_item = prior_by_id.get(source_id)
            if not prior_item or not prior_item.get("semanticDigest"):
                state = "NEW_BASELINE"
            elif prior_item["semanticDigest"] == digest:
                state = "UNCHANGED"
            else:
                state = "CHANGED_REVIEW_REQUIRED"
            result = {
                "sourceId": source_id,
                "url": source["url"],
                "state": state,
                "observedAt": observed_at.isoformat().replace("+00:00", "Z"),
                "httpStatus": status,
                "contentType": content_type,
                "etag": headers.get("ETag") or headers.get("etag"),
                "lastModified": headers.get("Last-Modified") or headers.get("last-modified"),
                "semanticDigest": digest,
                "normalizedTextLength": text_length,
                "byteCount": len(body),
            }
            results.append(result)
            if state in {"NEW_BASELINE", "CHANGED_REVIEW_REQUIRED"}:
                review_queue.append(
                    {
                        "sourceId": source_id,
                        "state": "SEMANTIC_REVIEW_REQUIRED",
                        "reason": state,
                        "automaticScorePromotionAllowed": False,
                        "requiredChecks": [
                            "read_current_primary_source",
                            "extract_supported_propositions",
                            "recalculate_only_supported_dimensions",
                            "run_failure_first_tests",
                            "compare_non_regression",
                            "formation_promotion_gate",
                        ],
                    }
                )
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            results.append(
                {
                    "sourceId": source_id,
                    "url": source["url"],
                    "state": "FETCH_FAILED",
                    "observedAt": observed_at.isoformat().replace("+00:00", "Z"),
                    "errorClass": type(exc).__name__,
                    "semanticDigest": None,
                    "byteCount": None,
                }
            )
            review_queue.append(
                {
                    "sourceId": source_id,
                    "state": "RECOVERY_REQUIRED",
                    "reason": "FETCH_FAILED",
                    "automaticScorePromotionAllowed": False,
                    "requiredChecks": [
                        "retry_with_bounded_backoff",
                        "verify_canonical_url",
                        "retain_last_good_evidence",
                    ],
                }
            )
    material = any(
        item["state"] in {"NEW_BASELINE", "CHANGED_REVIEW_REQUIRED", "FETCH_FAILED"}
        for item in results
    )
    result_digest = canonical_sha256(
        {
            item["sourceId"]: {
                "semanticDigest": item.get("semanticDigest"),
                "failure": item["state"] == "FETCH_FAILED",
            }
            for item in results
        }
    )
    return {
        "contract": OBSERVATION_CONTRACT,
        "observedAt": observed_at.isoformat().replace("+00:00", "Z"),
        "knowledgebaseFingerprint": canonical_sha256(knowledgebase),
        "observationDigest": result_digest,
        "sourceCount": len(results),
        "networkSourceCount": sum(item["url"].startswith("https://") for item in results),
        "changedSourceCount": sum(
            item["state"] == "CHANGED_REVIEW_REQUIRED" for item in results
        ),
        "failedSourceCount": sum(item["state"] == "FETCH_FAILED" for item in results),
        "materialChange": material,
        "sources": results,
        "reviewQueue": review_queue,
        "automaticScorePromotionAllowed": False,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def persist_observation(
    observation: Mapping[str, Any], repository: str | Path
) -> dict[str, Any]:
    repository = Path(repository)
    index_path = repository / "index.json"
    journal_path = repository / "refresh-journal.ndjson"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        if index.get("contract") != SOURCE_REPOSITORY_CONTRACT:
            raise ValueError("source repository contract mismatch")
    else:
        index = {"contract": SOURCE_REPOSITORY_CONTRACT, "snapshots": []}
    snapshot_id = (
        observation["observedAt"].replace(":", "").replace("-", "")
        + "-"
        + observation["observationDigest"].split(":", 1)[1][:12]
    )
    snapshot_path = repository / "snapshots" / f"{snapshot_id}.json"
    latest_digest = index.get("latestObservationDigest")
    if latest_digest != observation["observationDigest"]:
        if not snapshot_path.exists():
            _atomic_write_json(snapshot_path, observation)
        relative = str(snapshot_path.relative_to(repository))
        if relative not in index["snapshots"]:
            index["snapshots"].append(relative)
        index["latestSnapshotId"] = snapshot_id
        index["latestSnapshotPath"] = relative
        index["latestObservationDigest"] = observation["observationDigest"]
        index["updatedAt"] = observation["observedAt"]
        _atomic_write_json(index_path, index)
        state = "MATERIAL_OBSERVATION_WRITTEN"
    else:
        state = "NO_CHANGE_NO_SNAPSHOT_WRITE"
    if state == "MATERIAL_OBSERVATION_WRITTEN":
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        with journal_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "observedAt": observation["observedAt"],
                        "state": state,
                        "observationDigest": observation["observationDigest"],
                        "changedSourceCount": observation["changedSourceCount"],
                        "failedSourceCount": observation["failedSourceCount"],
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
    return {
        "state": state,
        "snapshotId": snapshot_id,
        "snapshotPath": str(snapshot_path),
        "indexPath": str(index_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--knowledgebase", default="frontier_knowledgebase_v2.json")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--observed-at")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--require-all", action="store_true")
    args = parser.parse_args()
    knowledgebase = load_knowledgebase(args.knowledgebase)
    observed_at = (
        datetime.fromisoformat(args.observed_at.replace("Z", "+00:00"))
        if args.observed_at
        else datetime.now(timezone.utc)
    )
    repository = Path(args.repository)
    prior = None
    index_path = repository / "index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        latest_path = index.get("latestSnapshotPath")
        if latest_path:
            prior = json.loads((repository / latest_path).read_text(encoding="utf-8"))
    observation = observe_sources(
        knowledgebase, observed_at=observed_at, prior=prior, timeout=args.timeout
    )
    persisted = persist_observation(observation, repository)
    output = {
        "decision": "REVIEW_REQUIRED" if observation["reviewQueue"] else "NO_CHANGE",
        "observationDigest": observation["observationDigest"],
        "changedSourceCount": observation["changedSourceCount"],
        "failedSourceCount": observation["failedSourceCount"],
        "automaticScorePromotionAllowed": False,
        "repository": persisted,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    if args.require_all and observation["failedSourceCount"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
