"""Command-line interface for EvidenceOps Provenance Passports."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from .core import (
    PassportValidationError,
    build_record_passport,
    validate_many,
    validate_passport,
)


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PassportValidationError(f"cannot read JSON from {path}: {exc}") from exc


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evidenceops-passport",
        description="Build and verify EvidenceOps Provenance Passports.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify", help="verify one passport")
    verify.add_argument("passport", type=Path)

    batch = subparsers.add_parser("verify-batch", help="verify multiple passports")
    batch.add_argument("passports", nargs="+", type=Path)

    build = subparsers.add_parser(
        "build-records",
        help="build a V2 passport from an ordered JSON records manifest",
    )
    build.add_argument("manifest", type=Path)
    build.add_argument("output", type=Path)
    build.add_argument("--passport-id", required=True)
    build.add_argument(
        "--classification",
        default="PRIVATE_EVIDENCE_METADATA",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            result = validate_passport(_read_json(args.passport)).as_dict()
            print(json.dumps(result, indent=2))
            return 0 if result["valid"] else 1

        if args.command == "verify-batch":
            batch = validate_many([_read_json(path) for path in args.passports])
            print(json.dumps(batch, indent=2))
            return 0 if batch["valid"] else 1

        manifest = _read_json(args.manifest)
        records = manifest.get("records")
        source = manifest.get("source")
        if not isinstance(records, list) or not isinstance(source, dict):
            raise PassportValidationError(
                "record manifest must contain an object 'source' and array 'records'"
            )
        passport = build_record_passport(
            records=records,
            passport_id=args.passport_id,
            source=source,
            classification=args.classification,
        )
        _write_json(args.output, passport)
        print(json.dumps(validate_passport(passport).as_dict(), indent=2))
        return 0
    except PassportValidationError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, indent=2))
        return 2


if __name__ == "__main__":
    sys.exit(main())
