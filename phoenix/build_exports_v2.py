#!/usr/bin/env python3
"""Build Phoenix exports with the retired-provider-effect v2 compatibility route."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phoenix_build_exports_base", ROOT / "phoenix" / "build_exports.py"
)
assert SPEC and SPEC.loader
BASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BASE
SPEC.loader.exec_module(BASE)


def stage_ops_v2(root: Path, stage: Path, policy: dict) -> list[BASE.FileRecord]:
    template = root / policy["ops"]["template_prefix"]
    if not template.is_dir():
        raise RuntimeError(f"Ops template missing: {template}")

    records: list[BASE.FileRecord] = []
    for path in sorted(template.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        rel = path.relative_to(template).as_posix()
        BASE.copy_file(path, stage / rel)
        records.append(
            BASE.FileRecord(
                path=rel,
                size=path.stat().st_size,
                sha256=BASE.sha256_file(path),
                classification="OPS_INCLUDED",
                reason="APPROVED_OPS_TEMPLATE",
            )
        )

    cutover = root / "phoenix" / "provider_cutover_v2.py"
    engine = root / "phoenix" / "provider_cutover_v2_engine.py"
    for label, path in (("Provider cutover v2 wrapper", cutover), ("Provider cutover v2 engine", engine)):
        if not path.is_file():
            raise RuntimeError(f"{label} missing: {path}")

    for source, export_path, reason in (
        (cutover, "provider_cutover.py", "V2_PROVIDER_EFFECT_RETIRED_COMPATIBILITY_BOUNDARY"),
        (engine, "provider_cutover_v2_engine.py", "V2_PRESERVED_DRY_RUN_ENGINE"),
    ):
        BASE.copy_file(source, stage / export_path)
        records.append(
            BASE.FileRecord(
                path=export_path,
                size=source.stat().st_size,
                sha256=BASE.sha256_file(source),
                classification="OPS_INCLUDED",
                reason=reason,
            )
        )

    actual = {item.path for item in records}
    missing = sorted(set(policy["ops"]["required_files"]) - actual)
    if missing:
        raise RuntimeError(f"Ops export missing required files: {missing}")
    if any(BASE.is_github_workflow_path(item.path) for item in records):
        raise RuntimeError("Ops export unexpectedly contains an active workflow")
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--policy", type=Path, default=Path("phoenix/export_policy.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("phoenix-export-output")
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()
    policy = args.policy if args.policy.is_absolute() else root / args.policy
    output = args.output if args.output.is_absolute() else root / args.output

    BASE.stage_ops = stage_ops_v2
    receipt = BASE.build(root, output, policy)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
