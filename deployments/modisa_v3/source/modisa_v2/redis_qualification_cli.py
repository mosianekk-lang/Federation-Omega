"""Safe, plan-only command line entry point for Redis qualification."""

from __future__ import annotations

import argparse
import json
import sys
from importlib.resources import files
from pathlib import Path

from . import __version__
from .redis_qualification import RedisQualificationRunner, RunMode, RunnerConfig, write_receipt


def source_hashes() -> dict[str, str]:
    raw = files("modisa_v2").joinpath("redis_qualification_sources.json").read_text(
        encoding="utf-8"
    )
    value = json.loads(raw)
    if not isinstance(value, dict) or set(value) != {"lock", "package", "runner"}:
        raise RuntimeError("Qualification source hashes are invalid")
    return {str(name): str(digest) for name, digest in value.items()}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Plan MODISA Redis live qualification safely")
    value.add_argument("--version", action="version", version=__version__)
    value.add_argument("--mode", choices=[RunMode.PLAN.value], default=RunMode.PLAN.value)
    value.add_argument("--output", type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    receipt = RedisQualificationRunner(
        RunnerConfig(mode=RunMode.PLAN, source_hashes=source_hashes())
    ).run()
    if args.output is not None:
        write_receipt(args.output, receipt)
    json.dump(receipt, sys.stdout, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
