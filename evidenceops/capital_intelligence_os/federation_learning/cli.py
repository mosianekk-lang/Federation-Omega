from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .fabric import EventType, LearningFabric


def _load_json(value: str | None, path: str | None) -> dict[str, Any]:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    if value:
        return json.loads(value)
    return {}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Federation Omega continuous learning and trigger capture"
    )
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--policy", required=True)
    sub = parser.add_subparsers(dest="command", required=True)

    capture = sub.add_parser("capture")
    capture.add_argument(
        "--event-type",
        choices=[item.value for item in EventType],
        required=True,
    )
    capture.add_argument("--system-id", required=True)
    capture.add_argument("--workflow-id", required=True)
    capture.add_argument("--mission-id", required=True)
    capture.add_argument("--summary", required=True)
    capture.add_argument("--details-json")
    capture.add_argument("--details-file")
    capture.add_argument("--category")
    capture.add_argument("--source-run-id", default="")
    capture.add_argument("--evidence-ref", action="append", default=[])

    result = sub.add_parser("capture-result")
    result.add_argument("--result-file", required=True)
    result.add_argument("--system-id", required=True)
    result.add_argument("--workflow-id", required=True)
    result.add_argument("--mission-id", required=True)
    result.add_argument("--source-run-id", default="")
    result.add_argument("--evidence-ref", action="append", default=[])

    sub.add_parser("verify")
    sub.add_parser("summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    fabric = LearningFabric(args.workspace, policy_path=args.policy)

    if args.command == "capture":
        details = _load_json(args.details_json, args.details_file)
        payload = fabric.record(
            event_type=args.event_type,
            system_id=args.system_id,
            workflow_id=args.workflow_id,
            mission_id=args.mission_id,
            summary=args.summary,
            details=details,
            category=args.category,
            source_run_id=args.source_run_id,
            evidence_refs=args.evidence_ref,
        )
    elif args.command == "capture-result":
        result = json.loads(Path(args.result_file).read_text(encoding="utf-8"))
        payload = {
            "events": fabric.capture_result(
                result,
                system_id=args.system_id,
                workflow_id=args.workflow_id,
                mission_id=args.mission_id,
                source_run_id=args.source_run_id,
                evidence_refs=args.evidence_ref,
            ),
            "summary": fabric.summary(),
        }
    elif args.command == "verify":
        payload = fabric.verify_chain()
    elif args.command == "summary":
        payload = fabric.summary()
    else:  # pragma: no cover
        raise AssertionError(args.command)

    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    status = payload.get("status") if isinstance(payload, dict) else None
    return 1 if status == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
