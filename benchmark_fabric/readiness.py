"""Deterministic, proof-gated JARVIS operational readiness evaluation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LEVEL_IDS = tuple(f"R{rank}" for rank in range(7))
CRITICALITY_WEIGHT = {"CRITICAL": 100, "HIGH": 70, "MEDIUM": 40, "LOW": 10}


def _load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def validate(standard: dict[str, Any], assessment: dict[str, Any]) -> None:
    errors: list[str] = []
    level_ids = tuple(item.get("id") for item in standard.get("levels", []))
    if level_ids != LEVEL_IDS:
        errors.append("levels must be the ordered canonical sequence R0..R6")
    if standard.get("scoreViewPolicy", {}).get("allowCombinedScore") is not False:
        errors.append("score views must explicitly prohibit a combined score")
    if "combinedScore" in assessment:
        errors.append("assessment must not contain combinedScore")

    category_ids = [item.get("id") for item in standard.get("categories", [])]
    if not category_ids or None in category_ids or len(category_ids) != len(set(category_ids)):
        errors.append("category identifiers must be present and unique")
    component_ids = [item.get("id") for item in assessment.get("components", [])]
    if not component_ids or None in component_ids or len(component_ids) != len(set(component_ids)):
        errors.append("component identifiers must be present and unique")
    known_components = set(component_ids)
    known_categories = set(category_ids)

    for component in assessment.get("components", []):
        component_id = component.get("id", "<unknown>")
        current = component.get("currentLevel")
        target = component.get("targetLevel")
        if current not in LEVEL_IDS or target not in LEVEL_IDS:
            errors.append(f"{component_id}: currentLevel and targetLevel must be R0..R6")
        elif LEVEL_IDS.index(current) > LEVEL_IDS.index(target):
            errors.append(f"{component_id}: currentLevel exceeds targetLevel")
        if component.get("categoryId") not in known_categories:
            errors.append(f"{component_id}: unknown categoryId")
        if component.get("criticality") not in CRITICALITY_WEIGHT:
            errors.append(f"{component_id}: invalid criticality")
        if current != "R0" and not component.get("evidence"):
            errors.append(f"{component_id}: non-zero readiness requires evidence")

    profile_ids: set[str] = set()
    for profile in standard.get("releaseProfiles", []):
        profile_id = profile.get("id")
        if not profile_id or profile_id in profile_ids:
            errors.append("release profile identifiers must be present and unique")
        profile_ids.add(profile_id)
        refs = profile.get("criticalComponentIds") or []
        if not refs:
            errors.append(f"{profile_id}: criticalComponentIds cannot be empty")
        unknown = sorted(set(refs) - known_components)
        if unknown:
            errors.append(f"{profile_id}: unknown components: {','.join(unknown)}")

    view_ids = [item.get("id") for item in assessment.get("scoreViews", [])]
    if len(view_ids) != len(set(view_ids)):
        errors.append("score view identifiers must be unique")
    required_views = set(standard.get("scoreViewPolicy", {}).get("requiredViews", []))
    if set(view_ids) != required_views:
        errors.append("assessment score views do not match the canonical view set")
    if errors:
        raise ValueError("; ".join(errors))


def _verified_evidence(component: dict[str, Any], kind: str, as_of: datetime, max_age_days: int | None) -> bool:
    for item in component.get("evidence", []):
        if item.get("kind") != kind or item.get("status") != "VERIFIED" or not item.get("proofRef"):
            continue
        if max_age_days is None:
            return True
        try:
            age = (as_of - _instant(item["verifiedAt"])).total_seconds() / 86400
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= age <= max_age_days:
            return True
    return False


def _effective_level(
    component: dict[str, Any], standard: dict[str, Any], assessment: dict[str, Any], as_of: datetime
) -> tuple[str, list[str]]:
    rank = LEVEL_IDS.index(component["currentLevel"])
    reasons: list[str] = []
    rules = {item["eventType"]: item for item in standard.get("demotionRules", [])}
    for event in assessment.get("failureEvents", []):
        if event.get("status") != "ACTIVE" or event.get("componentId") != component["id"]:
            continue
        rule = rules.get(event.get("eventType"))
        if rule:
            demotion_rank = LEVEL_IDS.index(rule["demoteTo"])
            if demotion_rank < rank:
                rank = demotion_rank
            reasons.append(event["eventType"])

    freshness = standard.get("freshnessPolicy", {})
    if rank >= LEVEL_IDS.index(freshness.get("appliesFromLevel", "R4")):
        kinds = freshness.get("requiredEvidenceKinds", [])
        max_age = int(freshness.get("maximumAgeDays", 30))
        if not any(_verified_evidence(component, kind, as_of, max_age) for kind in kinds):
            demotion_rank = LEVEL_IDS.index(freshness.get("demoteTo", "R3"))
            rank = min(rank, demotion_rank)
            reasons.append("evidence_stale_or_missing")
    return LEVEL_IDS[rank], sorted(set(reasons))


def evaluate(standard: dict[str, Any], assessment: dict[str, Any]) -> dict[str, Any]:
    validate(standard, assessment)
    as_of = _instant(assessment["assessedAt"])
    gates = {item["level"]: item for item in standard.get("promotionGates", [])}
    components: list[dict[str, Any]] = []

    for source in assessment["components"]:
        effective, demotion_reasons = _effective_level(source, standard, assessment, as_of)
        current_rank = LEVEL_IDS.index(effective)
        target_rank = LEVEL_IDS.index(source["targetLevel"])
        next_level = LEVEL_IDS[current_rank + 1] if current_rank < target_rank else None
        gate = gates.get(next_level, {}) if next_level else {}
        max_age = gate.get("maximumAgeDays")
        missing = [
            kind
            for kind in gate.get("requiredEvidenceKinds", [])
            if not _verified_evidence(source, kind, as_of, max_age)
        ]
        blockers = list(source.get("blockers", []))
        eligible = bool(next_level) and not missing and not blockers and not demotion_reasons
        gap = target_rank - current_rank
        priority = CRITICALITY_WEIGHT[source["criticality"]] + gap * 10 + len(blockers) * 2 + len(missing)
        components.append(
            {
                "id": source["id"],
                "name": source["name"],
                "categoryId": source["categoryId"],
                "criticality": source["criticality"],
                "declaredLevel": source["currentLevel"],
                "effectiveLevel": effective,
                "targetLevel": source["targetLevel"],
                "demotionReasons": demotion_reasons,
                "nextLevel": next_level,
                "promotionEligible": eligible,
                "missingEvidenceKinds": missing,
                "blockers": blockers,
                "nextGate": source.get("nextGate"),
                "priority": priority,
                "evidenceRefs": [item.get("proofRef") for item in source.get("evidence", []) if item.get("proofRef")],
            }
        )

    by_id = {item["id"]: item for item in components}
    profiles: list[dict[str, Any]] = []
    for profile in standard["releaseProfiles"]:
        critical = [by_id[item] for item in profile["criticalComponentIds"]]
        rank = min(LEVEL_IDS.index(item["effectiveLevel"]) for item in critical)
        bottlenecks = sorted(item["id"] for item in critical if LEVEL_IDS.index(item["effectiveLevel"]) == rank)
        profiles.append(
            {
                "id": profile["id"],
                "name": profile["name"],
                "readiness": LEVEL_IDS[rank],
                "target": profile["targetLevel"],
                "decisionRule": "MINIMUM_EFFECTIVE_LEVEL_ACROSS_CRITICAL_COMPONENTS",
                "bottlenecks": bottlenecks,
                "promotionBlocked": rank < LEVEL_IDS.index(profile["targetLevel"]),
            }
        )

    backlog = sorted(
        (
            {
                "componentId": item["id"],
                "priority": item["priority"],
                "currentLevel": item["effectiveLevel"],
                "targetLevel": item["targetLevel"],
                "nextLevel": item["nextLevel"],
                "promotionEligible": item["promotionEligible"],
                "missingEvidenceKinds": item["missingEvidenceKinds"],
                "blockers": item["blockers"],
                "nextGate": item["nextGate"],
            }
            for item in components
            if item["nextLevel"]
        ),
        key=lambda item: (-item["priority"], item["componentId"]),
    )
    return {
        "schema": "FEDOMEGA-JARVIS-READINESS-REPORT-1",
        "standardVersion": standard["version"],
        "assessedAt": assessment["assessedAt"],
        "scoreViewPolicy": {
            "combinedScore": None,
            "rule": "NEVER_AVERAGE_OR_SUBSTITUTE_SCORE_VIEWS",
        },
        "scoreViews": assessment["scoreViews"],
        "releaseProfiles": profiles,
        "components": components,
        "promotionBacklog": backlog,
        "summary": {
            "componentCount": len(components),
            "categoryCount": len(standard["categories"]),
            "profileCount": len(profiles),
            "promotionEligibleCount": sum(1 for item in components if item["promotionEligible"]),
            "demotedComponentCount": sum(1 for item in components if item["demotionReasons"]),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# JARVIS Readiness Assessment",
        "",
        f"Assessed: `{report['assessedAt']}` · Standard: `{report['standardVersion']}`",
        "",
        "> Score views are deliberately separate. No combined or averaged score is valid.",
        "",
        "## Release profiles",
        "",
        "| Profile | Current | Target | Bottlenecks |",
        "|---|---:|---:|---|",
    ]
    for profile in report["releaseProfiles"]:
        lines.append(f"| {profile['name']} | {profile['readiness']} | {profile['target']} | {', '.join(profile['bottlenecks'])} |")
    lines += ["", "## Separate score views", "", "| View | Raw | Evidence-adjusted | Scope |", "|---|---:|---:|---|"]
    for view in report["scoreViews"]:
        lines.append(f"| {view['name']} | {view.get('raw', 'n/a')} | {view.get('evidenceAdjusted', 'n/a')} | {view['scope']} |")
    lines += ["", "## Promotion backlog", "", "| Priority | Component | Current → Next → Target | Missing proof / blockers |", "|---:|---|---|---|"]
    for item in report["promotionBacklog"]:
        gaps = item["missingEvidenceKinds"] + item["blockers"]
        lines.append(f"| {item['priority']} | {item['componentId']} | {item['currentLevel']} → {item['nextLevel']} → {item['targetLevel']} | {'; '.join(gaps) or 'gate complete'} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standard", default="benchmark_fabric/catalog/readiness_standard.json")
    parser.add_argument("--assessment", default="benchmark_fabric/evidence/readiness_assessment_2026-08-22.json")
    parser.add_argument("--output", default="/tmp/jarvis-readiness")
    args = parser.parse_args()
    report = evaluate(_load(args.standard), _load(args.assessment))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "readiness-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "readiness-report.md").write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
