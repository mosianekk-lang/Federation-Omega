#!/usr/bin/env python3
"""Build Phoenix exports with the dual-authority v3.1 exact-lease engine."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
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


def _publish_pst_runtime() -> dict[str, object]:
    """Publish bounded verifier runtime settings for later Phoenix steps.

    ``GITHUB_ENV`` is the provider-native channel for exporting values to later
    steps.  The scratch root uses writable ``/tmp``.  ``PYTHONPATH`` exposes a
    narrow bootstrap that strips GitHub bearer authorization only when an
    artifact download redirect crosses from api.github.com to blob storage.
    Local builds and tests remain side-effect free when ``GITHUB_ENV`` is absent.
    """

    scratch_root = os.environ.get(
        "PST_VERIFY_ROOT", "/tmp/pst-composite-verify"
    )
    bootstrap_dir = ROOT / "runtime_bootstrap"
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    pythonpath = str(bootstrap_dir)
    if existing_pythonpath:
        pythonpath = f"{pythonpath}{os.pathsep}{existing_pythonpath}"

    github_env = os.environ.get("GITHUB_ENV")
    published = False
    if github_env:
        env_path = Path(github_env)
        with env_path.open("a", encoding="utf-8") as handle:
            handle.write(f"PST_VERIFY_ROOT={scratch_root}\n")
            handle.write(f"PYTHONPATH={pythonpath}\n")
        published = True
    return {
        "scratch_root": scratch_root,
        "pythonpath_bootstrap": str(bootstrap_dir),
        "github_env_published": published,
        "cross_host_authorization_guard": True,
        "source_mutation_attempted": False,
    }


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
        records.append(_include(path, stage, rel, "APPROVED_OPS_TEMPLATE"))

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

    pst_runtime = _publish_pst_runtime()
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
        "provider_apply_performed": False,
        "temporary_template_state_restoration": "REQUIRED_DURING_APPLY",
        "credential_value_recorded": False,
    }
    receipt["pst_verifier_runtime"] = pst_runtime
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
