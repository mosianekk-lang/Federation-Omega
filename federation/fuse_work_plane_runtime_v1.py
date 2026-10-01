"""FUSE Work Plane Runtime v1.

Source-independent candidate implementing interruption-safe mission continuity over an
append-only event model. It is deliberately not a new truth root: production
adapters must map events onto the existing Mission Bus Events v5 / Active Cognition
/ Proof surfaces.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Iterable

SCHEMA = "FUSE-WORK-PLANE-RUNTIME-V1"
VERSION = "1.2.0"
TERMINAL_STATES = {"RESULT_READY", "ACKED", "FAILED", "ABORTED", "RELEASED", "DEAD_LETTER"}
RECOVERABLE_STATES = {"CLAIMED", "RUNNING", "CHECKPOINTED", "ORPHANED_RECOVERABLE", "READBACK_REQUIRED"}
_ALLOWED_GIT_SUBCOMMANDS = {
    "status", "rev-parse", "show", "diff", "log", "ls-files", "cat-file", "init", "clone",
    "fetch", "checkout", "switch", "branch", "add", "commit", "merge-base", "hash-object",
}
_ALLOWED_PYTHON_MODULES = {"pytest", "compileall"}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def digest(value: Any) -> str:
    return sha256(_canonical(value)).hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    data = _canonical(value)
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


@dataclass(frozen=True, slots=True)
class WorkPlaneEvent:
    event_id: str
    mission_id: str
    event_type: str
    actor: str
    attempt: int
    fence: int
    source_state: str
    target_state: str
    event_time_ns: int
    prior_event_id: str | None = None
    checkpoint_hash: str | None = None
    result_hash: str | None = None
    effect_id: str | None = None
    effect_state: str = "NONE"
    notes: str = ""

    @property
    def event_hash(self) -> str:
        return digest(asdict(self))


class JsonlEventStore:
    """Local proof carrier only; production mapping must use existing canonical buses."""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def append(self, event: WorkPlaneEvent) -> None:
        with open(self.path, "ab") as fh:
            fh.write(_canonical(asdict(event)) + b"\n")
            fh.flush()
            os.fsync(fh.fileno())

    def events(self, mission_id: str | None = None) -> list[WorkPlaneEvent]:
        out: list[WorkPlaneEvent] = []
        for line in self.path.read_bytes().splitlines():
            if not line:
                continue
            raw = json.loads(line.decode("utf-8"))
            ev = WorkPlaneEvent(**raw)
            if mission_id is None or ev.mission_id == mission_id:
                out.append(ev)
        return out


@dataclass(frozen=True, slots=True)
class Projection:
    mission_id: str
    state: str
    actor: str | None
    attempt: int
    fence: int
    last_event_id: str | None
    last_event_time_ns: int
    heartbeat_ns: int
    lease_until_ns: int
    checkpoint_hash: str | None
    result_hash: str | None
    effect_state: str
    interruption_state: str


class WorkPlaneRuntime:
    def __init__(self, store: JsonlEventStore, state_path: str | os.PathLike[str]):
        self.store = store
        self.state_path = Path(state_path).resolve()
        self.state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"schema": SCHEMA, "version": VERSION, "missions": {}}
        raw = json.loads(self.state_path.read_text())
        if raw.get("schema") != SCHEMA or raw.get("version") != VERSION:
            raise ValueError("STATE_SCHEMA_MISMATCH")
        if not isinstance(raw.get("missions"), dict):
            raise ValueError("MISSIONS_STATE_INVALID")
        return raw

    def _save(self) -> None:
        _atomic_json(self.state_path, self.state)

    def _mission(self, mission_id: str) -> dict[str, Any]:
        return self.state["missions"].setdefault(mission_id, {
            "state": "PUBLISHED", "actor": None, "attempt": 0, "fence": 0,
            "heartbeat_ns": 0, "lease_until_ns": 0, "checkpoint_hash": None,
            "result_hash": None, "effect_state": "NONE", "effect_id": None,
            "effect_proof_ref": None, "last_event_id": None, "last_event_time_ns": 0,
        })

    def _append(self, mission_id: str, event_type: str, actor: str, source: str, target: str,
                *, attempt: int, fence: int, checkpoint_hash: str | None = None,
                result_hash: str | None = None, effect_id: str | None = None,
                effect_state: str = "NONE", notes: str = "") -> WorkPlaneEvent:
        m = self._mission(mission_id)
        now = time.time_ns()
        ev = WorkPlaneEvent(
            event_id=f"EVT-{mission_id}-{event_type}-{attempt}-{fence}-{now}",
            mission_id=mission_id, event_type=event_type, actor=actor,
            attempt=attempt, fence=fence, source_state=source, target_state=target,
            event_time_ns=now, prior_event_id=m.get("last_event_id"),
            checkpoint_hash=checkpoint_hash, result_hash=result_hash,
            effect_id=effect_id, effect_state=effect_state, notes=notes,
        )
        self.store.append(ev)
        m.update({
            "state": target, "actor": actor, "attempt": attempt, "fence": fence,
            "last_event_id": ev.event_id, "last_event_time_ns": now,
            "checkpoint_hash": checkpoint_hash if checkpoint_hash is not None else m.get("checkpoint_hash"),
            "result_hash": result_hash if result_hash is not None else m.get("result_hash"),
            "effect_state": effect_state,
            "effect_id": effect_id if effect_id is not None else m.get("effect_id"),
        })
        self._save()
        return ev

    def publish(self, mission_id: str, actor: str = "FUSE_ONE") -> WorkPlaneEvent:
        m = self._mission(mission_id)
        if m["last_event_id"]:
            raise RuntimeError("MISSION_ALREADY_EXISTS")
        return self._append(mission_id, "PUBLISH", actor, "ABSENT", "PUBLISHED", attempt=0, fence=0)

    def claim(self, mission_id: str, actor: str, ttl_seconds: int = 120) -> tuple[int, WorkPlaneEvent]:
        m = self._mission(mission_id)
        now = time.time_ns()
        if m["state"] in TERMINAL_STATES:
            raise RuntimeError("MISSION_TERMINAL")
        if m.get("actor") and m.get("lease_until_ns", 0) > now and m["actor"] != actor:
            raise RuntimeError("LEASE_HELD")
        attempt = int(m["attempt"]) + 1
        fence = int(m["fence"]) + 1
        src = m["state"]
        ev = self._append(mission_id, "CLAIM", actor, src, "CLAIMED", attempt=attempt, fence=fence)
        m = self._mission(mission_id)
        m["lease_until_ns"] = now + ttl_seconds * 1_000_000_000
        m["heartbeat_ns"] = now
        self._save()
        return fence, ev

    def assert_fence(self, mission_id: str, actor: str, fence: int) -> dict[str, Any]:
        m = self._mission(mission_id)
        if m.get("actor") != actor:
            raise RuntimeError("ACTOR_MISMATCH")
        if int(m.get("fence", -1)) != fence:
            raise RuntimeError("STALE_FENCE")
        if int(m.get("lease_until_ns", 0)) <= time.time_ns():
            raise RuntimeError("LEASE_EXPIRED")
        return m

    def heartbeat(self, mission_id: str, actor: str, fence: int, ttl_seconds: int = 120) -> WorkPlaneEvent:
        m = self.assert_fence(mission_id, actor, fence)
        now = time.time_ns()
        m["heartbeat_ns"] = now
        m["lease_until_ns"] = now + ttl_seconds * 1_000_000_000
        self._save()
        return self._append(mission_id, "HEARTBEAT", actor, m["state"], m["state"], attempt=m["attempt"], fence=fence)

    def running(self, mission_id: str, actor: str, fence: int) -> WorkPlaneEvent:
        m = self.assert_fence(mission_id, actor, fence)
        return self._append(mission_id, "RUNNING", actor, m["state"], "RUNNING", attempt=m["attempt"], fence=fence)

    def checkpoint(self, mission_id: str, actor: str, fence: int, checkpoint: object) -> WorkPlaneEvent:
        m = self.assert_fence(mission_id, actor, fence)
        h = digest(checkpoint)
        return self._append(mission_id, "CHECKPOINT", actor, m["state"], "CHECKPOINTED", attempt=m["attempt"], fence=fence, checkpoint_hash=h)

    def mark_effect_uncertain(self, mission_id: str, actor: str, fence: int, effect_id: str) -> WorkPlaneEvent:
        m = self.assert_fence(mission_id, actor, fence)
        return self._append(mission_id, "EFFECT_UNKNOWN", actor, m["state"], "READBACK_REQUIRED", attempt=m["attempt"], fence=fence, effect_id=effect_id, effect_state="UNKNOWN")

    def result_ready(self, mission_id: str, actor: str, fence: int, result: object) -> WorkPlaneEvent:
        m = self.assert_fence(mission_id, actor, fence)
        return self._append(mission_id, "RESULT_READY", actor, m["state"], "RESULT_READY", attempt=m["attempt"], fence=fence, result_hash=digest(result), effect_state=m.get("effect_state", "NONE"))

    def detect_interruption(self, mission_id: str, *, stale_after_seconds: int = 180,
                            expected_terminal_by_ns: int | None = None) -> str:
        m = self._mission(mission_id)
        if m["state"] in TERMINAL_STATES:
            return "TERMINAL"
        now = time.time_ns()
        lease_stale = bool(m.get("actor")) and int(m.get("lease_until_ns", 0)) <= now
        heartbeat_stale = bool(m.get("actor")) and int(m.get("heartbeat_ns", 0)) > 0 and now - int(m["heartbeat_ns"]) > stale_after_seconds * 1_000_000_000
        receipt_missing = expected_terminal_by_ns is not None and now > expected_terminal_by_ns and not m.get("result_hash")
        if lease_stale or heartbeat_stale or receipt_missing:
            return "ORPHANED_RECOVERABLE" if m.get("effect_state") in {"NONE", "ABSENT"} else "READBACK_REQUIRED"
        return "PROGRESSING"

    def recover_orphan(self, mission_id: str, new_actor: str, *, readback: str | None = None,
                       ttl_seconds: int = 120) -> tuple[int, WorkPlaneEvent]:
        m = self._mission(mission_id)
        status = self.detect_interruption(mission_id, stale_after_seconds=0)
        if status == "TERMINAL":
            raise RuntimeError("MISSION_TERMINAL")
        if status == "READBACK_REQUIRED":
            if readback is None:
                raise RuntimeError("READBACK_REQUIRED_BEFORE_RECOVERY")
            rb = readback.upper()
            if rb == "MATCH":
                raise RuntimeError("MATCH_REQUIRES_EXTERNAL_RESULT_IMPORT")
            if rb in {"CONFLICT", "UNKNOWN"}:
                self._append(mission_id, "READBACK_HOLD", "REALITY_GUARD", m["state"], "HELD", attempt=m["attempt"], fence=m["fence"], effect_state=rb, notes="External effect unresolved")
                raise RuntimeError("RECOVERY_HELD_BY_READBACK")
            if rb != "ABSENT":
                raise ValueError("INVALID_READBACK")
            m["effect_state"] = "ABSENT"
            self._save()
        self._append(mission_id, "ORPHANED", "HYPERCUBE", m["state"], "ORPHANED_RECOVERABLE", attempt=m["attempt"], fence=m["fence"], checkpoint_hash=m.get("checkpoint_hash"), effect_state=m.get("effect_state", "NONE"), notes="Stale lease/heartbeat/missing receipt")
        return self.claim(mission_id, new_actor, ttl_seconds=ttl_seconds)


    def confirm_effect_readback(self, mission_id: str, actor: str, fence: int, *,
                                effect_id: str, readback: str, proof_ref: str) -> WorkPlaneEvent:
        """Bind provider readback to the current fenced actor without replaying the effect."""
        m = self.assert_fence(mission_id, actor, fence)
        if m.get("effect_state") != "UNKNOWN":
            raise RuntimeError("EFFECT_NOT_UNKNOWN")
        if not effect_id or effect_id != m.get("effect_id"):
            raise RuntimeError("EFFECT_ID_MISMATCH")
        if not proof_ref.strip():
            raise ValueError("PROOF_REF_REQUIRED")
        rb = readback.upper()
        if rb not in {"MATCH", "ABSENT", "CONFLICT", "UNKNOWN"}:
            raise ValueError("INVALID_READBACK")
        if rb in {"CONFLICT", "UNKNOWN"}:
            return self._append(
                mission_id, "READBACK_HOLD", "REALITY_GUARD", m["state"], "HELD",
                attempt=m["attempt"], fence=fence, effect_id=effect_id, effect_state=rb,
                notes=f"proof={proof_ref}",
            )
        m["effect_proof_ref"] = proof_ref
        self._save()
        return self._append(
            mission_id, "EFFECT_READBACK", actor, m["state"], m["state"],
            attempt=m["attempt"], fence=fence, effect_id=effect_id, effect_state=rb,
            notes=f"proof={proof_ref}",
        )

    def import_external_result(self, mission_id: str, *, verifier: str, effect_id: str,
                               result: object, proof_ref: str) -> WorkPlaneEvent:
        """Terminally reconcile a stale interrupted UNKNOWN effect after exact MATCH proof.

        This does not replay the effect.  It is legal only after the original lease is stale,
        when the effect id matches the interrupted mission and an independent proof reference
        is supplied.
        """
        m = self._mission(mission_id)
        if m["state"] in TERMINAL_STATES:
            raise RuntimeError("MISSION_TERMINAL")
        if int(m.get("lease_until_ns", 0)) > time.time_ns():
            raise RuntimeError("LEASE_NOT_STALE")
        if m.get("effect_state") != "UNKNOWN":
            raise RuntimeError("EFFECT_NOT_UNKNOWN")
        if not effect_id or effect_id != m.get("effect_id"):
            raise RuntimeError("EFFECT_ID_MISMATCH")
        if not verifier.strip() or not proof_ref.strip():
            raise ValueError("VERIFIER_AND_PROOF_REQUIRED")
        m["effect_proof_ref"] = proof_ref
        self._save()
        return self._append(
            mission_id, "EXTERNAL_RESULT_IMPORTED", verifier, m["state"], "RESULT_READY",
            attempt=m["attempt"], fence=m["fence"], result_hash=digest(result),
            effect_id=effect_id, effect_state="MATCH", notes=f"proof={proof_ref};no_effect_replay=true",
        )

    def projection(self, mission_id: str) -> Projection:
        m = self._mission(mission_id)
        return Projection(
            mission_id=mission_id, state=m["state"], actor=m.get("actor"), attempt=int(m["attempt"]),
            fence=int(m["fence"]), last_event_id=m.get("last_event_id"), last_event_time_ns=int(m.get("last_event_time_ns", 0)),
            heartbeat_ns=int(m.get("heartbeat_ns", 0)), lease_until_ns=int(m.get("lease_until_ns", 0)),
            checkpoint_hash=m.get("checkpoint_hash"), result_hash=m.get("result_hash"),
            effect_state=m.get("effect_state", "NONE"), interruption_state=self.detect_interruption(mission_id),
        )


@dataclass(frozen=True, slots=True)
class TypedCommand:
    kind: str
    argv: tuple[str, ...]

    def validate(self) -> None:
        if self.kind == "GIT":
            if not self.argv or self.argv[0] != "git" or len(self.argv) < 2 or self.argv[1] not in _ALLOWED_GIT_SUBCOMMANDS:
                raise PermissionError("GIT_SUBCOMMAND_NOT_ALLOWED")
            return
        if self.kind == "PYTHON_MODULE":
            if len(self.argv) < 3 or Path(self.argv[0]).name not in {"python", "python3"} or self.argv[1] != "-m" or self.argv[2] not in _ALLOWED_PYTHON_MODULES:
                raise PermissionError("PYTHON_MODULE_NOT_ALLOWED")
            if "-c" in self.argv:
                raise PermissionError("INLINE_PYTHON_FORBIDDEN")
            return
        raise PermissionError("COMMAND_KIND_NOT_ALLOWED")


def run_typed_command(command: TypedCommand, cwd: str | os.PathLike[str], timeout_seconds: int = 300) -> subprocess.CompletedProcess[bytes]:
    command.validate()
    root = Path(cwd).resolve()
    root.mkdir(parents=True, exist_ok=True)
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONNOUSERSITE": "1"}
    return subprocess.run(list(command.argv), cwd=str(root), env=env, capture_output=True, timeout=timeout_seconds, check=False)
