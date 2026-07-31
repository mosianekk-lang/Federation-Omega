"""Command-line interface for EvidenceOps Provenance Passports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .core import PassportError, build_passport, build_passports, verify_passport, verify_passports


def _read_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(value: Any, output: str | None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="epp", description="Build and verify EvidenceOps Provenance Passports")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="build one passport from a manifest")
    build.add_argument("manifest")
    build.add_argument("-o", "--output")

    build_many = sub.add_parser("build-many", help="build passports from a JSON array of manifests")
    build_many.add_argument("manifests")
    build_many.add_argument("-o", "--output")

    verify = sub.add_parser("verify", help="verify one passport")
    verify.add_argument("passport")

    verify_many = sub.add_parser("verify-many", help="verify multiple passport files")
    verify_many.add_argument("passports", nargs="+")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            _write_json(build_passport(_read_json(args.manifest)), args.output)
        elif args.command == "build-many":
            manifests = _read_json(args.manifests)
            if not isinstance(manifests, list):
                raise PassportError("build-many input must be a JSON array")
            _write_json(build_passports(manifests), args.output)
        elif args.command == "verify":
            _write_json(verify_passport(_read_json(args.passport)), None)
        elif args.command == "verify-many":
            _write_json(verify_passports(_read_json(path) for path in args.passports), None)
        else:
            raise PassportError("unknown command")
    except (OSError, json.JSONDecodeError, PassportError) as exc:
        sys.stderr.write(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True) + "\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
