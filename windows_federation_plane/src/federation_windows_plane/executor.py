from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
import time
from pathlib import Path
import platform
import socket
import sys
from typing import Any

from .models import TaskEnvelope, TaskReceipt, task_sha256, utc_now
from .policy import ExecutionPolicy
from .trust_spine_v21 import NodeCapabilities, ResourceSovereigntyGovernor


HASH_CHECKPOINT_BYTES = 1024 * 1024


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _memory_budget_mb() -> int:
    if hasattr(os, "sysconf"):
        try:
            page_size = int(os.sysconf("SC_PAGE_SIZE"))
            pages = int(os.sysconf("SC_PHYS_PAGES"))
            if page_size > 0 and pages > 0:
                return max(64, int((page_size * pages) / (1024 * 1024)))
        except (OSError, ValueError, TypeError):
            pass
    return 1024


def _deterministic_bytes(seed: bytes, *, round_index: int, counter: int, byte_count: int) -> tuple[bytes, int]:
    out = bytearray()
    while len(out) < byte_count:
        out.extend(
            hashlib.sha256(
                seed + round_index.to_bytes(4, byteorder="big", signed=False) + counter.to_bytes(8, byteorder="big", signed=False)
            ).digest()
        )
        counter += 1
    return bytes(out[:byte_count]), counter


class WindowsPlane:
    def __init__(self, workspace: Path, *, require_windows: bool = True) -> None:
        self.workspace = workspace.resolve(strict=True)
        self.require_windows = require_windows
        self.policy = ExecutionPolicy(self.workspace)

    def _runner_identity(self) -> dict[str, Any]:
        return {
            "os": platform.system(),
            "os_release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "hostname_sha256": hashlib.sha256(socket.gethostname().encode("utf-8")).hexdigest(),
            "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "source_sha": os.environ.get("FEDERATION_SOURCE_SHA") or os.environ.get("GITHUB_SHA"),
            "github_event_sha": os.environ.get("GITHUB_SHA"),
        }

    def execute(self, task: TaskEnvelope) -> TaskReceipt:
        started = utc_now()
        if self.require_windows and platform.system() != "Windows":
            raise RuntimeError("WINDOWS_RUNTIME_REQUIRED")
        authorized = self.policy.authorize(task)
        if task.task_type == "health":
            result: dict[str, Any] = {
                "status": "healthy",
                "plane_version": "1.0.0",
                "allowlisted_tasks": ["health", "inventory", "hash_workspace_file", "heavy_sha256"],
                "arbitrary_command_execution": False,
            }
        elif task.task_type == "inventory":
            result = {
                "platform": platform.platform(),
                "processor": platform.processor(),
                "architecture": platform.machine(),
                "python_implementation": platform.python_implementation(),
                "python_version": platform.python_version(),
                "workspace_exists": self.workspace.is_dir(),
                "workspace_path_disclosed": False,
            }
        elif task.task_type == "hash_workspace_file":
            path = authorized["path"]
            result = {
                "relative_path": authorized["relative_path"],
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        elif task.task_type == "heavy_sha256":
            governor = ResourceSovereigntyGovernor()
            grant = governor.grant(
                NodeCapabilities(
                    trust_mode="B0_EPHEMERAL_LOW_TRUST",
                    logical_cores=max(1, os.cpu_count() or 1),
                    memory_budget_mb=_memory_budget_mb(),
                    gpu_class="NONE",
                    wasm_simd=False,
                    wasm_threads=False,
                    disk_cache_mb=0,
                    network_rtt_ms=0,
                    power_state="stable",
                    visibility_state="visible",
                ),
                requested_workers=authorized["requested_workers"],
                requested_memory_mb=authorized["requested_memory_mb"],
                requested_gpu=False,
                max_seconds=authorized["max_seconds"],
            )
            seed = bytes.fromhex(authorized["seed_hex"])
            rounds = authorized["rounds"]
            bytes_per_round = authorized["bytes_per_round"]
            total_bytes = authorized["total_bytes"]
            digest = hashlib.sha256()
            started_monotonic = time.perf_counter()
            deadline = started_monotonic + grant.max_seconds
            for round_index in range(rounds):
                produced = 0
                counter = 0
                while produced < bytes_per_round:
                    if time.perf_counter() > deadline:
                        raise RuntimeError("HEAVY_SHA256_DEADLINE_EXCEEDED")
                    block_size = min(HASH_CHECKPOINT_BYTES, bytes_per_round - produced)
                    block, counter = _deterministic_bytes(
                        seed, round_index=round_index, counter=counter, byte_count=block_size
                    )
                    digest.update(block)
                    produced += block_size
                    if time.perf_counter() > deadline:
                        raise RuntimeError("HEAVY_SHA256_DEADLINE_EXCEEDED")
            wall_seconds = max(0.0, time.perf_counter() - started_monotonic)
            throughput = (total_bytes / (1024 * 1024)) / wall_seconds if wall_seconds > 0 else 0.0
            result = {
                "final_sha256": digest.hexdigest(),
                "total_bytes": total_bytes,
                "rounds": rounds,
                "requested_workers": authorized["requested_workers"],
                "granted_workers": grant.cpu_workers,
                "requested_memory_mb": authorized["requested_memory_mb"],
                "granted_memory_mb": grant.memory_mb,
                "requested_max_seconds": authorized["max_seconds"],
                "granted_max_seconds": grant.max_seconds,
                "wall_seconds": wall_seconds,
                "throughput_mib_per_s": throughput,
                "resource_governor_bound": True,
                "generated_in_memory": True,
                "filesystem_used": False,
                "network_used": False,
                "shell_process_used": False,
                "gpu_used": False,
            }
        else:
            raise ValueError("TASK_TYPE_NOT_IMPLEMENTED")
        return TaskReceipt(
            schema="FEDERATION-WINDOWS-RECEIPT-V1",
            task_id=task.task_id,
            correlation_id=task.correlation_id,
            task_type=task.task_type,
            state="COMPLETED_VERIFIED_LOCAL",
            started_at=started,
            completed_at=utc_now(),
            runner=self._runner_identity(),
            task=asdict(task),
            result=result,
            task_sha256=task_sha256(task),
            result_sha256=_sha256_json(result),
        )
