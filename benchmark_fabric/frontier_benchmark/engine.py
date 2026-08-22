"""Deterministic, proof-gated benchmark scoring and reporting.

The engine intentionally separates three things that are often blurred:

* a vendor or standards source describing a frontier capability;
* verified evidence that JARVIS implements or operates that capability; and
* production proof that the capability is provider-bound and working.

Refreshing a public source can change source freshness and create a review
proposal.  It can never promote JARVIS maturity automatically.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


MATURITY_LABELS = {
    0: "ABSENT",
    1: "DESIGNED",
    2: "SOURCE_IMPLEMENTED",
    3: "TESTED",
    4: "PROVIDER_BOUND",
    5: "PRODUCTION_PROVEN",
}

SOURCE_CLASS_WEIGHTS = {
    "STANDARD": 1.0,
    "PRODUCT_DOCUMENTATION": 1.0,
    "ENGINEERING_GUIDANCE": 0.95,
    "PUBLIC_OPERATIONAL_EVIDENCE": 0.85,
    "PRESS_RELEASE": 0.65,
    "CAREERS_PAGE": 0.40,
}

FRESHNESS_WEIGHTS = {"FRESH": 1.0, "DUE": 0.8, "STALE": 0.4, "UNVERIFIED": 0.0}


class BenchmarkError(ValueError):
    """Raised when the benchmark corpus violates its proof contract."""


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def parse_instant(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def instant_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _unique(rows: Iterable[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        identity = str(row.get(key) or "")
        if not identity:
            raise BenchmarkError(f"{label} missing {key}")
        if identity in indexed:
            raise BenchmarkError(f"duplicate {label} {identity}")
        indexed[identity] = row
    return indexed


def _source_freshness(source: dict[str, Any], as_of: datetime) -> dict[str, Any]:
    verified_at = source.get("verifiedAt")
    ttl_days = int(source.get("freshnessDays") or 0)
    if not verified_at or ttl_days < 1:
        return {"state": "UNVERIFIED", "ageDays": None, "freshnessDays": ttl_days}
    age = max(0, (as_of - parse_instant(str(verified_at))).days)
    if age <= ttl_days:
        state = "FRESH"
    elif age <= ttl_days * 2:
        state = "DUE"
    else:
        state = "STALE"
    return {"state": state, "ageDays": age, "freshnessDays": ttl_days}


def _validate(
    controls_payload: dict[str, Any],
    baseline_payload: dict[str, Any],
    sources_payload: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    controls = _unique(controls_payload.get("controls") or [], "id", "control")
    evidence = _unique(baseline_payload.get("evidence") or [], "controlId", "evidence record")
    sources = _unique(sources_payload.get("sources") or [], "id", "source")

    if set(controls) != set(evidence):
        missing = sorted(set(controls) - set(evidence))
        extra = sorted(set(evidence) - set(controls))
        raise BenchmarkError(f"baseline/control mismatch missing={missing} extra={extra}")

    for control_id, control in controls.items():
        weight = control.get("weight")
        target = control.get("frontierTargetMaturity")
        if not isinstance(weight, (int, float)) or weight <= 0:
            raise BenchmarkError(f"{control_id} has invalid weight")
        if not isinstance(target, int) or target not in MATURITY_LABELS or target < 1:
            raise BenchmarkError(f"{control_id} has invalid target maturity")
        references = control.get("referenceSourceIds") or []
        if not references:
            raise BenchmarkError(f"{control_id} has no reference sources")
        unknown = sorted(set(references) - set(sources))
        if unknown:
            raise BenchmarkError(f"{control_id} references unknown sources {unknown}")

        record = evidence[control_id]
        maturity = record.get("maturity")
        confidence = record.get("confidence")
        if not isinstance(maturity, int) or maturity not in MATURITY_LABELS:
            raise BenchmarkError(f"{control_id} has invalid evidence maturity")
        if maturity > target:
            raise BenchmarkError(f"{control_id} maturity exceeds target")
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            raise BenchmarkError(f"{control_id} has invalid confidence")
        if maturity > 0 and not record.get("evidenceRefs"):
            raise BenchmarkError(f"{control_id} claims maturity without evidence refs")
        if maturity >= 4 and record.get("providerProof") is not True:
            raise BenchmarkError(f"{control_id} claims provider binding without provider proof")
        if maturity == 5 and record.get("productionProof") is not True:
            raise BenchmarkError(f"{control_id} claims production maturity without production proof")
        if not record.get("nextEvidence"):
            raise BenchmarkError(f"{control_id} has no next-evidence gate")

    allowed_hosts = set(sources_payload.get("allowedHosts") or [])
    if not allowed_hosts:
        raise BenchmarkError("official source host allowlist is empty")
    for source_id, source in sources.items():
        if source.get("evidenceClass") not in SOURCE_CLASS_WEIGHTS:
            raise BenchmarkError(f"{source_id} has invalid evidence class")
        if source.get("host") not in allowed_hosts:
            raise BenchmarkError(f"{source_id} host is outside the allowlist")
        if not str(source.get("url") or "").startswith("https://"):
            raise BenchmarkError(f"{source_id} is not HTTPS")
        if not source.get("publicEvidenceBoundary"):
            raise BenchmarkError(f"{source_id} lacks a public evidence boundary")

    return controls, evidence, sources


def evaluate(
    controls_payload: dict[str, Any],
    baseline_payload: dict[str, Any],
    sources_payload: dict[str, Any],
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate JARVIS against the reviewed frontier envelope."""

    now = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
    controls, evidence, sources = _validate(controls_payload, baseline_payload, sources_payload)

    source_states: dict[str, dict[str, Any]] = {}
    for source_id, source in sources.items():
        freshness = _source_freshness(source, now)
        source_states[source_id] = {
            "id": source_id,
            "organization": source.get("organization"),
            "title": source.get("title"),
            "url": source.get("url"),
            "evidenceClass": source.get("evidenceClass"),
            "publicEvidenceBoundary": source.get("publicEvidenceBoundary"),
            **freshness,
        }

    weighted_possible = 0.0
    weighted_alignment = 0.0
    weighted_adjusted = 0.0
    domain_accumulator: dict[str, dict[str, float]] = defaultdict(
        lambda: {"possible": 0.0, "alignment": 0.0, "adjusted": 0.0, "controls": 0.0}
    )
    rows: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    production_proven = 0
    provider_bound_or_better = 0

    for control_id in sorted(controls):
        control = controls[control_id]
        record = evidence[control_id]
        target = int(control["frontierTargetMaturity"])
        current = int(record["maturity"])
        weight = float(control["weight"])
        confidence = float(record["confidence"])
        ratio = current / target
        adjusted_ratio = ratio * confidence
        weighted_possible += weight
        weighted_alignment += weight * ratio
        weighted_adjusted += weight * adjusted_ratio

        domain = str(control["domain"])
        acc = domain_accumulator[domain]
        acc["possible"] += weight
        acc["alignment"] += weight * ratio
        acc["adjusted"] += weight * adjusted_ratio
        acc["controls"] += 1

        if current >= 4:
            provider_bound_or_better += 1
        if current == 5:
            production_proven += 1

        references = [source_states[source_id] for source_id in control["referenceSourceIds"]]
        frontier_confidence = round(
            sum(
                SOURCE_CLASS_WEIGHTS[item["evidenceClass"]]
                * FRESHNESS_WEIGHTS[item["state"]]
                for item in references
            )
            / len(references),
            4,
        )
        gap_points = weight * (1 - ratio)
        row = {
            "controlId": control_id,
            "domain": domain,
            "title": control["title"],
            "weight": weight,
            "currentMaturity": current,
            "currentState": MATURITY_LABELS[current],
            "targetMaturity": target,
            "targetState": MATURITY_LABELS[target],
            "evidenceConfidence": confidence,
            "frontierEvidenceConfidence": frontier_confidence,
            "alignmentPercent": round(ratio * 100, 2),
            "evidenceAdjustedPercent": round(adjusted_ratio * 100, 2),
            "gapPoints": round(gap_points, 4),
            "evidenceGrade": record.get("evidenceGrade"),
            "disposition": record.get("disposition"),
            "evidenceRefs": record.get("evidenceRefs") or [],
            "referenceSourceIds": control["referenceSourceIds"],
            "nextEvidence": record["nextEvidence"],
        }
        rows.append(row)
        if current < target:
            gaps.append({
                "controlId": control_id,
                "domain": domain,
                "title": control["title"],
                "currentState": MATURITY_LABELS[current],
                "targetState": MATURITY_LABELS[target],
                "gapPoints": round(gap_points, 4),
                "nextEvidence": record["nextEvidence"],
            })

    domain_rows = []
    for domain, acc in sorted(domain_accumulator.items()):
        domain_rows.append({
            "domain": domain,
            "controlCount": int(acc["controls"]),
            "alignmentPercent": round(100 * acc["alignment"] / acc["possible"], 2),
            "evidenceAdjustedPercent": round(100 * acc["adjusted"] / acc["possible"], 2),
        })

    source_counts = defaultdict(int)
    for state in source_states.values():
        source_counts[state["state"]] += 1

    report: dict[str, Any] = {
        "schema": "FEDOMEGA-FRONTIER-BENCHMARK-REPORT-1",
        "engineVersion": "1.0.0",
        "generatedAt": instant_text(now),
        "terminalState": "SUCCESS",
        "subject": baseline_payload.get("subject"),
        "scopeBoundary": baseline_payload.get("scopeBoundary"),
        "frontierDefinition": controls_payload.get("frontierDefinition"),
        "truthBoundary": (
            "Public vendor documentation and announcements define comparator capabilities only. "
            "They do not prove private internal practice, and source refresh never promotes JARVIS maturity."
        ),
        "scores": {
            "frontierEnvelopePercent": 100.0,
            "capabilityAlignmentPercent": round(100 * weighted_alignment / weighted_possible, 2),
            "evidenceAdjustedPercent": round(100 * weighted_adjusted / weighted_possible, 2),
            "providerBoundCoveragePercent": round(100 * provider_bound_or_better / len(controls), 2),
            "productionProvenCoveragePercent": round(100 * production_proven / len(controls), 2),
        },
        "sourceFreshness": dict(sorted(source_counts.items())),
        "domains": domain_rows,
        "controls": rows,
        "priorityGaps": sorted(gaps, key=lambda item: (-item["gapPoints"], item["controlId"])),
        "catalogHashes": {
            "controls": digest(controls_payload),
            "baseline": digest(baseline_payload),
            "sources": digest(sources_payload),
        },
    }
    report["reportSha256"] = digest(report)
    return report


def render_markdown(report: dict[str, Any], *, top_gaps: int = 15) -> str:
    scores = report["scores"]
    lines = [
        "# JARVIS Ultimate frontier benchmark",
        "",
        f"**Generated:** {report['generatedAt']}  ",
        f"**Terminal state:** {report['terminalState']}  ",
        f"**Capability alignment:** {scores['capabilityAlignmentPercent']:.2f}%  ",
        f"**Evidence-adjusted alignment:** {scores['evidenceAdjustedPercent']:.2f}%  ",
        f"**Provider-bound coverage:** {scores['providerBoundCoveragePercent']:.2f}%  ",
        f"**Production-proven coverage:** {scores['productionProvenCoveragePercent']:.2f}%",
        "",
        "The comparator is a frontier envelope, not a league table: each control uses the strongest "
        "relevant public practice found across Microsoft, Alphabet/Google, SoftBank and current standards.",
        "",
        f"> Truth boundary: {report['truthBoundary']}",
        "",
        "## Domain benchmark",
        "",
        "| Domain | Controls | Alignment | Evidence-adjusted |",
        "|---|---:|---:|---:|",
    ]
    for row in report["domains"]:
        lines.append(
            f"| {row['domain']} | {row['controlCount']} | {row['alignmentPercent']:.2f}% | "
            f"{row['evidenceAdjustedPercent']:.2f}% |"
        )
    lines.extend([
        "",
        "## Highest-impact remaining evidence gates",
        "",
        "| Control | Domain | Current | Required proof |",
        "|---|---|---|---|",
    ])
    for gap in report["priorityGaps"][:top_gaps]:
        lines.append(
            f"| {gap['controlId']} — {gap['title']} | {gap['domain']} | {gap['currentState']} | "
            f"{gap['nextEvidence']} |"
        )
    lines.extend([
        "",
        "## Source freshness",
        "",
        "| State | Count |",
        "|---|---:|",
    ])
    for state, count in sorted(report["sourceFreshness"].items()):
        lines.append(f"| {state} | {count} |")
    lines.extend([
        "",
        f"Report digest: `{report['reportSha256']}`",
        "",
    ])
    return "\n".join(lines)

