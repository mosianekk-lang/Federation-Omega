from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _safe_relative_path(raw: str) -> Path:
    path = PurePosixPath(raw)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError(f"unsafe sandbox path: {raw}")
    return Path(*path.parts)


@dataclass(frozen=True)
class SandboxPolicy:
    timeout_seconds: float = 5.0
    max_output_bytes: int = 64_000
    max_artifact_bytes: int = 1_000_000
    allowed_executables: tuple[str, ...] = ()
    allowed_env_keys: tuple[str, ...] = ("LANG", "LC_ALL", "TZ")

    def validate(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_output_bytes <= 0 or self.max_artifact_bytes <= 0:
            raise ValueError("byte quotas must be positive")


@dataclass(frozen=True)
class SandboxTask:
    task_id: str
    command: tuple[str, ...]
    input_files: Mapping[str, str] = field(default_factory=dict)
    export_paths: tuple[str, ...] = ()

    def validate(self, policy: SandboxPolicy) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id is required")
        if not self.command:
            raise ValueError("command is required")
        if policy.allowed_executables and self.command[0] not in policy.allowed_executables:
            raise PermissionError(f"executable is not allowed: {self.command[0]}")
        for path in [*self.input_files.keys(), *self.export_paths]:
            _safe_relative_path(path)


class ReceiptLedger:
    """Append-only hash-chained JSONL ledger with exact readback verification."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _last_hash(self) -> str:
        if not self.path.exists():
            return "GENESIS"
        lines = [line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return json.loads(lines[-1])["entry_hash"] if lines else "GENESIS"

    def append(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        entry = {"previous_hash": self._last_hash(), "payload": dict(payload)}
        entry["entry_hash"] = _digest(entry)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
        readback = json.loads(self.path.read_text(encoding="utf-8").splitlines()[-1])
        if readback != entry:
            raise IOError("receipt readback mismatch")
        return entry

    def verify(self) -> dict[str, Any]:
        previous = "GENESIS"
        count = 0
        if not self.path.exists():
            return {"valid": True, "entries": 0, "head": previous}
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            entry = json.loads(raw)
            claimed = entry.pop("entry_hash")
            valid = entry.get("previous_hash") == previous and _digest(entry) == claimed
            entry["entry_hash"] = claimed
            if not valid:
                return {"valid": False, "entries": count, "head": previous}
            previous = claimed
            count += 1
        return {"valid": True, "entries": count, "head": previous}


class OperationalSandbox:
    """Disposable subprocess sandbox with quotas, artifact readback and cleanup proof.

    This is a process-level isolation boundary for authorised CI workloads. It does
    not claim kernel, VM or container isolation.
    """

    def __init__(self, policy: SandboxPolicy, ledger: ReceiptLedger):
        policy.validate()
        self.policy = policy
        self.ledger = ledger

    def run(self, task: SandboxTask) -> dict[str, Any]:
        task.validate(self.policy)
        root = Path(tempfile.mkdtemp(prefix="ao-sandbox-"))
        status = "ERROR"
        returncode: int | None = None
        stdout = b""
        stderr = b""
        artifacts: dict[str, dict[str, Any]] = {}
        error: str | None = None

        try:
            for raw_path, content in task.input_files.items():
                target = root / _safe_relative_path(raw_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            env = {key: os.environ[key] for key in self.policy.allowed_env_keys if key in os.environ}
            env["AO_SANDBOX"] = "1"
            try:
                completed = subprocess.run(
                    list(task.command),
                    cwd=root,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=self.policy.timeout_seconds,
                    check=False,
                    start_new_session=True,
                )
                returncode = completed.returncode
                stdout = completed.stdout
                stderr = completed.stderr
                status = "PASS" if returncode == 0 else "NONZERO_EXIT"
            except subprocess.TimeoutExpired as exc:
                stdout = exc.stdout or b""
                stderr = exc.stderr or b""
                status = "TIMEOUT"

            if len(stdout) + len(stderr) > self.policy.max_output_bytes:
                status = "OUTPUT_LIMIT"

            artifact_total = 0
            missing_exports: list[str] = []
            for raw_path in task.export_paths:
                target = root / _safe_relative_path(raw_path)
                if not target.is_file():
                    missing_exports.append(raw_path)
                    continue
                data = target.read_bytes()
                artifact_total += len(data)
                artifacts[raw_path] = {
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "text": data.decode("utf-8", errors="replace") if len(data) <= 16_000 else None,
                }
            if missing_exports and status == "PASS":
                status = "READBACK_MISSING"
            if artifact_total > self.policy.max_artifact_bytes:
                status = "ARTIFACT_LIMIT"
        except Exception as exc:  # deterministic receipt for validation and OS failures
            error = f"{type(exc).__name__}: {exc}"
            status = "ERROR"
        finally:
            shutil.rmtree(root, ignore_errors=True)

        rollback_verified = not root.exists()
        result: dict[str, Any] = {
            "task_id": task.task_id,
            "status": status,
            "returncode": returncode,
            "stdout": stdout[: self.policy.max_output_bytes].decode("utf-8", errors="replace"),
            "stderr": stderr[: self.policy.max_output_bytes].decode("utf-8", errors="replace"),
            "artifacts": artifacts,
            "execution_verified": returncode == 0,
            "readback_verified": len(artifacts) == len(task.export_paths),
            "health_verified": status == "PASS",
            "rollback_verified": rollback_verified,
            "error": error,
            "policy": asdict(self.policy),
        }
        result["result_hash"] = _digest(result)
        ledger_entry = self.ledger.append(result)
        result["ledger_entry_hash"] = ledger_entry["entry_hash"]
        result["persistence_verified"] = self.ledger.verify()["valid"]
        return result
