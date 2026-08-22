"""Command-line entry point for benchmark evaluation and source refresh."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .engine import evaluate, instant_text, load_json, render_markdown
from .fetcher import refresh_all


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTROLS = ROOT / "catalog" / "frontier_controls.json"
DEFAULT_SOURCES = ROOT / "catalog" / "official_sources.json"
DEFAULT_BASELINE = ROOT / "evidence" / "jarvis_baseline_2026-08-22.json"


def _instant(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _write_report(output: Path, report: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "benchmark-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "benchmark-report.md").write_text(render_markdown(report), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Federation Omega frontier benchmark fabric")
    parser.add_argument("--controls", type=Path, default=DEFAULT_CONTROLS)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--as-of", help="RFC3339 evaluation/refresh time")
    parser.add_argument(
        "--refresh-official-sources",
        action="store_true",
        help="perform the HTTPS-only read-only official-source refresh",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    now = _instant(args.as_of)
    controls = load_json(args.controls)
    sources = load_json(args.sources)
    baseline = load_json(args.baseline)
    report = evaluate(controls, baseline, sources, as_of=now)
    _write_report(args.output, report)

    terminal = "SUCCESS"
    if args.refresh_official_sources:
        manifest = refresh_all(sources, args.output, fetched_at=now)
        terminal = manifest["terminalState"]

    summary = {
        "generatedAt": instant_text(now),
        "terminalState": terminal,
        "benchmarkReportSha256": report["reportSha256"],
        "capabilityAlignmentPercent": report["scores"]["capabilityAlignmentPercent"],
        "evidenceAdjustedPercent": report["scores"]["evidenceAdjustedPercent"],
        "providerBoundCoveragePercent": report["scores"]["providerBoundCoveragePercent"],
        "productionProvenCoveragePercent": report["scores"]["productionProvenCoveragePercent"],
        "repositoryMutationAttempted": False,
    }
    (args.output / "run-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    return 0 if terminal == "SUCCESS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
