from __future__ import annotations

import argparse
import json
from pathlib import Path

from .canary import run_privacy_safe_canary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omega-cybernetic-v11",
        description="Run deterministic Federation Omega cybernetic control canaries.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    canary = subparsers.add_parser("canary", help="run the privacy-safe synthetic control canary")
    canary.add_argument("--timestamp", default="2026-08-05T23:35:00+02:00")
    canary.add_argument("--previous-receipt-hash")
    canary.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "canary":
        raise AssertionError(f"unhandled command: {args.command}")
    receipt = run_privacy_safe_canary(
        now=args.timestamp,
        previous_receipt_hash=args.previous_receipt_hash,
    )
    payload = json.dumps(receipt.to_dict(), indent=2, sort_keys=True, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
