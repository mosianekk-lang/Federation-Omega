from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Sequence

from .core import FidelityError, SCHEMA, isolate_payload


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate canonical fidelity and isolate platform constraints."
    )
    parser.add_argument("--input", required=True, type=Path, help="JSON request path")
    parser.add_argument("--output", type=Path, help="atomic JSON result path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with args.input.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        result = isolate_payload(payload)
    except (OSError, json.JSONDecodeError, FidelityError, TypeError, ValueError) as exc:
        error = {
            "schema": SCHEMA,
            "resultState": "INVALID_INPUT",
            "executionState": "NOT_EXECUTED",
            "error": f"{exc.__class__.__name__}: {exc}",
        }
        print(json.dumps(error, sort_keys=True), file=sys.stderr)
        return 2
    if args.output:
        _write_atomic(args.output, result)
    else:
        json.dump(result, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
