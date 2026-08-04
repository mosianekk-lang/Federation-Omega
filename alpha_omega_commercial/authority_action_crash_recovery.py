from __future__ import annotations

import hashlib
import json
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from authority_action_atomicity import (
    AtomicAuthoritySnapshotCommercialControlPlane,
)
from authority_snapshot import digest
from authority_snapshot_control_plane import LIVE_PROFILE


class CrashSafeAtomicAuthoritySnapshotCommercialControlPlane(
    AtomicAuthoritySnapshotCommercialControlPlane
):
    """Canonical v7 control plane with durable process-crash recovery.

    The v6 control plane restores every governed local persistence surface when an
    exception is observed in-process. This class closes the remaining process-crash
    window by persisting a hash-bound recovery bundle before ACTION_PREPARED. On
    restart, any prepared transaction without a terminal event is restored before
    the control plane can accept another consequential action.
    """

    RECOVERY_DIRECTORY = "authority_action_recovery"
    RECOVERY_MANIFEST = "manifest.json"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.recovery_root = self.state_dir / self.RECOVERY_DIRECTORY
        self.recovery_root.mkdir(parents=True, exist_ok=True)
        self._recover_unterminated_transactions()
        self._cleanup_orphan_recovery_bundles()

    @staticmethod
    def _sha256_bytes(value: bytes) -> str:
        return hashlib.sha256(value).hexdigest()

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        try:
            descriptor = os.open(path, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        except OSError:
            pass
        finally:
            os.close(descriptor)

    def _recovery_bundle(self, transaction_id: str) -> Path:
        if (
            not transaction_id.startswith("AO-ACTION-")
            or "/" in transaction_id
            or "\\" in transaction_id
            or ".." in transaction_id
        ):
            raise RuntimeError("authority action recovery transaction id invalid")
        return self.recovery_root / transaction_id

    def _prepare_recovery_bundle(
        self,
        transaction: dict[str, Any],
        backup: dict[Path, bytes | None],
    ) -> str:
        transaction_id = str(transaction["transaction_id"])
        bundle = self._recovery_bundle(transaction_id)
        temporary = self.recovery_root / f".{transaction_id}.tmp"
        if bundle.exists() or temporary.exists():
            raise RuntimeError("authority action recovery bundle already exists")

        files_directory = temporary / "files"
        files_directory.mkdir(parents=True, exist_ok=False)
        entries: list[dict[str, Any]] = []
        root = self.state_dir.resolve()
        for index, (path, content) in enumerate(
            sorted(backup.items(), key=lambda item: str(item[0]))
        ):
            resolved = path.resolve()
            try:
                relative = resolved.relative_to(root)
            except ValueError as exc:
                raise RuntimeError(
                    "authority action recovery path outside state directory"
                ) from exc
            entry: dict[str, Any] = {
                "relative_path": relative.as_posix(),
                "existed": content is not None,
                "content_file": None,
                "content_sha256": None,
            }
            if content is not None:
                content_name = f"{index:04d}.bin"
                content_path = files_directory / content_name
                with content_path.open("wb") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                entry["content_file"] = f"files/{content_name}"
                entry["content_sha256"] = self._sha256_bytes(content)
            entries.append(entry)

        manifest: dict[str, Any] = {
            "recovery_version": 1,
            "transaction_id": transaction_id,
            "stage": transaction["stage"],
            "action": transaction["action"],
            "object_id": transaction["object_id"],
            "snapshot_sha256": transaction["snapshot_sha256"],
            "acceptance_entry_sha256": transaction["acceptance_entry_sha256"],
            "created_at": transaction["recorded_at"],
            "entries": entries,
        }
        manifest["manifest_sha256"] = digest(manifest)
        manifest_path = temporary / self.RECOVERY_MANIFEST
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._fsync_directory(files_directory)
        self._fsync_directory(temporary)
        os.replace(temporary, bundle)
        self._fsync_directory(self.recovery_root)
        transaction["recovery_manifest_sha256"] = manifest["manifest_sha256"]
        return str(manifest["manifest_sha256"])

    def _load_recovery_manifest(
        self,
        transaction_id: str,
        *,
        expected_sha256: str | None,
    ) -> dict[str, Any]:
        bundle = self._recovery_bundle(transaction_id)
        manifest_path = bundle / self.RECOVERY_MANIFEST
        if not manifest_path.exists():
            raise RuntimeError("authority action recovery manifest missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        observed_hash = manifest.pop("manifest_sha256", None)
        calculated_hash = digest(manifest)
        manifest["manifest_sha256"] = observed_hash
        if not observed_hash or observed_hash != calculated_hash:
            raise RuntimeError("authority action recovery manifest hash invalid")
        if expected_sha256 and observed_hash != expected_sha256:
            raise RuntimeError("authority action recovery manifest binding invalid")
        if manifest.get("transaction_id") != transaction_id:
            raise RuntimeError("authority action recovery transaction mismatch")

        root = self.state_dir.resolve()
        for entry in manifest.get("entries", []):
            relative = Path(str(entry.get("relative_path", "")))
            if relative.is_absolute() or ".." in relative.parts:
                raise RuntimeError("authority action recovery path invalid")
            target = (root / relative).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise RuntimeError("authority action recovery path invalid") from exc
            if bool(entry.get("existed")):
                content_file = entry.get("content_file")
                if not content_file:
                    raise RuntimeError("authority action recovery content missing")
                content_path = (bundle / str(content_file)).resolve()
                try:
                    content_path.relative_to(bundle.resolve())
                except ValueError as exc:
                    raise RuntimeError(
                        "authority action recovery content path invalid"
                    ) from exc
                if not content_path.exists():
                    raise RuntimeError("authority action recovery content missing")
                content = content_path.read_bytes()
                if self._sha256_bytes(content) != entry.get("content_sha256"):
                    raise RuntimeError("authority action recovery content hash invalid")
            elif entry.get("content_file") is not None:
                raise RuntimeError("authority action recovery absent-file entry invalid")
        return manifest

    def _restore_recovery_bundle(self, transaction: dict[str, Any]) -> None:
        transaction_id = str(transaction["transaction_id"])
        expected = transaction.get("recovery_manifest_sha256")
        if not expected:
            raise RuntimeError("authority action recovery binding missing")
        manifest = self._load_recovery_manifest(
            transaction_id,
            expected_sha256=str(expected),
        )
        bundle = self._recovery_bundle(transaction_id)
        root = self.state_dir.resolve()
        for entry in manifest["entries"]:
            target = root / Path(entry["relative_path"])
            content: bytes | None = None
            if entry["existed"]:
                content = (bundle / entry["content_file"]).read_bytes()
            self._restore_file(target, content)
        self._reload_external_controller()

    def _remove_recovery_bundle(self, transaction_id: str) -> None:
        bundle = self._recovery_bundle(transaction_id)
        if bundle.exists():
            shutil.rmtree(bundle)
            self._fsync_directory(self.recovery_root)

    def _append_transaction_event(
        self,
        event_type: str,
        transaction: dict[str, Any],
        *,
        result_sha256: str | None = None,
        failure_class: str | None = None,
    ) -> dict[str, Any]:
        self._verify_transaction_ledger()
        events = self._transaction_events()
        event: dict[str, Any] = {
            "sequence": len(events) + 1,
            "event": event_type,
            "transaction_id": transaction["transaction_id"],
            "stage": transaction["stage"],
            "action": transaction["action"],
            "object_id": transaction["object_id"],
            "snapshot_id": transaction["snapshot_id"],
            "snapshot_sha256": transaction["snapshot_sha256"],
            "acceptance_sequence": transaction["acceptance_sequence"],
            "acceptance_entry_sha256": transaction["acceptance_entry_sha256"],
            "domains": transaction["domains"],
            "recorded_at": transaction["recorded_at"],
            "recovery_manifest_sha256": transaction.get(
                "recovery_manifest_sha256"
            ),
            "previous_event_sha256": (
                events[-1]["event_sha256"] if events else "GENESIS"
            ),
        }
        if result_sha256 is not None:
            event["result_sha256"] = result_sha256
        if failure_class is not None:
            event["failure_class"] = failure_class
        event["event_sha256"] = digest(event)
        with self.transaction_file.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        self._fsync_directory(self.transaction_file.parent)
        return event

    def _unterminated_prepared_events(self) -> list[dict[str, Any]]:
        events = self._transaction_events()
        terminal = {
            event["transaction_id"]
            for event in events
            if event["event"] in {"ACTION_COMMITTED", "ACTION_ROLLED_BACK"}
        }
        return [
            event
            for event in events
            if event["event"] == "ACTION_PREPARED"
            and event["transaction_id"] not in terminal
        ]

    def _recover_unterminated_transactions(self) -> None:
        for prepared in self._unterminated_prepared_events():
            if not prepared.get("recovery_manifest_sha256"):
                raise RuntimeError(
                    "unterminated authority action lacks durable recovery binding"
                )
            transaction = {
                key: prepared[key]
                for key in (
                    "transaction_id",
                    "stage",
                    "action",
                    "object_id",
                    "snapshot_id",
                    "snapshot_sha256",
                    "acceptance_sequence",
                    "acceptance_entry_sha256",
                    "domains",
                    "recorded_at",
                    "recovery_manifest_sha256",
                )
            }
            self._restore_recovery_bundle(transaction)
            self._append_transaction_event(
                "ACTION_ROLLED_BACK",
                transaction,
                failure_class="PROCESS_RESTART_RECOVERY",
            )
            self._remove_recovery_bundle(transaction["transaction_id"])

    def _cleanup_orphan_recovery_bundles(self) -> None:
        active = {
            event["transaction_id"]
            for event in self._unterminated_prepared_events()
        }
        for path in self.recovery_root.iterdir():
            if path.name.startswith(".") and path.name.endswith(".tmp"):
                shutil.rmtree(path, ignore_errors=True)
            elif path.is_dir() and path.name not in active:
                shutil.rmtree(path, ignore_errors=True)
        self._fsync_directory(self.recovery_root)

    @contextmanager
    def _atomic_action(
        self,
        *,
        stage: str,
        action: str,
        object_id: str,
        domains: tuple[str, ...],
        now: str,
    ) -> Iterator[dict[str, Any]]:
        if self.authority_profile != LIVE_PROFILE:
            yield {}
            return
        if self._active_transaction is not None:
            raise RuntimeError("nested authority action transactions are not allowed")

        self.accept_authority_snapshot(now=now)
        ledger = self.authority_snapshot_acceptance
        with ledger._locked():
            entry = self._latest_locked_acceptance(now=now)
            snapshot = self.authority_snapshot_validator.snapshot
            assert snapshot is not None
            missing = sorted(set(domains) - set(snapshot.domains))
            if missing:
                raise PermissionError(
                    "authority action transaction failed: AUTHORITY_DOMAINS_MISSING:"
                    + ",".join(missing)
                )
            events = self._transaction_events()
            transaction: dict[str, Any] = {
                "transaction_id": f"AO-ACTION-{len(events) + 1:08d}",
                "stage": stage,
                "action": action,
                "object_id": object_id,
                "snapshot_id": snapshot.snapshot_id,
                "snapshot_sha256": snapshot.snapshot_sha256,
                "acceptance_sequence": entry["sequence"],
                "acceptance_entry_sha256": entry["entry_sha256"],
                "domains": sorted(set(domains)),
                "recorded_at": now,
            }
            backup = self._capture_transaction_files()
            self._prepare_recovery_bundle(transaction, backup)
            self._append_transaction_event("ACTION_PREPARED", transaction)
            self._active_acceptance_entry = entry
            self._active_transaction = transaction
            try:
                yield transaction
                current = self._latest_locked_acceptance(now=now)
                if current["entry_sha256"] != entry["entry_sha256"]:
                    raise RuntimeError(
                        "authority action transaction acceptance changed"
                    )
                transaction["result_sha256"] = self._transaction_result_sha256(
                    transaction
                )
                self._append_transaction_event(
                    "ACTION_COMMITTED",
                    transaction,
                    result_sha256=transaction["result_sha256"],
                )
                try:
                    self._remove_recovery_bundle(transaction["transaction_id"])
                except OSError:
                    pass
            except Exception as exc:
                try:
                    self._restore_recovery_bundle(transaction)
                except Exception as recovery_error:
                    raise RuntimeError(
                        "authority action durable rollback failed; restart recovery required"
                    ) from recovery_error
                self._append_transaction_event(
                    "ACTION_ROLLED_BACK",
                    transaction,
                    failure_class=exc.__class__.__name__,
                )
                try:
                    self._remove_recovery_bundle(transaction["transaction_id"])
                except OSError:
                    pass
                raise
            finally:
                self._active_transaction = None
                self._active_acceptance_entry = None

    def authority_action_recovery_readback(self) -> dict[str, Any]:
        unterminated = self._unterminated_prepared_events()
        bundles = sorted(
            path.name
            for path in self.recovery_root.iterdir()
            if path.is_dir() and not path.name.startswith(".")
        )
        recovered = [
            event
            for event in self._transaction_events()
            if event.get("failure_class") == "PROCESS_RESTART_RECOVERY"
        ]
        return {
            "recovery_directory": self.RECOVERY_DIRECTORY,
            "integrity": "VERIFIED",
            "unterminated_transactions": [
                event["transaction_id"] for event in unterminated
            ],
            "durable_recovery_bundles": bundles,
            "process_restart_recoveries": len(recovered),
            "new_actions_blocked_until_recovery": True,
            "recovery_manifest_hash_bound": True,
            "recovery_content_hash_verified": True,
            "restart_rollback_is_idempotent": True,
        }

    def authority_action_transaction_readback(self) -> dict[str, Any]:
        result = super().authority_action_transaction_readback()
        result["process_crash_recovery"] = self.authority_action_recovery_readback()
        result["process_crash_partial_state_visible"] = False
        return result

    def governed_authority_readback(self) -> dict[str, Any]:
        result = super().governed_authority_readback()
        result["canonical_class"] = self.__class__.__name__
        result["predecessor_class"] = (
            "AtomicAuthoritySnapshotCommercialControlPlane"
        )
        result["authority_action_recovery"] = (
            self.authority_action_recovery_readback()
        )
        return result
