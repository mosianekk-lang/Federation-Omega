"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .benchmark import score_benchmark
from .canary_controller import evaluate_canary
from .context_capsule import build_capsule
from .ledger_head import LedgerHead
from .recovery_snapshot import sign_snapshot, verify_snapshot
from .stream_guard import assess_stream


def _read(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _key() -> bytes:
    value = os.environ.get("CFBE_SNAPSHOT_KEY")
    if not value:
        raise SystemExit("CFBE_SNAPSHOT_KEY is required and is never persisted")
    return value.encode("utf-8")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="cfbe-chatperf")
    sub = root.add_subparsers(dest="command", required=True)
    for command in ("benchmark", "capsule", "stream"):
        item = sub.add_parser(command)
        item.add_argument("input")
    sign = sub.add_parser("snapshot-sign")
    sign.add_argument("input")
    sign.add_argument("--key-id", required=True)
    verify = sub.add_parser("snapshot-verify")
    verify.add_argument("input")
    verify.add_argument("--coverage", action="append", default=[])
    verify.add_argument("--generation", type=int)
    canary = sub.add_parser("canary")
    canary.add_argument("input")
    canary.add_argument("--generation", type=int, required=True)
    ledger = sub.add_parser("ledger-append")
    ledger.add_argument("database")
    ledger.add_argument("input")
    ledger.add_argument("--task", required=True)
    ledger.add_argument("--generation", type=int, required=True)
    ledger.add_argument("--slot", required=True)
    ledger.add_argument("--fence", type=int, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "benchmark":
        result = score_benchmark(_read(args.input))
    elif args.command == "capsule":
        result = build_capsule(_read(args.input))
    elif args.command == "stream":
        result = assess_stream(_read(args.input))
    elif args.command == "snapshot-sign":
        result = sign_snapshot(_read(args.input), _key(), args.key_id)
    elif args.command == "snapshot-verify":
        result = verify_snapshot(_read(args.input), _key(), required_coverage=set(args.coverage), expected_generation=args.generation)
    elif args.command == "canary":
        result = evaluate_canary(_read(args.input), generation=args.generation)
    else:
        result = LedgerHead(args.database).append(task_id=args.task, generation=args.generation, slot=args.slot, fence=args.fence, payload=_read(args.input))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
