from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from authority_action_crash_recovery import (
    CrashSafeAtomicAuthoritySnapshotCommercialControlPlane,
)
from authority_snapshot import digest


class JournalSafeAtomicAuthoritySnapshotCommercialControlPlane(
    CrashSafeAtomicAuthoritySnapshotCommercialControlPlane
):
    """Canonical v8 control plane with atomic transaction-event publication.

    V7 persists a durable pre-action recovery bundle and restores any prepared
    transaction that lacks a terminal event after process restart. Its transaction
    ledger is a single append-only JSONL file, however, so an abrupt process exit
    during an event append can leave a torn final line and prevent deterministic
    restart recovery. V8 freezes the legacy JSONL prefix and publishes every new
    event as one independently hash-bound file using write, fsync, atomic rename
    and directory fsync. A crash can therefore expose either the preceding valid
    journal or the complete new event, never a partially published event.
    """

    JOURNAL_DIRECTORY = "authority_action_transaction_journal"
    JOURNAL_ENTRY_PATTERN = re.compile(
        r"^(?P<sequence>[0-9]{8})-(?P<sha256>[0-9a-f]{64})\.event\.json$"
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if args:
            root = Path(args[0])
        elif "state_dir" in kwargs:
            root = Path(kwargs["state_dir"])
        else:
            raise TypeError("state_dir is required")
        self.transaction_journal_root = root / self.JOURNAL_DIRECTORY
        self.transaction_journal_root.mkdir(parents=True, exist_ok=True)
        self._cleanup_incomplete_journal_publications()
        super().__init__(*args, **kwargs)
        self._verify_transaction_ledger()

    def _cleanup_incomplete_journal_publications(self) -> None:
        for path in self.transaction_journal_root.iterdir():
            if path.name.startswith(".") and path.name.endswith(".tmp"):
                if not path.is_file():
                    raise RuntimeError(
                        "authority action journal temporary entry invalid"
                    )
                path.unlink()
        self._fsync_directory(self.transaction_journal_root)

    def _legacy_transaction_events(self) -> list[dict[str, Any]]:
        return super()._transaction_events()

    def _journal_transaction_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for path in sorted(self.transaction_journal_root.iterdir()):
            if path.name.startswith(".") and path.name.endswith(".tmp"):
                raise RuntimeError(
                    "authority action journal incomplete publication present"
                )
            match = self.JOURNAL_ENTRY_PATTERN.fullmatch(path.name)
            if not path.is_file() or match is None:
                raise RuntimeError("authority action journal entry path invalid")
            try:
                event = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    "authority action journal entry unreadable"
                ) from exc
            sequence = int(match.group("sequence"))
            filename_hash = match.group("sha256")
            if event.get("sequence") != sequence:
                raise RuntimeError("authority action journal sequence binding invalid")
            payload = dict(event)
            observed_hash = payload.pop("event_sha256", None)
            if observed_hash != filename_hash or observed_hash != digest(payload):
                raise RuntimeError("authority action journal hash binding invalid")
            events.append(event)
        return events

    def _transaction_events(self) -> list[dict[str, Any]]:
        return self._legacy_transaction_events() + self._journal_transaction_events()

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

        final_name = (
            f"{event['sequence']:08d}-{event['event_sha256']}.event.json"
        )
        final_path = self.transaction_journal_root / final_name
        temporary = self.transaction_journal_root / (
            f".{final_name}.{os.getpid()}.tmp"
        )
        if final_path.exists() or temporary.exists():
            raise RuntimeError("authority action journal publication conflict")
        payload = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
        try:
            with temporary.open("x", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, final_path)
            self._fsync_directory(self.transaction_journal_root)
        except Exception:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            raise
        return event

    def authority_action_journal_readback(self) -> dict[str, Any]:
        legacy = self._legacy_transaction_events()
        journal = self._journal_transaction_events()
        self._verify_transaction_ledger()
        temporary_entries = sorted(
            path.name
            for path in self.transaction_journal_root.iterdir()
            if path.name.startswith(".") and path.name.endswith(".tmp")
        )
        return {
            "journal_directory": self.JOURNAL_DIRECTORY,
            "integrity": "VERIFIED",
            "legacy_jsonl_events": len(legacy),
            "atomically_published_events": len(journal),
            "total_events": len(legacy) + len(journal),
            "incomplete_publications": temporary_entries,
            "legacy_prefix_frozen": True,
            "event_file_hash_bound": True,
            "event_filename_hash_bound": True,
            "atomic_rename_publication": True,
            "event_file_fsync": True,
            "journal_directory_fsync": True,
            "torn_event_visible_after_process_crash": False,
        }

    def authority_action_transaction_readback(self) -> dict[str, Any]:
        result = super().authority_action_transaction_readback()
        result["transaction_journal"] = self.authority_action_journal_readback()
        result["torn_transaction_event_visible_after_process_crash"] = False
        return result

    def governed_authority_readback(self) -> dict[str, Any]:
        result = super().governed_authority_readback()
        result["canonical_class"] = self.__class__.__name__
        result["predecessor_class"] = (
            "CrashSafeAtomicAuthoritySnapshotCommercialControlPlane"
        )
        result["authority_action_transaction_journal"] = (
            self.authority_action_journal_readback()
        )
        return result
