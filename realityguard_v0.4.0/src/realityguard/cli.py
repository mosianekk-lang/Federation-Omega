"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import RealityGuard
from .learning import LearningLedger, PromotionState
from .redaction import redact
from .schema import InputError
from .taxonomy import FAILURES, TAXONOMY_VERSION
from .upgrade import UpgradeDecisionCode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="realityguard", description="Detect false AI work-state claims before they reach the owner.")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="scan one structured JSON claim")
    scan.add_argument("--input", required=True, type=Path)
    scan.add_argument("--audit-log", type=Path, help="append a redacted JSONL decision record")
    resolve = sub.add_parser("resolve", help="scan truth and route the preserved objective through existing capabilities")
    resolve.add_argument("--input", required=True, type=Path)
    resolve.add_argument("--capabilities", required=True, type=Path)
    prebuild = sub.add_parser("prebuild", help="block duplicate builds and authorize only reuse or a proven residual gap")
    prebuild.add_argument("--input", required=True, type=Path)
    prebuild.add_argument("--capabilities", required=True, type=Path)
    upgrade = sub.add_parser("upgrade", help="automatically assess a material cycle and select a governed reuse-first upgrade route")
    upgrade.add_argument("--input", required=True, type=Path)
    upgrade.add_argument("--capabilities", required=True, type=Path)
    learn = sub.add_parser("learn", help="record one governed incident in the deduplicated local learning ledger")
    learn.add_argument("--incident", required=True, type=Path)
    learn.add_argument("--ledger", required=True, type=Path)
    learn.add_argument("--promotion-state", choices=[state.name for state in PromotionState], default="DETECTED")
    learn.add_argument("--regression-test", action="append", default=[])
    learn.add_argument("--dry-run", action="store_true")
    sub.add_parser("taxonomy", help="print the versioned failure taxonomy")
    sub.add_parser("health", help="run a dependency-free health check")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "health":
        print(json.dumps({"status": "ok", "engine": "RealityGuard", "version": "0.4.0", "mode": "offline-deterministic", "automatic_upgrade": "host-invoked-material-cycles", "external_bindings": False}, sort_keys=True))
        return 0
    if args.command == "taxonomy":
        print(json.dumps({"version": TAXONOMY_VERSION, "failures": {key: {"title": val[0], "definition": val[1]} for key, val in FAILURES.items()}}, indent=2, sort_keys=True))
        return 0
    if args.command == "learn":
        try:
            incident = json.loads(args.incident.read_text(encoding="utf-8"))
            receipt = LearningLedger(args.ledger).record(
                incident,
                promotion_state=PromotionState[args.promotion_state],
                regression_tests=tuple(args.regression_test),
                dry_run=args.dry_run,
            ).to_dict()
        except (OSError, json.JSONDecodeError, InputError) as exc:
            print(json.dumps({"error": "INVALID_INPUT", "message": str(exc)}), file=sys.stderr)
            return 2
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if args.command == "resolve":
            manifest = json.loads(args.capabilities.read_text(encoding="utf-8"))
            result = RealityGuard().resolve(payload, manifest)
        elif args.command == "prebuild":
            manifest = json.loads(args.capabilities.read_text(encoding="utf-8"))
            result = RealityGuard().prebuild(payload, manifest)
        elif args.command == "upgrade":
            manifest = json.loads(args.capabilities.read_text(encoding="utf-8"))
            result = RealityGuard().upgrade(payload, manifest)
        else:
            result = RealityGuard().scan(payload).to_dict()
    except (OSError, json.JSONDecodeError, InputError) as exc:
        print(json.dumps({"error": "INVALID_INPUT", "message": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.command == "scan" and args.audit_log:
        args.audit_log.parent.mkdir(parents=True, exist_ok=True)
        record = {"input": redact(payload), "result": result}
        with args.audit_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    if args.command == "prebuild":
        return 0 if result["proposed_action_authorized"] else 4
    if args.command == "upgrade":
        blocked = {
            UpgradeDecisionCode.BLOCK_DUPLICATE_UPGRADE.value,
            UpgradeDecisionCode.BLOCK_UNSAFE_UPGRADE.value,
        }
        return 5 if result["decision"] in blocked else 0
    verdict = result["truth"]["verdict"] if args.command == "resolve" else result["verdict"]
    return 0 if verdict == "ALLOW_BOUNDED" else 3


if __name__ == "__main__":
    raise SystemExit(main())
