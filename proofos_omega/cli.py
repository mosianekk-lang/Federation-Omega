from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from .core import (
    ProofCache,
    ProofRunner,
    ProofSelector,
    changed_paths_from_git,
    load_manifest,
)
from .hermetic import enforce_hermetic_fallback, run_hermetic_r5_fallback
from .policy import ProofPolicy
from .impact import ImpactCompiler


_DIAGNOSTIC_MAX_CHARS = 12000
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_AUTH_VALUE_RE = re.compile(r"(?i)\b(?:bearer|token)\s+[A-Za-z0-9._~+/=-]{6,}")
_SECRET_VALUE_RES = (
    re.compile(r"\b(?:sk-(?:proj-|or-v1-|ant-)?|github_pat_|gh[pousr]_)[A-Za-z0-9_.-]{6,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(token|secret|password|api[_-]?key|authorization|cookie)\b(\s*[:=]\s*)([^\r\n]+)"
)


def _write_json(path: str | Path, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _redact_diagnostic(text: str) -> str:
    """Return a bounded, secret-scrubbed diagnostic while preserving the traceback tail."""
    value = _ANSI_ESCAPE_RE.sub("", text)
    value = _AUTH_VALUE_RE.sub("[REDACTED_AUTH]", value)
    for pattern in _SECRET_VALUE_RES:
        value = pattern.sub("[REDACTED_SECRET]", value)
    value = _SECRET_ASSIGNMENT_RE.sub(r"\1\2[REDACTED]", value)
    if len(value) > _DIAGNOSTIC_MAX_CHARS:
        value = (
            f"[...diagnostic truncated to last {_DIAGNOSTIC_MAX_CHARS} characters...]\n"
            + value[-_DIAGNOSTIC_MAX_CHARS:]
        )
    return value


def _diagnostic_argv(spec) -> list[str] | None:
    """Reconstruct only already-admitted deterministic ProofOS court kinds."""
    if spec.kind == "unittest_glob":
        return [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            spec.target,
            "-v",
        ]
    if spec.kind == "unittest_module":
        return [sys.executable, "-m", "unittest", spec.target, "-v"]
    if spec.kind == "compileall":
        return [sys.executable, "-m", "compileall", "-q", spec.target]
    return None


def _emit_failure_diagnostics(*, policy: ProofPolicy, report, repo_root: str | Path) -> None:
    """Emit failure-only diagnostics without changing authoritative ProofOS evidence.

    The authoritative court has already executed and its hashes remain unchanged in
    the immutable admission report. This observability pass reruns only failed,
    policy-registered deterministic courts and writes a bounded/redacted excerpt to
    stderr. Diagnostic failure can never turn an admission failure into success or
    change its failure class.
    """
    root = Path(repo_root)
    for result in report.results:
        if result.status.startswith("PASS") or result.status.startswith("SKIPPED"):
            continue
        spec = policy.tests.get(result.test_id)
        argv = _diagnostic_argv(spec) if spec is not None else None
        if argv is None:
            continue
        diagnostic = ""
        diagnostic_status = "RERUN_COMPLETED"
        try:
            process = subprocess.run(
                argv,
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=spec.timeout_seconds,
                check=False,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            diagnostic = _redact_diagnostic(
                (process.stdout or "") + (process.stderr or "")
            )
        except subprocess.TimeoutExpired as exc:
            stdout = (
                exc.stdout.decode(errors="replace")
                if isinstance(exc.stdout, bytes)
                else (exc.stdout or "")
            )
            stderr = (
                exc.stderr.decode(errors="replace")
                if isinstance(exc.stderr, bytes)
                else (exc.stderr or "")
            )
            diagnostic_status = "RERUN_TIMEOUT"
            diagnostic = _redact_diagnostic(
                stdout + stderr + "\n[diagnostic rerun timed out]"
            )
        except Exception as exc:
            diagnostic_status = "RERUN_UNAVAILABLE"
            diagnostic = f"[diagnostic rerun unavailable: {type(exc).__name__}]"
        print(
            "PROOFOS_DIAGNOSTIC_BEGIN"
            f" test_id={result.test_id}"
            f" authoritative_status={result.status}"
            f" authoritative_returncode={result.returncode}"
            f" diagnostic_status={diagnostic_status}",
            file=sys.stderr,
        )
        if diagnostic:
            print(diagnostic, file=sys.stderr)
        print(f"PROOFOS_DIAGNOSTIC_END test_id={result.test_id}", file=sys.stderr)


def _emit_hermetic_failure(execution) -> None:
    if execution is None or execution.result.status.startswith("PASS"):
        return
    diagnostic = _redact_diagnostic(
        (execution.stdout or b"").decode(errors="replace")
        + (execution.stderr or b"").decode(errors="replace")
    )
    print(
        "PROOFOS_HERMETIC_R5_DIAGNOSTIC_BEGIN"
        f" test_id={execution.result.test_id}"
        f" status={execution.result.status}"
        f" returncode={execution.result.returncode}"
        f" head={execution.head_sha}",
        file=sys.stderr,
    )
    if diagnostic:
        print(diagnostic, file=sys.stderr)
    print(
        f"PROOFOS_HERMETIC_R5_DIAGNOSTIC_END test_id={execution.result.test_id}",
        file=sys.stderr,
    )


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

    # R5's full-federation proof is made hermetic before any selected court can
    # mutate the working checkout. An exact-head clean worktree result is then
    # made authoritative in the final admission report. This strengthens the
    # release floor: dirty state can neither create a false pass nor a false block.
    hermetic = run_hermetic_r5_fallback(
        policy=policy,
        manifest=manifest,
        repo_root=args.repo_root,
    )

    temporary_cache = None
    if args.cache_dir:
        cache = ProofCache(args.cache_dir)
    elif hermetic is not None and hermetic.result.status == "PASS":
        temporary_cache = tempfile.TemporaryDirectory(prefix="proofos-hermetic-cache-")
        cache = ProofCache(Path(temporary_cache.name) / "cache")
    else:
        cache = None

    try:
        if hermetic is not None and hermetic.result.status == "PASS" and cache is not None:
            cache.store(hermetic.result)

        report = ProofRunner(
            policy=policy,
            repo_root=args.repo_root,
            cache=cache,
        ).run(manifest)
        report = enforce_hermetic_fallback(
            report,
            hermetic,
            fallback_test_id=policy.fallback_test_id,
        )
    finally:
        if temporary_cache is not None:
            temporary_cache.cleanup()

    _write_json(args.output, report.to_dict())
    if hermetic is not None:
        print(
            "PROOFOS_HERMETIC_R5"
            f" status={hermetic.result.status}"
            f" head={hermetic.head_sha}"
            f" proof={hermetic.result.proof_key}"
            f" clean_checkout={str(hermetic.clean_checkout_verified).lower()}"
        )
    print(
        "PROOFOS_ADMISSION"
        f" status={report.status}"
        f" manifest={report.manifest_sha256}"
        f" report={report.report_sha256}"
        f" tests={len(report.results)}"
        f" failures={len(report.blocking_failures)}"
    )
    if report.status != "PASS":
        _emit_hermetic_failure(hermetic)
        _emit_failure_diagnostics(policy=policy, report=report, repo_root=args.repo_root)
        return 1
    return 0


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
