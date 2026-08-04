#!/usr/bin/env python3
"""Build Phoenix exports with the dual-authority provider cutover v3 engine."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

V2_SPEC = importlib.util.spec_from_file_location(
    "phoenix_build_exports_v2", ROOT / "phoenix" / "build_exports_v2.py"
)
assert V2_SPEC and V2_SPEC.loader
V2 = importlib.util.module_from_spec(V2_SPEC)
sys.modules[V2_SPEC.name] = V2
V2_SPEC.loader.exec_module(V2)


def stage_ops_v3(
    root: Path, stage: Path, policy: dict
) -> list[V2.BASE.FileRecord]:
    template = root / policy["ops"]["template_prefix"]
    if not template.is_dir():
        raise RuntimeError(f"Ops template missing: {template}")

    records: list[V2.BASE.FileRecord] = []
    for path in sorted(template.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        rel = path.relative_to(template).as_posix()
        V2.BASE.copy_file(path, stage / rel)
        records.append(
            V2.BASE.FileRecord(
                path=rel,
                size=path.stat().st_size,
                sha256=V2.BASE.sha256_file(path),
                classification="OPS_INCLUDED",
                reason="APPROVED_OPS_TEMPLATE",
            )
        )

    cutover = root / "phoenix" / "provider_cutover_v3.py"
    if not cutover.is_file():
        raise RuntimeError(f"Provider cutover v3 missing: {cutover}")
    V2.BASE.copy_file(cutover, stage / "provider_cutover.py")
    records.append(
        V2.BASE.FileRecord(
            path="provider_cutover.py",
            size=cutover.stat().st_size,
            sha256=V2.BASE.sha256_file(cutover),
            classification="OPS_INCLUDED",
            reason="DUAL_AUTHORITY_PROVIDER_CUTOVER_V3",
        )
    )

    actual = {item.path for item in records}
    missing = sorted(set(policy["ops"]["required_files"]) - actual)
    if missing:
        raise RuntimeError(f"Ops export missing required files: {missing}")
    if any(V2.BASE.is_github_workflow_path(item.path) for item in records):
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

    V2.BASE.stage_ops = stage_ops_v3
    receipt = V2.BASE.build(root, output, policy)
    receipt["provider_cutover_engine"] = {
        "version": "3",
        "authority_models": [
            "INSTALLATION_TEMPLATE",
            "USER_SCOPED",
        ],
        "installation_template_endpoint": (
            f"/repos/{receipt.get('source_repository', 'mosianekk-lang/Federation-Omega')}"
            "/generate"
        ),
        "provider_apply_performed": False,
        "temporary_template_state_restoration": "REQUIRED_DURING_APPLY",
        "credential_value_recorded": False,
    }
    receipt["source_mutation_attempted"] = False
    receipt.pop("receipt_sha256", None)
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    receipt["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()

    receipt_path = output / "phoenix-export-receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
