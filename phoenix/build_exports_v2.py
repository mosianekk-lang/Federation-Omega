#!/usr/bin/env python3
"""Build Phoenix exports with the user-scoped provider cutover v2 engine."""

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
    if not cutover.is_file():
        raise RuntimeError(f"Provider cutover v2 missing: {cutover}")
    BASE.copy_file(cutover, stage / "provider_cutover.py")
    records.append(
        BASE.FileRecord(
            path="provider_cutover.py",
            size=cutover.stat().st_size,
            sha256=BASE.sha256_file(cutover),
            classification="OPS_INCLUDED",
            reason="USER_SCOPED_PROVIDER_CUTOVER_V2",
        )
    )

    actual = {item.path for item in records}
    missing = sorted(set(policy["ops"]["required_files"]) - actual)
    if missing:
        raise RuntimeError(f"Ops export missing required files: {missing}")
    if any(BASE.is_github_workflow_path(item.path) for item in records):
        raise RuntimeError("Ops export unexpectedly contains an active workflow")
    return records


def build_v2(root: Path, output: Path, policy: Path) -> dict:
    """Create a side-effect-free v2 export and complete receipt."""

    BASE.stage_ops = stage_ops_v2
    receipt = BASE.build(root, output, policy)
    receipt["provider_cutover_engine"] = {
        "version": "2",
        "authority_models": ["USER_SCOPED"],
        "entrypoint": "provider_cutover.py",
        "provider_apply_performed": False,
        "credential_value_recorded": False,
    }
    receipt["export_generation"] = {
        "side_effect_free": True,
        "provider_dispatch_performed": False,
        "provider_mutation_performed": False,
    }
    return BASE.publish_receipt(output / "phoenix-export-receipt.json", receipt)


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

    receipt = build_v2(root, output, policy)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
