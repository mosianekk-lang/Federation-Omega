from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import (
    ImpactCompiler,
    ProofCache,
    ProofPolicy,
    ProofRunner,
    ProofSelector,
    changed_paths_from_git,
    load_manifest,
)


def _write_json(path: str | Path, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def compile_command(args: argparse.Namespace) -> int:
    policy = ProofPolicy.from_path(args.policy)
    if args.changed_file:
        changed_paths = [line.strip() for line in Path(args.changed_file).read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        changed_paths = changed_paths_from_git(args.repo_root, args.base, args.head)
    impact = ImpactCompiler(policy).assess(changed_paths)
    manifest = ProofSelector(policy).compile_manifest(
        base_sha=args.base,
        head_sha=args.head,
        impact=impact,
    )
    _write_json(args.output, manifest.to_dict())
    print(
        "PROOFOS_MANIFEST"
        f" sha256={manifest.manifest_sha256}"
        f" risk={manifest.impact.risk.name}"
        f" selected={len(manifest.selected_tests)}"
        f" omitted={len(manifest.omitted_tests)}"
        f" unmapped={len(manifest.impact.unmapped_production_paths)}"
    )
    return 0


def run_command(args: argparse.Namespace) -> int:
    policy = ProofPolicy.from_path(args.policy)
    manifest = load_manifest(args.manifest)
    cache = ProofCache(args.cache_dir) if args.cache_dir else None
    report = ProofRunner(policy=policy, repo_root=args.repo_root, cache=cache).run(manifest)
    _write_json(args.output, report.to_dict())
    print(
        "PROOFOS_ADMISSION"
        f" status={report.status}"
        f" manifest={report.manifest_sha256}"
        f" report={report.report_sha256}"
        f" tests={len(report.results)}"
        f" failures={len(report.blocking_failures)}"
    )
    return 0 if report.status == "PASS" else 1


def verify_command(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    policy = ProofPolicy.from_path(args.policy)
    if manifest.policy_sha256 != policy.sha256:
        print("PROOFOS_VERIFY policy_hash_mismatch", file=sys.stderr)
        return 1
    if not manifest.selector_state.get("omission_proof_complete"):
        print("PROOFOS_VERIFY omission_proof_incomplete", file=sys.stderr)
        return 1
    print(
        "PROOFOS_VERIFY"
        f" status=PASS manifest={manifest.manifest_sha256}"
        f" graph={manifest.impact.graph_sha256}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="proofos-omega")
    sub = parser.add_subparsers(dest="command", required=True)

    compile_parser = sub.add_parser("compile", help="compile a hash-bound proof manifest")
    compile_parser.add_argument("--policy", required=True)
    compile_parser.add_argument("--base", required=True)
    compile_parser.add_argument("--head", required=True)
    compile_parser.add_argument("--repo-root", default=".")
    compile_parser.add_argument("--changed-file")
    compile_parser.add_argument("--output", required=True)
    compile_parser.set_defaults(func=compile_command)

    run_parser = sub.add_parser("run", help="execute only the manifest-selected proof set")
    run_parser.add_argument("--policy", required=True)
    run_parser.add_argument("--manifest", required=True)
    run_parser.add_argument("--repo-root", default=".")
    run_parser.add_argument("--cache-dir")
    run_parser.add_argument("--output", required=True)
    run_parser.set_defaults(func=run_command)

    verify_parser = sub.add_parser("verify", help="verify manifest integrity and proof completeness")
    verify_parser.add_argument("--policy", required=True)
    verify_parser.add_argument("--manifest", required=True)
    verify_parser.set_defaults(func=verify_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"PROOFOS_ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
