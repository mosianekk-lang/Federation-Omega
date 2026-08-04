#!/usr/bin/env python3
"""Build Phoenix exports with the dual-authority v3.1 exact-lease engine."""

from __future__ import annotations

import argparse
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


def _include(
    source: Path,
    destination: Path,
    export_path: str,
    reason: str,
) -> V2.BASE.FileRecord:
    V2.BASE.copy_file(source, destination / export_path)
    return V2.BASE.FileRecord(
        path=export_path,
        size=source.stat().st_size,
        sha256=V2.BASE.sha256_file(source),
        classification="OPS_INCLUDED",
        reason=reason,
    )


def stage_ops_v3_1(
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
        records.append(
            _include(path, stage, rel, "APPROVED_OPS_TEMPLATE")
        )

    entrypoint = root / "phoenix" / "provider_cutover_v3_1.py"
    base = root / "phoenix" / "provider_cutover_v3.py"
    if not entrypoint.is_file():
        raise RuntimeError(f"Provider cutover v3.1 missing: {entrypoint}")
    if not base.is_file():
        raise RuntimeError(f"Provider cutover v3 base missing: {base}")

    records.append(
        _include(
            entrypoint,
            stage,
            "provider_cutover.py",
            "DUAL_AUTHORITY_PROVIDER_CUTOVER_V3_1_EXACT_LEASE",
        )
    )
    records.append(
        _include(
            base,
            stage,
            "provider_cutover_v3_base.py",
            "VERIFIED_PROVIDER_CUTOVER_V3_BASE",
        )
    )

    actual = {item.path for item in records}
    missing = sorted(set(policy["ops"]["required_files"]) - actual)
    if missing:
        raise RuntimeError(f"Ops export missing required files: {missing}")
    if any(item.path.startswith(".github/workflows/") for item in records):
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

    V2.BASE.stage_ops = stage_ops_v3_1
    receipt = V2.BASE.build(root, output, policy)
    receipt["provider_cutover_engine"] = {
        "version": "3.1",
        "authority_models": [
            "INSTALLATION_TEMPLATE",
            "USER_SCOPED",
        ],
        "installation_template_endpoint": (
            "/repos/mosianekk-lang/Federation-Omega/generate"
        ),
        "template_generated_main_replacement": (
            "EXACT_PROVIDER_BOUND_FORCE_WITH_LEASE"
        ),
        "entrypoint": "provider_cutover.py",
        "base_controller": "provider_cutover_v3_base.py",
        "temporary_template_state_restored": True,
        "credential_value_recorded": False,
    }
    receipt["pst_remote_verifier_dispatch"] = (
        V2.maybe_dispatch_pst_remote_verifier(root)
    )
    receipt_path = output / "phoenix-export-receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
