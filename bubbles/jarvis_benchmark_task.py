from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from typing import Mapping


MODULE_VERSION = "1.0.0"
TASK_ROOT = Path(__file__).resolve().parent / "task_modules" / "jarvis_benchmark_control_plane"
CLI_PATH = TASK_ROOT / "src" / "cli.js"
MAX_OUTPUT_BYTES = 512_000
ALLOWED_ACTIONS = {
    "jarvis_benchmark_validate": "validate",
    "jarvis_benchmark_snapshot": "evaluate",
    "jarvis_benchmark_opportunities": "opportunities",
    "jarvis_benchmark_refresh_plan": "refresh-plan",
}


class JarvisBenchmarkTaskError(ValueError):
    pass


def _validate_payload(payload: Mapping[str, object]) -> None:
    unknown = sorted(set(payload).difference({"fixture"}))
    if unknown:
        raise JarvisBenchmarkTaskError(
            "JARVIS benchmark task accepts only the public fixture selector; "
            f"unknown fields: {', '.join(unknown)}"
        )
    if payload.get("fixture", "public-sample-v1") != "public-sample-v1":
        raise JarvisBenchmarkTaskError("Only the committed public-sample-v1 fixture is allowed")


def run_jarvis_benchmark_task(
    action: str,
    payload: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Run one bounded, source-only benchmark task behind the central command bus.

    The adapter never accepts an arbitrary path, URL, body of private evidence, ledger
    write, network refresh, server start, daemon start, or provider credential.
    """

    try:
        command = ALLOWED_ACTIONS[action]
    except KeyError as exc:
        raise JarvisBenchmarkTaskError(f"Unsupported JARVIS benchmark action: {action}") from exc
    if payload is None:
        payload = {}
    if not isinstance(payload, Mapping):
        raise JarvisBenchmarkTaskError("JARVIS benchmark payload must be an object")
    _validate_payload(payload)

    if not CLI_PATH.is_file():
        raise JarvisBenchmarkTaskError("JARVIS benchmark task module is incomplete")

    with TemporaryDirectory(prefix="jarvis-benchmark-task-") as state_dir:
        ledger = Path(state_dir) / "learning-ledger.jsonl"
        environment = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "NODE_ENV": "test",
            "TZ": "UTC",
        }
        process = subprocess.run(
            ["node", str(CLI_PATH), command, "--ledger", str(ledger)],
            cwd=TASK_ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        if process.returncode != 0:
            raise JarvisBenchmarkTaskError(
                f"JARVIS benchmark task failed closed with exit code {process.returncode}"
            )
        encoded = process.stdout.encode("utf-8")
        if len(encoded) > MAX_OUTPUT_BYTES:
            raise JarvisBenchmarkTaskError("JARVIS benchmark task output exceeded its bound")
        try:
            result = json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            raise JarvisBenchmarkTaskError("JARVIS benchmark task returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise JarvisBenchmarkTaskError("JARVIS benchmark task result must be an object")

    return {
        "kind": "LOCAL_JARVIS_BENCHMARK_CONTROL_PLANE",
        "moduleVersion": MODULE_VERSION,
        "action": action,
        "fixture": "public-sample-v1",
        "result": result,
        "providerEffects": False,
        "networkUsed": False,
        "runtimeLedgerPersisted": False,
        "truthBoundary": (
            "This receipt proves only bounded execution against the committed public fixture. "
            "It does not expose or benchmark private JARVIS evidence, refresh external sources, "
            "write a durable ledger, deploy a service, or prove production readiness."
        ),
    }

