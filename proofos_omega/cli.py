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
    ExecutionBudget,
    RunBudgetExhausted,
    ProofCache,
    ProofRunner,
    ProofSelector,
    changed_paths_from_git,
    load_manifest,
    run_court_process,
)
from .policy import ProofPolicy
from .impact import ImpactCompiler


_DIAGNOSTIC_MAX_CHARS = 12000
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_AUTH_VALUE_RE = re.compile(r"(?i)\b(?:bearer|token)\s+[A-Za-z0-9._~+/=-]{6,}")
_SECRET_VALUE_RES = (
    re.compile(r"\b(?:sk-(?:proj-|or-v1-|ant-)?|github[_]pat_|gh[pousr]_)[A-Za-z0-9_.-]{6,}\b"),
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
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, prefix=target.name + ".", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
            stream.flush()
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


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


def _emit_failure_diagnostics(*, policy: ProofPolicy, report, repo_root: str | Path,
                              budget: ExecutionBudget | None = None,
                              captured_output: dict[str, str] | None = None,
                              progress=None) -> None:
    """Emit failure-only diagnostics without changing authoritative ProofOS evidence.

    The authoritative court has already executed and its hashes remain unchanged in
    the immutable admission report. Prefer captured court output; an existing
    repeatability probe must never cause a third execution. For legacy callers
    without captured output or a previous probe, a diagnostic rerun consumes only
    the remaining shared budget. Excerpts are redacted before leaving memory.
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
            if captured_output is not None and result.test_id in captured_output:
                diagnostic_status = "CAPTURED_COURT_OUTPUT"
                diagnostic = _redact_diagnostic(captured_output[result.test_id])
            elif getattr(result, "diagnostic_returncode", None) is not None:
                diagnostic_status = "REPEATABILITY_ALREADY_PROBED"
            elif result.status == "FAIL_BUDGET_EXHAUSTED" or getattr(result, "repeatability", None) == "BUDGET_EXHAUSTED":
                diagnostic_status = "BUDGET_EXHAUSTED"
            elif result.status == "FAIL_NOT_PRESENT":
                diagnostic_status = "PROOF_TARGET_NOT_PRESENT"
            else:
                if progress is not None:
                    progress({"event": "DIAGNOSTIC_START", "test_id": result.test_id,
                              "status": "DIAGNOSTIC_ONLY", "remaining_seconds": budget.remaining() if budget is not None else None})
                timeout = budget.timeout(spec.timeout_seconds) if budget is not None else spec.timeout_seconds
                process = run_court_process(
                    argv,
                    budgeted=budget is not None,
                    cwd=root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout,
                    check=False,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                diagnostic = _redact_diagnostic((process.stdout or "") + (process.stderr or ""))
        except RunBudgetExhausted:
            diagnostic_status = "BUDGET_EXHAUSTED"
            if progress is not None:
                progress({"event": "BUDGET_EXHAUSTED", "test_id": result.test_id, "phase": "DIAGNOSTIC",
                          "status": "DIAGNOSTIC_ONLY", "remaining_seconds": 0.0})
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
    budget_seconds = getattr(args, "budget_seconds", None)
    budget = ExecutionBudget(budget_seconds) if budget_seconds is not None else None
    progress_path = getattr(args, "progress_output", None) or Path(args.output).with_suffix(".progress.json")
    if Path(progress_path).resolve() == Path(args.output).resolve():
        raise ValueError("progress output must differ from the authoritative report")

    def publish_progress(event):
        payload = {"schema": "FEDERATION-PROOFOS-RUN-PROGRESS-V1", "manifest_sha256": manifest.manifest_sha256, **event}
        _write_json(progress_path, payload)
        print("PROOFOS_PROGRESS" + f" event={event['event']} test_id={event.get('test_id') or '-'}"
              + f" completed={event.get('completed_count', '-')} selected={event.get('selected_count', '-')}"
              + f" remaining_seconds={event.get('remaining_seconds')}", flush=True)

    runner = ProofRunner(policy=policy, repo_root=args.repo_root, cache=cache)
    report = runner.run(manifest, budget=budget, progress=publish_progress)
    _write_json(args.output, report.to_dict())
    print(
        "PROOFOS_ADMISSION"
        f" status={report.status}"
        f" manifest={report.manifest_sha256}"
        f" report={report.report_sha256}"
        f" tests={len(report.results)}"
        f" failures={len(report.blocking_failures)}"
    )
    if report.status != "PASS":
        _emit_failure_diagnostics(policy=policy, report=report, repo_root=args.repo_root,
                                  budget=budget, captured_output=runner.failure_outputs, progress=publish_progress)
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
    run_parser.add_argument("--budget-seconds", type=float, help="shared court/repeatability/diagnostic budget; reserve hosted upload headroom")
    run_parser.add_argument("--progress-output", help="atomic progress checkpoint (defaults beside the admission report)")
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
