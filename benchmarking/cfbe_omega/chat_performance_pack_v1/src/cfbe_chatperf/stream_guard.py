"""Fail-closed stream and workload admission checks."""

from __future__ import annotations

from typing import Any, Mapping


def assess_stream(packet: Mapping[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    payload = int(packet.get("payload_tokens", 0))
    if payload > int(packet.get("max_payload_tokens", 4000)):
        issues.append("PAYLOAD_OVERFLOW")
    if int(packet.get("retry_count", 0)) > int(packet.get("retry_budget", 1)):
        issues.append("RETRY_STORM")
    if int(packet.get("concurrency", 1)) > int(packet.get("max_concurrency", 4)):
        issues.append("CONCURRENCY_OVERFLOW")
    if float(packet.get("elapsed_minutes", 0)) > float(packet.get("max_elapsed_minutes", 18)):
        issues.append("TIMEBOX_EXCEEDED")
    if packet.get("raw_payload_serialized") is True:
        issues.append("RAW_PAYLOAD_SERIALIZED")
    if packet.get("contains_secret") is True:
        issues.append("SECRET_EXPOSURE")
    if packet.get("unchanged_failed_route_retried") is True:
        issues.append("UNCHANGED_ROUTE_RETRY")
    return {
        "decision": "ADMIT" if not issues else "QUARANTINE",
        "issues": issues,
        "checkpoint_required": bool(issues),
        "maximum_segment_tokens": min(int(packet.get("max_payload_tokens", 4000)), 4000),
    }
