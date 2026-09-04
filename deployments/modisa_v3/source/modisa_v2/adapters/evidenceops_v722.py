"""Proof-bound MODISA checkpoint adapter for EvidenceOps v7.2.2 P12.

The adapter composes the P12 crash/resume worker beneath MODISA. It does not
complete a MODISA workflow, execute legal work, call a model, or grant external
authority. MODISA remains the owner of matter walls, workflow transitions,
proof chains, approvals, and release decisions.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from ..schemas import WorkflowRecord, WorkflowStatus

ADAPTER_SCHEMA = "MODISA_EVIDENCEOPS_V722_ADAPTER_RECEIPT_V1"
ADAPTER_VERSION = "1.0.0"
UPSTREAM_VERSION = "7.2.2"
UPSTREAM_COMMIT = "47ce62cbd6ae9fb5cfbde8a1132796c2e70ce01e"
UPSTREAM_TREE = "b9f8f4532fc87dbc0a78b3d6ef4466ba595adf1d"
UPSTREAM_SCRIPT_SHA256 = "245e8f6683080521489d48ca66ea741e3f81e8a918b7e8244733e870015fb6a1"


class AdapterError(RuntimeError):
    """Base error for adapter failures."""


class AdapterCollisionError(AdapterError):
    """An existing checkpoint belongs to a different workflow snapshot."""


class AdapterVerificationError(AdapterError):
    """A source, receipt, policy, or integrity verification failed."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdapterVerificationError(f"Unreadable JSON receipt: {path}") from exc
    if not isinstance(raw, dict):
        raise AdapterVerificationError(f"JSON receipt must be an object: {path}")
    return cast(dict[str, Any], raw)


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


class EvidenceOpsV722Adapter:
    """Run and verify a pinned EvidenceOps P12 checkpoint for a MODISA workflow."""

    def __init__(
        self,
        *,
        workspace_root: Path,
        upstream_script: Path | None = None,
        timeout_seconds: float = 30.0,
        expected_upstream_sha256: str = UPSTREAM_SCRIPT_SHA256,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        bundled_upstream = (
            Path(__file__).parent
            / "upstream"
            / "evidenceops_v722"
            / "p12_provider_worker.py.snapshot"
        )
        self.upstream_script = (upstream_script or bundled_upstream).resolve()
        self.workspace_root = workspace_root.resolve()
        self.timeout_seconds = timeout_seconds
        self.expected_upstream_sha256 = expected_upstream_sha256

    def checkpoint(
        self,
        workflow: WorkflowRecord,
        *,
        worker_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        """Create or idempotently read a verified, matter-bound checkpoint receipt."""
        snapshot = self._validate_and_snapshot(workflow, worker_id=worker_id, request_id=request_id)
        fingerprint = _sha256_value(snapshot)
        final_directory = self._final_directory(workflow)

        if final_directory.exists():
            existing_receipt = self.verify_checkpoint(final_directory)
            if existing_receipt.get("request_fingerprint") != fingerprint:
                raise AdapterCollisionError(
                    "Checkpoint key already exists for a different workflow snapshot"
                )
            return existing_receipt

        self.workspace_root.mkdir(parents=True, exist_ok=True)
        final_directory.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".adapter-stage-", dir=self.workspace_root) as name:
            stage = Path(name)
            upstream_workspace = stage / "upstream"
            self._run_upstream("checkpoint", upstream_workspace, snapshot, expected_returncode=75)
            self._run_upstream("resume", upstream_workspace, snapshot, expected_returncode=0)
            self._run_upstream("verify", upstream_workspace, snapshot, expected_returncode=0)

            upstream_receipt_path = (
                upstream_workspace / "reports" / "p12_provider_worker_receipt.json"
            )
            upstream_receipt = self._verify_upstream_receipt(upstream_receipt_path)
            receipt: dict[str, Any] = {
                "schema": ADAPTER_SCHEMA,
                "adapter_version": ADAPTER_VERSION,
                "upstream_version": UPSTREAM_VERSION,
                "upstream_commit": UPSTREAM_COMMIT,
                "upstream_tree": UPSTREAM_TREE,
                "upstream_script_sha256": self.expected_upstream_sha256,
                "matter_id": workflow.matter_id,
                "mission_id": workflow.mission_id,
                "workflow_id": workflow.workflow_id,
                "workflow_status": workflow.status.value,
                "worker_id": worker_id,
                "request_id": request_id,
                "workflow_snapshot_sha256": snapshot["workflow_snapshot_sha256"],
                "request_fingerprint": fingerprint,
                "upstream_receipt_sha256": upstream_receipt["receipt_sha256"],
                "upstream_receipt_file_sha256": _sha256_file(upstream_receipt_path),
                "authority_ceiling": "A1",
                "external_effects": 0,
                "proof": {
                    "source_pin_verified": True,
                    "matter_binding": True,
                    "mission_binding": True,
                    "workflow_binding": True,
                    "checkpoint_integrity": True,
                    "crash_resume": True,
                    "semantic_readback": True,
                    "rollback_canary": True,
                    "consequential_action_denied": True,
                    "idempotency_key": fingerprint,
                },
                "truth_boundary": (
                    "This receipt proves a local A0/A1 checkpoint sidecar for one MODISA "
                    "workflow snapshot. It does not prove legal-work completion, model execution, "
                    "provider deployment, or external authority."
                ),
            }
            receipt["receipt_sha256"] = _sha256_value(receipt)
            _atomic_write_json(stage / "adapter_receipt.json", receipt)

            try:
                os.replace(stage, final_directory)
            except OSError as exc:
                if not final_directory.exists():
                    raise AdapterError("Atomic checkpoint promotion failed") from exc
                existing = self.verify_checkpoint(final_directory)
                if existing.get("request_fingerprint") != fingerprint:
                    raise AdapterCollisionError(
                        "Concurrent checkpoint promotion produced a different snapshot"
                    ) from exc
                return existing

        return self.verify_checkpoint(final_directory)

    def verify_checkpoint(self, checkpoint_directory: Path) -> dict[str, Any]:
        """Verify the adapter envelope, pinned source, and nested P12 receipt."""
        self._verify_source_pin()
        directory = checkpoint_directory.resolve()
        try:
            directory.relative_to(self.workspace_root)
        except ValueError as exc:
            raise AdapterVerificationError("Checkpoint is outside the configured workspace") from exc

        receipt_path = directory / "adapter_receipt.json"
        receipt = _read_object(receipt_path)
        supplied = receipt.get("receipt_sha256")
        unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        if supplied != _sha256_value(unsigned):
            raise AdapterVerificationError("Adapter receipt hash mismatch")
        if receipt.get("schema") != ADAPTER_SCHEMA:
            raise AdapterVerificationError("Unexpected adapter receipt schema")
        if receipt.get("external_effects") != 0 or receipt.get("authority_ceiling") != "A1":
            raise AdapterVerificationError("Adapter authority boundary widened")

        upstream_path = directory / "upstream" / "reports" / "p12_provider_worker_receipt.json"
        upstream = self._verify_upstream_receipt(upstream_path)
        if receipt.get("upstream_receipt_sha256") != upstream.get("receipt_sha256"):
            raise AdapterVerificationError("Nested upstream receipt binding mismatch")
        if receipt.get("upstream_receipt_file_sha256") != _sha256_file(upstream_path):
            raise AdapterVerificationError("Nested upstream receipt file hash mismatch")
        return receipt

    def _validate_and_snapshot(
        self,
        workflow: WorkflowRecord,
        *,
        worker_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        self._verify_source_pin()
        if not worker_id.strip() or not request_id.strip():
            raise ValueError("worker_id and request_id are required")
        if workflow.status != WorkflowStatus.RUNNING:
            raise AdapterError("Only a RUNNING workflow may be checkpointed")
        if workflow.lease_owner != worker_id:
            raise AdapterError("Worker does not hold the MODISA workflow lease")
        if workflow.lease_expires_at is None or workflow.lease_expires_at <= datetime.now(UTC):
            raise AdapterError("MODISA workflow lease is absent or expired")

        workflow_snapshot = {
            "matter_id": workflow.matter_id,
            "mission_id": workflow.mission_id,
            "workflow_id": workflow.workflow_id,
            "workflow_type": workflow.workflow_type,
            "workflow_status": workflow.status.value,
            "input_payload": workflow.input_payload,
            "state_payload": workflow.state_payload,
            "attempts": workflow.attempts,
            "max_attempts": workflow.max_attempts,
            "lease_owner": workflow.lease_owner,
            "lease_expires_at": (
                workflow.lease_expires_at.isoformat() if workflow.lease_expires_at else None
            ),
        }
        return {
            "matter_id": workflow.matter_id,
            "mission_id": workflow.mission_id,
            "workflow_id": workflow.workflow_id,
            "worker_id": worker_id,
            "request_id": request_id,
            "workflow_snapshot_sha256": _sha256_value(workflow_snapshot),
        }

    def _verify_source_pin(self) -> None:
        if not self.upstream_script.is_file():
            raise AdapterVerificationError("Pinned EvidenceOps worker source is missing")
        observed = _sha256_file(self.upstream_script)
        if observed != self.expected_upstream_sha256:
            raise AdapterVerificationError(
                f"Pinned EvidenceOps worker hash mismatch: observed {observed}"
            )

    def _final_directory(self, workflow: WorkflowRecord) -> Path:
        matter_key = hashlib.sha256(workflow.matter_id.encode()).hexdigest()
        workflow_key = hashlib.sha256(workflow.workflow_id.encode()).hexdigest()
        return self.workspace_root / matter_key / workflow_key

    def _run_upstream(
        self,
        mode: str,
        workspace: Path,
        snapshot: dict[str, Any],
        *,
        expected_returncode: int,
    ) -> None:
        command = [
            sys.executable,
            str(self.upstream_script),
            mode,
            "--workspace",
            str(workspace),
            "--event-name",
            "modisa_workflow_checkpoint",
            "--run-id",
            str(snapshot["workflow_id"]),
            "--run-attempt",
            "1",
            "--workflow",
            "modisa-evidenceops-v722-adapter",
            "--sha",
            str(snapshot["workflow_snapshot_sha256"]),
            "--ref",
            "refs/local/modisa-adapter",
            "--repository",
            "local/MODISA-Agent-Recovery-v2.3",
        ]
        try:
            completed = subprocess.run(  # noqa: S603
                command,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AdapterError(f"EvidenceOps worker timed out during {mode}") from exc
        if completed.returncode != expected_returncode:
            detail = completed.stderr.strip() or completed.stdout.strip() or "no diagnostic"
            raise AdapterError(
                f"EvidenceOps worker {mode} returned {completed.returncode}; expected "
                f"{expected_returncode}: {detail[:800]}"
            )

    @staticmethod
    def _verify_upstream_receipt(path: Path) -> dict[str, Any]:
        receipt = _read_object(path)
        supplied = receipt.get("receipt_sha256")
        unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        if supplied != _sha256_value(unsigned):
            raise AdapterVerificationError("EvidenceOps receipt hash mismatch")
        proof = receipt.get("proof")
        if not isinstance(proof, dict):
            raise AdapterVerificationError("EvidenceOps proof payload is missing")
        required_true = (
            "checkpoint_integrity",
            "crash_resume",
            "persistent_primary_state",
            "replicated_state",
            "semantic_readback",
            "rollback_canary",
            "consequential_action_denied",
        )
        if not all(proof.get(key) is True for key in required_true):
            raise AdapterVerificationError("EvidenceOps proof gate is incomplete")
        if proof.get("external_effects") != 0:
            raise AdapterVerificationError("EvidenceOps external-effects boundary widened")
        return receipt
