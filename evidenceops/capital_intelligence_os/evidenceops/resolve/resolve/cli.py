from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ledger import AppendOnlyLedger
from .transport import reconstruct, segment_file
from .verification import verify_hash, verify_sqlite, verify_zip


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evidenceops-resolve")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("workspace", type=Path)

    segment = sub.add_parser("segment")
    segment.add_argument("source", type=Path)
    segment.add_argument("output_dir", type=Path)
    segment.add_argument("--part-size-mib", type=int, default=90)

    rebuild = sub.add_parser("reconstruct")
    rebuild.add_argument("manifest", type=Path)
    rebuild.add_argument("parts_dir", type=Path)
    rebuild.add_argument("output", type=Path)

    verify = sub.add_parser("verify")
    verify.add_argument("path", type=Path)
    verify.add_argument("--sha256")
    verify.add_argument("--size", type=int)
    verify.add_argument("--zip", action="store_true")
    verify.add_argument("--sqlite", action="store_true")

    audit = sub.add_parser("audit")
    audit.add_argument("workspace", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        args.workspace.mkdir(parents=True, exist_ok=True)
        AppendOnlyLedger(args.workspace / "resolve_ledger.jsonl").append("WORKSPACE_INITIALISED", {"workspace": str(args.workspace)})
        print(json.dumps({"ok": True, "workspace": str(args.workspace)}, indent=2))
        return 0
    if args.command == "segment":
        result = segment_file(args.source, args.output_dir, args.part_size_mib * 1024 * 1024)
    elif args.command == "reconstruct":
        result = reconstruct(args.manifest, args.parts_dir, args.output)
    elif args.command == "verify":
        result = verify_hash(args.path, args.sha256, args.size)
        if args.zip:
            result["zip"] = verify_zip(args.path)
            result["ok"] = result["ok"] and result["zip"]["ok"]
        if args.sqlite:
            result["sqlite"] = verify_sqlite(args.path)
            result["ok"] = result["ok"] and result["sqlite"]["ok"]
    else:
        ledger = AppendOnlyLedger(args.workspace / "resolve_ledger.jsonl")
        discrepancies = AppendOnlyLedger(args.workspace / "discrepancies.jsonl")
        result = {
            "ok": True,
            "ledger_records": len(ledger.read_all()),
            "discrepancies": len(discrepancies.read_all()),
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
