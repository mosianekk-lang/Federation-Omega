from __future__ import annotations

import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - live provider runtimes must be POSIX
    fcntl = None

from authority_action_coordination import (
    CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane,
)
from authority_snapshot import digest
from authority_snapshot_control_plane import LIVE_PROFILE


class IdentityPinnedCoordinatedAuthoritySnapshotCommercialControlPlane(
    CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane
):
    """Canonical v10 control plane with identity-pinned process coordination.

    V9 serializes startup recovery, governed actions and integrity readback with a
    provider-process file lock. A lock pathname can nevertheless be unlinked or
    replaced while an existing worker still owns the old inode. A later worker
    could then lock the replacement inode and enter the critical section
    concurrently. V10 opens the lock without following symlinks, requires one
    regular private file, pins its device/inode identity for the complete critical
    section, revalidates it before transaction commit and fails live profiles
    closed when provider-process locking is unavailable.
    """

    LOCK_MODE = 0o600

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        profile = kwargs.get("authority_profile")
        if profile is None and len(args) >= 4:
            profile = args[3]
        self._coordination_requires_provider_process_lock = profile == LIVE_PROFILE
        if self._coordination_requires_provider_process_lock and fcntl is None:
            raise RuntimeError(
                "live authority requires provider-process POSIX coordination"
            )
        super().__init__(*args, **kwargs)

    def _open_coordination_lock(self) -> int:
        flags = os.O_RDWR | os.O_CREAT
        flags |= getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(
            self.action_coordination_lock_path,
            flags,
            self.LOCK_MODE,
        )
        try:
            observed = os.fstat(descriptor)
            if not stat.S_ISREG(observed.st_mode):
                raise RuntimeError("coordination lock is not a regular file")
            if observed.st_nlink != 1:
                raise RuntimeError("coordination lock hard-link count invalid")
            path_state = os.lstat(self.action_coordination_lock_path)
            if stat.S_ISLNK(path_state.st_mode):
                raise RuntimeError("coordination lock symlink rejected")
            if (observed.st_dev, observed.st_ino) != (
                path_state.st_dev,
                path_state.st_ino,
            ):
                raise RuntimeError("coordination lock identity mismatch")
            os.fchmod(descriptor, self.LOCK_MODE)
            return descriptor
        except Exception:
            os.close(descriptor)
            raise

    def _verify_lock_identity(self, descriptor: int) -> os.stat_result:
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode):
            raise RuntimeError("coordination lock descriptor invalid")
        if observed.st_nlink != 1:
            raise RuntimeError("coordination lock was unlinked or hard-linked")
        path_state = os.lstat(self.action_coordination_lock_path)
        if stat.S_ISLNK(path_state.st_mode):
            raise RuntimeError("coordination lock path became a symlink")
        if (observed.st_dev, observed.st_ino) != (
            path_state.st_dev,
            path_state.st_ino,
        ):
            raise RuntimeError("coordination lock path was replaced")
        if stat.S_IMODE(observed.st_mode) != self.LOCK_MODE:
            raise RuntimeError("coordination lock permissions drifted")
        return observed

    def _verify_current_lock_identity(self) -> os.stat_result:
        descriptor = getattr(self._action_coordination_local, "lock_fd", None)
        if descriptor is None:
            raise RuntimeError("coordination lock identity is not active")
        return self._verify_lock_identity(descriptor)

    @contextmanager
    def _action_coordination_locked(self) -> Iterator[None]:
        depth = getattr(self._action_coordination_local, "depth", 0)
        if depth:
            self._verify_current_lock_identity()
            self._action_coordination_local.depth = depth + 1
            try:
                yield
                self._verify_current_lock_identity()
            finally:
                self._action_coordination_local.depth = depth
            return

        if self._coordination_requires_provider_process_lock and fcntl is None:
            raise RuntimeError(
                "live authority requires provider-process POSIX coordination"
            )

        with self._action_coordination_fallback_lock:
            descriptor = self._open_coordination_lock()
            locked = False
            try:
                if fcntl is not None:
                    fcntl.flock(descriptor, fcntl.LOCK_EX)
                    locked = True
                elif self._coordination_requires_provider_process_lock:
                    raise RuntimeError(
                        "provider-process coordination lock unavailable"
                    )
                identity = self._verify_lock_identity(descriptor)
                self._action_coordination_local.depth = 1
                self._action_coordination_local.lock_fd = descriptor
                self._action_coordination_local.lock_identity = (
                    identity.st_dev,
                    identity.st_ino,
                )
                try:
                    yield
                    self._verify_current_lock_identity()
                finally:
                    self._action_coordination_local.depth = 0
                    self._action_coordination_local.lock_fd = None
                    self._action_coordination_local.lock_identity = None
            finally:
                if locked and fcntl is not None:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

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
                # This executes before the predecessor transaction context writes
                # ACTION_COMMITTED, so identity loss becomes a rollback trigger.
                self._verify_current_lock_identity()

    def _append_transaction_event(
        self,
        event_type: str,
        transaction: dict[str, Any],
        *,
        result_sha256: str | None = None,
        failure_class: str | None = None,
    ) -> dict[str, Any]:
        if event_type == "ACTION_COMMITTED":
            self._verify_current_lock_identity()
        return super()._append_transaction_event(
            event_type,
            transaction,
            result_sha256=result_sha256,
            failure_class=failure_class,
        )

    def authority_action_coordination_integrity_readback(self) -> dict[str, Any]:
        with self._action_coordination_locked():
            observed = self._verify_current_lock_identity()
            identity = {
                "device": observed.st_dev,
                "inode": observed.st_ino,
            }
            return {
                "integrity": "VERIFIED",
                "lock_identity_sha256": digest(identity),
                "lock_regular_file_required": True,
                "lock_single_link_required": True,
                "lock_symlink_following_allowed": False,
                "lock_mode": oct(self.LOCK_MODE),
                "lock_identity_pinned_for_critical_section": True,
                "lock_identity_revalidated_before_commit": True,
                "lock_identity_revalidated_before_unlock": True,
                "live_profile_requires_provider_process_lock": True,
                "process_local_fallback_grants_live_authority": False,
                "lock_path_replacement_can_authorize_parallel_live_action": False,
            }

    def authority_action_transaction_readback(self) -> dict[str, Any]:
        with self._action_coordination_locked():
            result = super().authority_action_transaction_readback()
            result["coordination_lock_integrity"] = (
                self.authority_action_coordination_integrity_readback()
            )
            result["lock_path_replacement_can_authorize_parallel_live_action"] = False
            return result

    def governed_authority_readback(self) -> dict[str, Any]:
        with self._action_coordination_locked():
            result = super().governed_authority_readback()
            result["canonical_class"] = self.__class__.__name__
            result["predecessor_class"] = (
                "CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane"
            )
            result["authority_action_coordination_integrity"] = (
                self.authority_action_coordination_integrity_readback()
            )
            return result
