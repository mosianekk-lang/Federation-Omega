#!/usr/bin/env python3
"""Evidence-backed, dual-axis frontier benchmark and append-only repository.

Capability strength and operational maturity are deliberately separate. Public
vendor documentation can establish potential, but it cannot be treated as
equal-maturity proof that a product was operated in this environment.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable, Mapping


CONTRACT = "SOVARA_FRONTIER_BENCHMARK_KNOWLEDGEBASE_V2"
REPORT_CONTRACT = "SOVARA_FRONTIER_BENCHMARK_REPORT_V2"
REPOSITORY_CONTRACT = "SOVARA_FRONTIER_BENCHMARK_REPOSITORY_V2"
ENGINE_VERSION = "2.0.0"
ALLOWED_TIERS = {
    "LOCAL_PROVIDER_READBACK": 1.0,
    "LOCAL_EXECUTED_EVIDENCE": 0.98,
    "OPEN_SOURCE_UPSTREAM": 0.92,
    "PRIMARY_OFFICIAL_DOCUMENTATION": 0.86,
    "PRIMARY_OFFICIAL_RELEASE": 0.82,
}
ALLOWED_VISIBILITY = {
    "OWNER_FULL_EVIDENCE",
    "PUBLIC_PRODUCT_EVIDENCE",
    "PUBLIC_VISIBILITY_LIMITED",
}


class BenchmarkError(ValueError):
    """Raised when benchmark evidence or repository state is invalid."""


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def parse_date(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise BenchmarkError(f"{field} must be an ISO date") from exc


def parse_datetime(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise BenchmarkError(f"{field} must be an ISO datetime") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_knowledgebase(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    validate_knowledgebase(value)
    return value


def _require_exact_scores(
    system: Mapping[str, Any], key: str, dimension_ids: set[str]
) -> None:
    scores = system.get(key)
    if not isinstance(scores, Mapping) or set(scores) != dimension_ids:
        raise BenchmarkError(f"system {system.get('id')} {key} dimensions do not match")
    for dimension_id, score in scores.items():
        if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 5:
            raise BenchmarkError(
                f"system {system.get('id')} {key}.{dimension_id} must be an integer from 0 to 5"
            )


def validate_knowledgebase(value: Mapping[str, Any]) -> None:
    if value.get("contract") != CONTRACT:
        raise BenchmarkError("wrong knowledgebase contract")
    if value.get("ownerId") != "KIM_KAGISO_MOSIANE":
        raise BenchmarkError("owner identity mismatch")
    parse_date(value.get("asOf"), "asOf")
    if value.get("claimPolicy", {}).get("absoluteOrPerpetualSuperiorityAllowed") is not False:
        raise BenchmarkError("absolute or perpetual superiority must be prohibited")

    dimensions = value.get("dimensions")
    sources = value.get("sources")
    systems = value.get("systems")
    if not isinstance(dimensions, list) or not dimensions:
        raise BenchmarkError("dimensions required")
    if not isinstance(sources, list) or not sources:
        raise BenchmarkError("sources required")
    if not isinstance(systems, list) or not systems:
        raise BenchmarkError("systems required")

    dimension_ids = [item.get("id") for item in dimensions]
    if None in dimension_ids or len(set(dimension_ids)) != len(dimension_ids):
        raise BenchmarkError("dimension IDs must be unique")
    if sum(item.get("weight", 0) for item in dimensions) != 100:
        raise BenchmarkError("dimension weights must sum to 100")
    for dimension in dimensions:
        if not isinstance(dimension.get("weight"), int) or dimension["weight"] <= 0:
            raise BenchmarkError("dimension weights must be positive integers")
        if not dimension.get("definition"):
            raise BenchmarkError(f"dimension {dimension.get('id')} definition required")
    dimension_set = set(dimension_ids)

    source_ids: set[str] = set()
    source_map: dict[str, Mapping[str, Any]] = {}
    for source in sources:
        source_id = source.get("id")
        if not source_id or source_id in source_ids:
            raise BenchmarkError("source IDs must be non-empty and unique")
        source_ids.add(source_id)
        source_map[source_id] = source
        for field in ("publisher", "title", "url", "retrievedAt", "sourceTier"):
            if not source.get(field):
                raise BenchmarkError(f"source {source_id} missing {field}")
        parse_date(source["retrievedAt"], f"source {source_id} retrievedAt")
        if source["sourceTier"] not in ALLOWED_TIERS:
            raise BenchmarkError(f"source {source_id} has unsupported source tier")
        horizon = source.get("freshnessHorizonDays")
        if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon < 1:
            raise BenchmarkError(f"source {source_id} freshness horizon invalid")
        supported = source.get("supportedDimensions")
        if not isinstance(supported, list) or not supported:
            raise BenchmarkError(f"source {source_id} supported dimensions required")
        if not set(supported).issubset(dimension_set):
            raise BenchmarkError(f"source {source_id} references unknown dimensions")
        propositions = source.get("propositions")
        if not isinstance(propositions, list) or not propositions:
            raise BenchmarkError(f"source {source_id} propositions required")
        proposition_ids = [item.get("id") for item in propositions]
        if None in proposition_ids or len(set(proposition_ids)) != len(proposition_ids):
            raise BenchmarkError(f"source {source_id} proposition IDs must be unique")
        if source["url"].startswith("http") and not source["url"].startswith("https://"):
            raise BenchmarkError(f"source {source_id} must use HTTPS")

    system_ids: set[str] = set()
    for system in systems:
        system_id = system.get("id")
        if not system_id or system_id in system_ids:
            raise BenchmarkError("system IDs must be non-empty and unique")
        system_ids.add(system_id)
        if system.get("publicVisibilityState") not in ALLOWED_VISIBILITY:
            raise BenchmarkError(f"system {system_id} visibility state invalid")
        linked_sources = system.get("sourceIds")
        if not isinstance(linked_sources, list) or not linked_sources:
            raise BenchmarkError(f"system {system_id} sources required")
        if not set(linked_sources).issubset(source_ids):
            raise BenchmarkError(f"system {system_id} references unknown sources")
        _require_exact_scores(system, "capabilityScores", dimension_set)
        _require_exact_scores(system, "maturityScores", dimension_set)
        if any(
            system["maturityScores"][dimension_id]
            > system["capabilityScores"][dimension_id]
            for dimension_id in dimension_set
        ):
            raise BenchmarkError(
                f"system {system_id} operational maturity cannot exceed capability"
            )
        for dimension_id, score in system["capabilityScores"].items():
            if score <= 0:
                continue
            supported = any(
                dimension_id in source_map[source_id]["supportedDimensions"]
                for source_id in linked_sources
            )
            if not supported:
                raise BenchmarkError(
                    f"system {system_id} score {dimension_id} lacks linked evidence"
                )
        if system.get("kind") != "OWNER_SYSTEM" and any(
            score > 3 for score in system["maturityScores"].values()
        ):
            raise BenchmarkError(
                f"system {system_id} public evidence cannot establish maturity above 3"
            )

    subject_id = value.get("subjectSystemId")
    if subject_id not in system_ids:
        raise BenchmarkError("subjectSystemId must identify a system")
    subject = next(item for item in systems if item["id"] == subject_id)
    if subject.get("kind") != "OWNER_SYSTEM":
        raise BenchmarkError("subject system must be OWNER_SYSTEM")
    target = value.get("target") or {}
    required = target.get("requiredCapabilityByDimension")
    if set(required or {}) != dimension_set or any(score != 5 for score in required.values()):
        raise BenchmarkError("target must require five in every dimension")


def source_fingerprint(source: Mapping[str, Any]) -> str:
    stable = {
        key: source.get(key)
        for key in (
            "id",
            "publisher",
            "title",
            "url",
            "publishedOrUpdatedAt",
            "sourceTier",
            "supportedDimensions",
            "propositions",
        )
    }
    return canonical_sha256(stable)


def source_evidence(
    source: Mapping[str, Any], *, current_date: date
) -> dict[str, Any]:
    retrieved = parse_date(source["retrievedAt"], "retrievedAt")
    age_days = max(0, (current_date - retrieved).days)
    horizon = int(source["freshnessHorizonDays"])
    if age_days <= horizon:
        freshness = 1.0
        state = "CURRENT"
    elif age_days <= horizon * 2:
        freshness = round(1.0 - (age_days - horizon) / horizon * 0.4, 4)
        state = "AGING"
    else:
        freshness = 0.25
        state = "EXPIRED"
    tier_confidence = ALLOWED_TIERS[source["sourceTier"]]
    return {
        "id": source["id"],
        "publisher": source["publisher"],
        "title": source["title"],
        "url": source["url"],
        "sourceTier": source["sourceTier"],
        "retrievedAt": source["retrievedAt"],
        "ageDays": age_days,
        "freshnessHorizonDays": horizon,
        "freshnessState": state,
        "freshnessFactor": freshness,
        "tierConfidence": tier_confidence,
        "evidenceConfidence": round(freshness * tier_confidence, 4),
        "fingerprint": source_fingerprint(source),
    }


def weighted_axis(
    scores: Mapping[str, int], dimensions: Iterable[Mapping[str, Any]]
) -> float:
    raw = sum(scores[item["id"]] * item["weight"] for item in dimensions)
    return round(raw / 5.0, 2)


def _dimension_confidence(
    system: Mapping[str, Any],
    dimension_id: str,
    source_map: Mapping[str, Mapping[str, Any]],
) -> float:
    candidates = [
        source_map[source_id]["evidenceConfidence"]
        for source_id in system["sourceIds"]
        if dimension_id in source_map[source_id]["supportedDimensions"]
    ]
    return max(candidates, default=0.0)


def compile_report(
    value: Mapping[str, Any],
    *,
    current_date: date | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    validate_knowledgebase(value)
    current_date = current_date or datetime.now(timezone.utc).date()
    observed_at = observed_at or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    observed_at = observed_at.astimezone(timezone.utc)

    dimensions = value["dimensions"]
    evidence = [source_evidence(source, current_date=current_date) for source in value["sources"]]
    evidence_by_id = {item["id"]: item for item in evidence}
    source_contract_by_id = {item["id"]: item for item in value["sources"]}
    systems = value["systems"]
    subject = next(item for item in systems if item["id"] == value["subjectSystemId"])
    commercial = [item for item in systems if item["kind"] != "OWNER_SYSTEM"]

    system_results: list[dict[str, Any]] = []
    for system in systems:
        confidence_by_dimension = {
            dimension["id"]: _dimension_confidence(
                system, dimension["id"],
                {
                    key: {
                        **source_contract_by_id[key],
                        **evidence_by_id[key],
                    }
                    for key in system["sourceIds"]
                },
            )
            for dimension in dimensions
        }
        confidence_weighted = round(
            sum(
                confidence_by_dimension[item["id"]] * item["weight"]
                for item in dimensions
            ),
            2,
        )
        capability = weighted_axis(system["capabilityScores"], dimensions)
        maturity = weighted_axis(system["maturityScores"], dimensions)
        system_results.append(
            {
                "id": system["id"],
                "name": system["name"],
                "company": system["company"],
                "kind": system["kind"],
                "publicVisibilityState": system["publicVisibilityState"],
                "capabilityScore": capability,
                "operationalMaturityScore": maturity,
                "evidenceConfidenceScore": confidence_weighted,
                "confidenceAdjustedCapability": round(
                    capability * confidence_weighted / 100.0, 2
                ),
                "capabilityScores": dict(system["capabilityScores"]),
                "maturityScores": dict(system["maturityScores"]),
                "dimensionConfidence": confidence_by_dimension,
                "sourceIds": list(system["sourceIds"]),
            }
        )
    result_by_id = {item["id"]: item for item in system_results}
    subject_result = result_by_id[subject["id"]]

    envelope: dict[str, Any] = {}
    opportunities: list[dict[str, Any]] = []
    for dimension in dimensions:
        dimension_id = dimension["id"]
        leader_score = max(item["capabilityScores"][dimension_id] for item in commercial)
        leaders = sorted(
            item["id"]
            for item in commercial
            if item["capabilityScores"][dimension_id] == leader_score
        )
        leader_maturity = max(
            item["maturityScores"][dimension_id]
            for item in commercial
            if item["id"] in leaders
        )
        subject_capability = subject["capabilityScores"][dimension_id]
        subject_maturity = subject["maturityScores"][dimension_id]
        capability_gap = max(0, leader_score - subject_capability)
        proof_gap = max(0, leader_maturity - subject_maturity)
        if capability_gap:
            gap_kind = "CAPABILITY_GAP"
        elif proof_gap:
            gap_kind = "EQUAL_MATURITY_PROOF_GAP"
        else:
            gap_kind = "NO_DOCUMENTED_GAP"
        envelope[dimension_id] = {
            "frontierCapability": leader_score,
            "frontierLeaders": leaders,
            "publicLeaderMaturity": leader_maturity,
            "sovaraCapability": subject_capability,
            "sovaraMaturity": subject_maturity,
            "gapKind": gap_kind,
        }
        if gap_kind != "NO_DOCUMENTED_GAP":
            impact = dimension["weight"] * (capability_gap + proof_gap * 0.5)
            if dimension.get("critical") is True:
                impact *= 1.5
            opportunities.append(
                {
                    "dimension": dimension_id,
                    "label": dimension["label"],
                    "critical": dimension.get("critical") is True,
                    "gapKind": gap_kind,
                    "capabilityGap": capability_gap,
                    "maturityGap": proof_gap,
                    "leaders": leaders,
                    "opportunityScore": round(impact, 2),
                    "requiredAction": "OPEN_BOUNDED_MEASURED_EXPERIMENT",
                    "promotionGates": [
                        "failure_first_tests_pass",
                        "matched_workload_baseline",
                        "independent_semantic_proof",
                        "no_critical_dimension_regression",
                        "rollback_or_compensation_proven",
                        "owner_authority_unchanged",
                    ],
                }
            )
    opportunities.sort(
        key=lambda item: (-item["opportunityScore"], item["dimension"])
    )

    frontier_score = round(
        sum(
            envelope[item["id"]]["frontierCapability"] * item["weight"]
            for item in dimensions
        )
        / 5.0,
        2,
    )
    critical_gaps = [item for item in opportunities if item["critical"]]
    expired = [item for item in evidence if item["freshnessState"] == "EXPIRED"]
    if expired:
        state = "UNKNOWN_STALE_EVIDENCE"
    elif any(item["gapKind"] == "CAPABILITY_GAP" for item in critical_gaps):
        state = "MEASURED_GAPS_ACTIVE"
    elif critical_gaps:
        state = "EQUAL_MATURITY_PROOF_GAPS_ACTIVE"
    else:
        state = "FRONTIER_PARITY_CANDIDATE_NOT_SUPERIORITY"

    dataset_fingerprint = canonical_sha256(value)
    source_digest = canonical_sha256(
        {item["id"]: item["fingerprint"] for item in evidence}
    )
    return {
        "contract": REPORT_CONTRACT,
        "engineVersion": ENGINE_VERSION,
        "asOf": value["asOf"],
        "observedAt": observed_at.isoformat().replace("+00:00", "Z"),
        "datasetFingerprint": dataset_fingerprint,
        "sourceDigest": source_digest,
        "snapshotFingerprint": canonical_sha256(
            {
                "engineVersion": ENGINE_VERSION,
                "datasetFingerprint": dataset_fingerprint,
                "sourceDigest": source_digest,
            }
        ),
        "snapshotState": state,
        "snapshotCurrent": not expired,
        "sourceCount": len(evidence),
        "expiredSourceCount": len(expired),
        "dimensionCount": len(dimensions),
        "systemCount": len(systems),
        "subjectSystemId": subject["id"],
        "subject": subject_result,
        "frontierEnvelopeScore": frontier_score,
        "systems": sorted(
            system_results,
            key=lambda item: (-item["capabilityScore"], item["id"]),
        ),
        "frontierEnvelope": envelope,
        "opportunityQueue": opportunities,
        "criticalGapCount": len(critical_gaps),
        "sources": evidence,
        "comparisonRule": "Capability, operational maturity and evidence confidence remain separate axes. Public vendor evidence is not promoted to equal-maturity execution proof.",
        "claimAllowed": False,
        "claimGate": "No absolute or perpetual superiority claim. Any future AHEAD_PROVEN claim requires current evidence, matched workloads, independent live proof, non-regression, and stronger maturity in every critical dimension.",
        "unknownPolicy": "Unobserved private internal practices remain UNKNOWN_PUBLIC_VISIBILITY_LIMITED and receive no inferred score increase.",
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }


def compare_reports(
    previous: Mapping[str, Any] | None, current: Mapping[str, Any]
) -> dict[str, Any]:
    if previous is None:
        return {
            "state": "INITIAL_SNAPSHOT",
            "materialChange": True,
            "changedSystems": [item["id"] for item in current["systems"]],
            "changedDimensions": sorted(current["frontierEnvelope"]),
            "addedSources": [item["id"] for item in current["sources"]],
            "removedSources": [],
        }
    previous_systems = {item["id"]: item for item in previous.get("systems", [])}
    current_systems = {item["id"]: item for item in current["systems"]}
    changed_systems = sorted(
        system_id
        for system_id in set(previous_systems) | set(current_systems)
        if previous_systems.get(system_id) != current_systems.get(system_id)
    )
    previous_envelope = previous.get("frontierEnvelope", {})
    changed_dimensions = sorted(
        dimension_id
        for dimension_id in set(previous_envelope) | set(current["frontierEnvelope"])
        if previous_envelope.get(dimension_id)
        != current["frontierEnvelope"].get(dimension_id)
    )
    previous_sources = {item["id"] for item in previous.get("sources", [])}
    current_sources = {item["id"] for item in current["sources"]}
    material = bool(
        changed_systems
        or changed_dimensions
        or previous.get("sourceDigest") != current.get("sourceDigest")
        or previous.get("snapshotState") != current.get("snapshotState")
    )
    return {
        "state": "MATERIAL_CHANGE" if material else "NO_MATERIAL_CHANGE",
        "materialChange": material,
        "changedSystems": changed_systems,
        "changedDimensions": changed_dimensions,
        "addedSources": sorted(current_sources - previous_sources),
        "removedSources": sorted(previous_sources - current_sources),
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


def _append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, separators=(",", ":")))
        handle.write("\n")


@dataclass(frozen=True)
class RefreshResult:
    state: str
    snapshot_id: str
    snapshot_path: str
    delta_path: str | None
    index_path: str
    material_change: bool


def refresh_repository(
    value: Mapping[str, Any],
    repository: str | Path,
    *,
    current_date: date | None = None,
    observed_at: datetime | None = None,
) -> RefreshResult:
    repository = Path(repository)
    report = compile_report(
        value, current_date=current_date, observed_at=observed_at
    )
    snapshot_id = f"{report['asOf']}-{report['snapshotFingerprint'].split(':', 1)[1][:16]}"
    snapshot_path = repository / "snapshots" / f"{snapshot_id}.json"
    index_path = repository / "index.json"
    journal_path = repository / "refresh-journal.ndjson"

    index: dict[str, Any]
    previous: dict[str, Any] | None = None
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        if index.get("contract") != REPOSITORY_CONTRACT:
            raise BenchmarkError("repository contract mismatch")
        latest_path = index.get("latestSnapshotPath")
        if latest_path:
            previous_file = repository / latest_path
            if not previous_file.exists():
                raise BenchmarkError("repository latest snapshot missing")
            previous = json.loads(previous_file.read_text(encoding="utf-8"))
    else:
        index = {
            "contract": REPOSITORY_CONTRACT,
            "engineVersion": ENGINE_VERSION,
            "snapshots": [],
            "deltas": [],
        }

    delta = compare_reports(previous, report)
    material = delta["materialChange"]
    delta_path: Path | None = None
    if material:
        if snapshot_path.exists():
            existing = json.loads(snapshot_path.read_text(encoding="utf-8"))
            if existing.get("snapshotFingerprint") != report["snapshotFingerprint"]:
                raise BenchmarkError("immutable snapshot collision")
        else:
            _atomic_write_json(snapshot_path, report)
        if previous is not None:
            previous_id = index["latestSnapshotId"]
            delta_id = f"{previous_id}--{snapshot_id}"
            delta_path = repository / "deltas" / f"{delta_id}.json"
            delta_record = {
                "contract": "SOVARA_FRONTIER_BENCHMARK_DELTA_V2",
                "fromSnapshotId": previous_id,
                "toSnapshotId": snapshot_id,
                "observedAt": report["observedAt"],
                **delta,
            }
            if not delta_path.exists():
                _atomic_write_json(delta_path, delta_record)
            relative_delta = str(delta_path.relative_to(repository))
            if relative_delta not in index["deltas"]:
                index["deltas"].append(relative_delta)
        relative_snapshot = str(snapshot_path.relative_to(repository))
        if relative_snapshot not in index["snapshots"]:
            index["snapshots"].append(relative_snapshot)
        index["latestSnapshotId"] = snapshot_id
        index["latestSnapshotPath"] = relative_snapshot
        index["latestSnapshotFingerprint"] = report["snapshotFingerprint"]
        index["updatedAt"] = report["observedAt"]
        _atomic_write_json(index_path, index)

    if material:
        event = {
            "contract": "SOVARA_FRONTIER_REFRESH_EVENT_V2",
            "observedAt": report["observedAt"],
            "state": delta["state"],
            "snapshotId": snapshot_id,
            "snapshotFingerprint": report["snapshotFingerprint"],
            "materialChange": True,
        }
        _append_jsonl(journal_path, event)
    return RefreshResult(
        state=delta["state"],
        snapshot_id=snapshot_id,
        snapshot_path=str(snapshot_path),
        delta_path=str(delta_path) if delta_path else None,
        index_path=str(index_path),
        material_change=material,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="frontier_knowledgebase_v2.json")
    parser.add_argument("--repository")
    parser.add_argument("--report-out")
    parser.add_argument("--current-date")
    parser.add_argument("--observed-at")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = load_knowledgebase(args.dataset)
    current_date = parse_date(args.current_date, "current-date") if args.current_date else None
    observed_at = parse_datetime(args.observed_at, "observed-at") if args.observed_at else None
    report = compile_report(value, current_date=current_date, observed_at=observed_at)
    if args.report_out:
        _atomic_write_json(Path(args.report_out), report)
    result: dict[str, Any] = {
        "decision": "ALLOW" if report["snapshotCurrent"] else "BLOCK_STALE",
        "snapshotState": report["snapshotState"],
        "snapshotFingerprint": report["snapshotFingerprint"],
        "criticalGapCount": report["criticalGapCount"],
        "claimAllowed": False,
    }
    if args.repository:
        refresh = refresh_repository(
            value,
            args.repository,
            current_date=current_date,
            observed_at=observed_at,
        )
        result["repositoryRefresh"] = refresh.__dict__
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.check and not report["snapshotCurrent"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
