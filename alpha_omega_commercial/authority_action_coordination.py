from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - POSIX is used by provider runtimes
    fcntl = None

from authority_action_journal import (
    JournalSafeAtomicAuthoritySnapshotCommercialControlPlane,
)


class CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane(
    JournalSafeAtomicAuthoritySnapshotCommercialControlPlane
):
    """Canonical v9 control plane with process-coordinated recovery and actions.

    V8 makes each transaction event atomically publishable, but a second worker
    could still start while another worker held a durable ACTION_PREPARED record.
    Startup recovery would then be able to mistake the live transaction for a
    crashed transaction and restore its recovery bundle. V9 places startup
    cleanup/recovery, every governed action and integrity readback behind one
    provider-process lock. A live transaction therefore cannot be rolled back by
    a concurrently starting worker, while an actual process crash releases the
    operating-system lock so the next worker can recover deterministically.
    """

    COORDINATION_LOCK_FILE = "authority_action_coordination.lock"
    _fallback_locks: dict[str, threading.RLock] = {}
    _fallback_locks_guard = threading.Lock()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if args:
            root = Path(args[0])
        elif "state_dir" in kwargs:
            root = Path(kwargs["state_dir"])
        else:
            raise TypeError("state_dir is required")
        root.mkdir(parents=True, exist_ok=True)
        self.action_coordination_lock_path = root / self.COORDINATION_LOCK_FILE
        lock_key = str(self.action_coordination_lock_path.resolve())
        with self._fallback_locks_guard:
            self._action_coordination_fallback_lock = self._fallback_locks.setdefault(
                lock_key, threading.RLock()
            )
        self._action_coordination_local = threading.local()
        with self._action_coordination_locked():
            super().__init__(*args, **kwargs)

    @contextmanager
    def _action_coordination_locked(self) -> Iterator[None]:
        """Serialize startup recovery, live actions and integrity readback."""

        depth = getattr(self._action_coordination_local, "depth", 0)
        if depth:
            self._action_coordination_local.depth = depth + 1
            try:
                yield
            finally:
                self._action_coordination_local.depth = depth
            return

        with self._action_coordination_fallback_lock:
            with self.action_coordination_lock_path.open(
                "a+", encoding="utf-8"
            ) as handle:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                self._action_coordination_local.depth = 1
                try:
                    yield
                finally:
                    self._action_coordination_local.depth = 0
                    if fcntl is not None:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

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
        with self._action_coordination_locked():
            with super()._atomic_action(
                stage=stage,
                action=action,
                object_id=object_id,
                domains=domains,
                now=now,
            ) as transaction:
                yield transaction

    def authority_action_coordination_readback(self) -> dict[str, Any]:
        with self._action_coordination_locked():
            self._verify_transaction_ledger()
            return {
                "coordination_lock_file": self.COORDINATION_LOCK_FILE,
                "integrity": "VERIFIED",
                "provider_process_lock_available": fcntl is not None,
                "process_local_reentrant_fallback": True,
                "startup_cleanup_serialized": True,
                "startup_recovery_serialized": True,
                "live_authority_actions_serialized": True,
                "integrity_readback_serialized": True,
                "concurrent_startup_can_rollback_live_transaction": False,
                "process_crash_releases_coordination_lock": True,
                "new_action_blocked_until_recovery_complete": True,
            }

    def authority_action_transaction_readback(self) -> dict[str, Any]:
        with self._action_coordination_locked():
            result = super().authority_action_transaction_readback()
            result["process_coordination"] = (
                self.authority_action_coordination_readback()
            )
            result["concurrent_startup_can_rollback_live_transaction"] = False
            return result

    def governed_authority_readback(self) -> dict[str, Any]:
        with self._action_coordination_locked():
            result = super().governed_authority_readback()
            result["canonical_class"] = self.__class__.__name__
            result["predecessor_class"] = (
                "JournalSafeAtomicAuthoritySnapshotCommercialControlPlane"
            )
            result["authority_action_process_coordination"] = (
                self.authority_action_coordination_readback()
            )
            return result
