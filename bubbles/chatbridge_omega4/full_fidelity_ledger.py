from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


class LedgerError(RuntimeError):
    """Base error for the full-fidelity conversation ledger."""


class ConversationNotBound(LedgerError):
    pass


class ConversationIdentityConflict(LedgerError):
    pass


class TranscriptConflict(LedgerError):
    pass


class TranscriptGap(LedgerError):
    pass


class TranscriptIntegrityError(LedgerError):
    pass


class IncompleteTranscript(LedgerError):
    pass


class TerminalExecutionClaimError(LedgerError):
    pass


class ConversationRole(str, Enum):
    SYSTEM = "SYSTEM"
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    TOOL = "TOOL"
    CONNECTOR = "CONNECTOR"
    DEVELOPER = "DEVELOPER"
    UNKNOWN = "UNKNOWN"


class ConversationEventType(str, Enum):
    MESSAGE = "MESSAGE"
    TOOL_CALL = "TOOL_CALL"
    TOOL_RESULT = "TOOL_RESULT"
    ATTACHMENT = "ATTACHMENT"
    DECISION = "DECISION"
    CORRECTION = "CORRECTION"
    CHECKPOINT = "CHECKPOINT"
    TERMINAL_WARNING = "TERMINAL_WARNING"
    MIGRATION = "MIGRATION"
    OTHER = "OTHER"


class EventExecutionState(str, Enum):
    OBSERVED = "OBSERVED"
    ATTEMPTED = "ATTEMPTED"
    EXECUTED_VERIFIED = "EXECUTED_VERIFIED"
    FAILED_VERIFIED = "FAILED_VERIFIED"
    NOT_EXECUTED_TERMINAL = "NOT_EXECUTED_TERMINAL"
    UNVERIFIED = "UNVERIFIED"


class PayloadAvailability(str, Enum):
    RAW_GOVERNED = "RAW_GOVERNED"
    REDACTED = "REDACTED"
    HASH_ONLY = "HASH_ONLY"
    POINTER_ONLY = "POINTER_ONLY"


class ArtifactAvailability(str, Enum):
    VERIFIED_AVAILABLE = "VERIFIED_AVAILABLE"
    POINTER_ONLY = "POINTER_ONLY"
    MISSING = "MISSING"
    UNVERIFIED = "UNVERIFIED"


class TranscriptIntegrityState(str, Enum):
    PASS_EXACT = "PASS_EXACT"
    PASS_BOUNDED = "PASS_BOUNDED"
    FAIL_HASH_CHAIN = "FAIL_HASH_CHAIN"
    EMPTY = "EMPTY"


class TranscriptRestoreMode(str, Enum):
    EXACT_TRANSCRIPT_RESTORE = "EXACT_TRANSCRIPT_RESTORE"
    BOUNDED_TRANSCRIPT_RESTORE = "BOUNDED_TRANSCRIPT_RESTORE"
    REJECT_TAMPERED = "REJECT_TAMPERED"
    NO_TRANSCRIPT = "NO_TRANSCRIPT"


@dataclass(frozen=True)
class ArtifactReference:
    artifact_key: str
    filename: str = ""
    mime_type: str = ""
    size_bytes: int = 0
    sha256: str = ""
    locator: str = ""
    availability: ArtifactAvailability = ArtifactAvailability.VERIFIED_AVAILABLE
    required_for_context: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_key": self.artifact_key,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size_bytes": int(self.size_bytes),
            "sha256": self.sha256,
            "locator": self.locator,
            "availability": self.availability.value,
            "required_for_context": bool(self.required_for_context),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ArtifactReference":
        return cls(
            artifact_key=str(payload.get("artifact_key", "")),
            filename=str(payload.get("filename", "")),
            mime_type=str(payload.get("mime_type", "")),
            size_bytes=int(payload.get("size_bytes", 0) or 0),
            sha256=str(payload.get("sha256", "")),
            locator=str(payload.get("locator", "")),
            availability=ArtifactAvailability(
                payload.get(
                    "availability",
                    ArtifactAvailability.UNVERIFIED.value,
                )
            ),
            required_for_context=bool(payload.get("required_for_context", True)),
        )


@dataclass(frozen=True)
class ConversationEvent:
    conversation_key: str
    sequence: int
    role: ConversationRole
    event_type: ConversationEventType
    content: Any
    occurred_at: str
    source_turn_id: str = ""
    provider_event_id: str = ""
    idempotency_key: str = ""
    execution_state: EventExecutionState = EventExecutionState.OBSERVED
    payload_availability: PayloadAvailability = PayloadAvailability.RAW_GOVERNED
    sensitivity: str = "GOVERNED_LOCAL"
    artifacts: Tuple[ArtifactReference, ...] = field(default_factory=tuple)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def hash_material(self) -> Dict[str, Any]:
        return {
            "conversation_key": self.conversation_key.strip(),
            "sequence": int(self.sequence),
            "role": self.role.value,
            "event_type": self.event_type.value,
            "content": self.content,
            "occurred_at": self.occurred_at,
            "source_turn_id": self.source_turn_id,
            "provider_event_id": self.provider_event_id,
            "execution_state": self.execution_state.value,
            "payload_availability": self.payload_availability.value,
            "sensitivity": self.sensitivity,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> Dict[str, Any]:
        payload = self.hash_material()
        payload["idempotency_key"] = self.idempotency_key
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ConversationEvent":
        return cls(
            conversation_key=str(payload["conversation_key"]),
            sequence=int(payload["sequence"]),
            role=ConversationRole(payload.get("role", ConversationRole.UNKNOWN.value)),
            event_type=ConversationEventType(
                payload.get("event_type", ConversationEventType.OTHER.value)
            ),
            content=payload.get("content"),
            occurred_at=str(payload.get("occurred_at", "")),
            source_turn_id=str(payload.get("source_turn_id", "")),
            provider_event_id=str(payload.get("provider_event_id", "")),
            idempotency_key=str(payload.get("idempotency_key", "")),
            execution_state=EventExecutionState(
                payload.get("execution_state", EventExecutionState.UNVERIFIED.value)
            ),
            payload_availability=PayloadAvailability(
                payload.get(
                    "payload_availability",
                    PayloadAvailability.POINTER_ONLY.value,
                )
            ),
            sensitivity=str(payload.get("sensitivity", "GOVERNED_LOCAL")),
            artifacts=tuple(
                ArtifactReference.from_dict(item)
                for item in payload.get("artifacts", [])
            ),
            metadata=dict(payload.get("metadata", {})),
        )


def _now() -> float:
    return time.time()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _conversation_key(value: str) -> str:
    key = value.strip()
    if not key:
        raise ValueError("conversation_key cannot be blank")
    return key


def _namespace_key(value: str) -> str:
    key = value.strip().casefold()
    if not key:
        raise ValueError("namespace_key cannot be blank")
    return key


def _merkle_root(hashes: Sequence[str]) -> str:
    if not hashes:
        return ""
    level = list(hashes)
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            hashlib.sha256((level[index] + level[index + 1]).encode("utf-8")).hexdigest()
            for index in range(0, len(level), 2)
        ]
    return level[0]


def _missing_ranges(
    sequences: Sequence[int],
    expected_first: Optional[int],
    expected_last: Optional[int],
) -> List[Dict[str, int]]:
    if not sequences:
        if expected_first is not None and expected_last is not None:
            return [{"start": expected_first, "end": expected_last}]
        return []

    start = expected_first if expected_first is not None else sequences[0]
    end = expected_last if expected_last is not None else sequences[-1]
    if end < start:
        return []

    present = set(sequences)
    missing: List[Dict[str, int]] = []
    range_start: Optional[int] = None
    for sequence in range(start, end + 1):
        if sequence not in present:
            if range_start is None:
                range_start = sequence
        elif range_start is not None:
            missing.append({"start": range_start, "end": sequence - 1})
            range_start = None
    if range_start is not None:
        missing.append({"start": range_start, "end": end})
    return missing


class FullFidelityConversationLedger:
    """Append-only, hash-chained conversation record for ChatBridge Ω4.8.

    The ledger is deliberately provider-neutral. A connected adapter must submit each
    observed message, tool call/result, attachment reference, correction and terminal
    warning. The core can then prove exact coverage, or expose explicit missing ranges;
    it never invents uncaptured turns.
    """

    VERSION = "FFCL-1.0"
    CAPTURE_POLICY = "EVERY_OBSERVED_TURN_AND_PROVIDER_EVENT_APPEND_ONLY"
    RESTORE_POLICY = "EXACT_IF_COMPLETE_ELSE_BOUNDED_WITH_GAP_MANIFEST_NEVER_GUESS"

    def __init__(self, path: str) -> None:
        self.path = path
        self._local = threading.local()
        self._bootstrap()

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                self.path,
                timeout=30,
                isolation_level=None,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    def _bootstrap(self) -> None:
        conn = sqlite3.connect(self.path)
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS conversation_ledgers(
                conversation_key TEXT PRIMARY KEY,
                namespace_key TEXT NOT NULL,
                source_provider TEXT NOT NULL,
                title TEXT NOT NULL,
                capture_policy TEXT NOT NULL,
                privacy_policy TEXT NOT NULL,
                expected_first_sequence INTEGER,
                expected_last_sequence INTEGER,
                first_sequence INTEGER,
                last_sequence INTEGER,
                last_event_hash TEXT NOT NULL,
                terminal_observed INTEGER NOT NULL,
                closure_reason TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversation_events(
                event_id TEXT PRIMARY KEY,
                conversation_key TEXT NOT NULL
                    REFERENCES conversation_ledgers(conversation_key),
                sequence INTEGER NOT NULL,
                role TEXT NOT NULL,
                event_type TEXT NOT NULL,
                content_json TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                source_turn_id TEXT NOT NULL,
                provider_event_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                execution_state TEXT NOT NULL,
                payload_availability TEXT NOT NULL,
                sensitivity TEXT NOT NULL,
                artifacts_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                previous_event_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL,
                captured_at REAL NOT NULL,
                UNIQUE(conversation_key, sequence),
                UNIQUE(conversation_key, idempotency_key)
            );

            CREATE TABLE IF NOT EXISTS conversation_ledger_events(
                ledger_event_id TEXT PRIMARY KEY,
                conversation_key TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_conversation_events_sequence
                ON conversation_events(conversation_key, sequence);
            """
        )
        conn.close()

    def _audit(
        self,
        conn: sqlite3.Connection,
        conversation_key: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        conn.execute(
            "INSERT INTO conversation_ledger_events VALUES(?,?,?,?,?)",
            (
                f"ffcl_evt_{uuid.uuid4().hex}",
                conversation_key,
                event_type,
                _canonical_json(payload),
                _now(),
            ),
        )

    def bind(
        self,
        conversation_key: str,
        namespace_key: str,
        *,
        source_provider: str = "CHATGPT",
        title: str = "",
        expected_first_sequence: int = 1,
        privacy_policy: str = "GOVERNED_LOCAL_MINIMUM_NECESSARY_ACCESS",
    ) -> Dict[str, Any]:
        key = _conversation_key(conversation_key)
        namespace = _namespace_key(namespace_key)
        if expected_first_sequence < 1:
            raise ValueError("expected_first_sequence must be >= 1")
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT * FROM conversation_ledgers WHERE conversation_key=?",
                (key,),
            ).fetchone()
            if row:
                if (
                    row["namespace_key"] != namespace
                    or row["source_provider"] != source_provider
                ):
                    raise ConversationIdentityConflict(
                        "conversation is already bound to a different namespace or provider"
                    )
                if (
                    row["expected_first_sequence"] is not None
                    and int(row["expected_first_sequence"]) != expected_first_sequence
                ):
                    raise ConversationIdentityConflict(
                        "expected first sequence conflicts with the existing binding"
                    )
                conn.execute("COMMIT")
                result = dict(row)
                result["reused"] = True
                return result

            now = _now()
            conn.execute(
                """
                INSERT INTO conversation_ledgers(
                    conversation_key,namespace_key,source_provider,title,capture_policy,
                    privacy_policy,expected_first_sequence,expected_last_sequence,
                    first_sequence,last_sequence,last_event_hash,terminal_observed,
                    closure_reason,status,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    key,
                    namespace,
                    source_provider,
                    title,
                    self.CAPTURE_POLICY,
                    privacy_policy,
                    expected_first_sequence,
                    None,
                    None,
                    None,
                    "",
                    0,
                    "",
                    "OPEN",
                    now,
                    now,
                ),
            )
            self._audit(
                conn,
                key,
                "CONVERSATION_BOUND",
                {
                    "namespace_key": namespace,
                    "source_provider": source_provider,
                    "expected_first_sequence": expected_first_sequence,
                },
            )
            verify = conn.execute(
                "SELECT * FROM conversation_ledgers WHERE conversation_key=?",
                (key,),
            ).fetchone()
            if not verify:
                raise RuntimeError("conversation binding readback failed")
            conn.execute("COMMIT")
            result = dict(verify)
            result["reused"] = False
            return result
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def _row_to_event(self, row: sqlite3.Row) -> ConversationEvent:
        return ConversationEvent(
            conversation_key=row["conversation_key"],
            sequence=int(row["sequence"]),
            role=ConversationRole(row["role"]),
            event_type=ConversationEventType(row["event_type"]),
            content=json.loads(row["content_json"]),
            occurred_at=row["occurred_at"],
            source_turn_id=row["source_turn_id"],
            provider_event_id=row["provider_event_id"],
            idempotency_key=row["idempotency_key"],
            execution_state=EventExecutionState(row["execution_state"]),
            payload_availability=PayloadAvailability(row["payload_availability"]),
            sensitivity=row["sensitivity"],
            artifacts=tuple(
                ArtifactReference.from_dict(item)
                for item in json.loads(row["artifacts_json"])
            ),
            metadata=json.loads(row["metadata_json"]),
        )

    def _event_hashes(
        self,
        event: ConversationEvent,
        previous_event_hash: str,
    ) -> Tuple[str, str]:
        content_hash = _digest(event.hash_material())
        event_hash = _digest(
            {
                "conversation_key": event.conversation_key.strip(),
                "sequence": int(event.sequence),
                "previous_event_hash": previous_event_hash,
                "content_hash": content_hash,
            }
        )
        return content_hash, event_hash

    def _idempotency_key(self, event: ConversationEvent, content_hash: str) -> str:
        return event.idempotency_key.strip() or _digest(
            {
                "conversation_key": event.conversation_key.strip(),
                "sequence": int(event.sequence),
                "content_hash": content_hash,
            }
        )

    def _append_locked(
        self,
        conn: sqlite3.Connection,
        event: ConversationEvent,
        *,
        allow_gap: bool,
    ) -> Dict[str, Any]:
        key = _conversation_key(event.conversation_key)
        if event.sequence < 1:
            raise ValueError("event sequence must be >= 1")
        ledger = conn.execute(
            "SELECT * FROM conversation_ledgers WHERE conversation_key=?",
            (key,),
        ).fetchone()
        if not ledger:
            raise ConversationNotBound(key)
        if ledger["status"].startswith("SEALED"):
            raise TranscriptConflict("sealed conversations are immutable")

        expected_next = (
            int(ledger["last_sequence"]) + 1
            if ledger["last_sequence"] is not None
            else int(ledger["expected_first_sequence"])
        )

        existing_sequence = conn.execute(
            """
            SELECT * FROM conversation_events
            WHERE conversation_key=? AND sequence=?
            """,
            (key, event.sequence),
        ).fetchone()
        previous_hash = ledger["last_event_hash"]
        content_hash, event_hash = self._event_hashes(event, previous_hash)
        idempotency_key = self._idempotency_key(event, content_hash)

        if existing_sequence:
            existing_event = self._row_to_event(existing_sequence)
            existing_content_hash, _ = self._event_hashes(
                existing_event,
                existing_sequence["previous_event_hash"],
            )
            if existing_content_hash == content_hash:
                return {
                    "state": "EVENT_REUSED_IDEMPOTENT",
                    "conversation_key": key,
                    "sequence": int(event.sequence),
                    "event_hash": existing_sequence["event_hash"],
                    "content_hash": existing_sequence["content_hash"],
                    "reused": True,
                }
            raise TranscriptConflict(
                f"sequence {event.sequence} already contains different content"
            )

        existing_idempotency = conn.execute(
            """
            SELECT * FROM conversation_events
            WHERE conversation_key=? AND idempotency_key=?
            """,
            (key, idempotency_key),
        ).fetchone()
        if existing_idempotency:
            if (
                int(existing_idempotency["sequence"]) == int(event.sequence)
                and existing_idempotency["content_hash"] == content_hash
            ):
                return {
                    "state": "EVENT_REUSED_IDEMPOTENT",
                    "conversation_key": key,
                    "sequence": int(event.sequence),
                    "event_hash": existing_idempotency["event_hash"],
                    "content_hash": existing_idempotency["content_hash"],
                    "reused": True,
                }
            raise TranscriptConflict("idempotency key is already bound to different content")

        if event.sequence != expected_next:
            if event.sequence < expected_next:
                raise TranscriptConflict(
                    f"event sequence {event.sequence} is behind next sequence {expected_next}"
                )
            if not allow_gap:
                raise TranscriptGap(
                    f"missing event range {expected_next}-{event.sequence - 1}"
                )

        event_id = f"ffcl_turn_{uuid.uuid4().hex}"
        now = _now()
        conn.execute(
            """
            INSERT INTO conversation_events(
                event_id,conversation_key,sequence,role,event_type,content_json,
                occurred_at,source_turn_id,provider_event_id,idempotency_key,
                execution_state,payload_availability,sensitivity,artifacts_json,
                metadata_json,content_hash,previous_event_hash,event_hash,captured_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                event_id,
                key,
                int(event.sequence),
                event.role.value,
                event.event_type.value,
                _canonical_json(event.content),
                event.occurred_at,
                event.source_turn_id,
                event.provider_event_id,
                idempotency_key,
                event.execution_state.value,
                event.payload_availability.value,
                event.sensitivity,
                _canonical_json(
                    [artifact.to_dict() for artifact in event.artifacts]
                ),
                _canonical_json(dict(event.metadata)),
                content_hash,
                previous_hash,
                event_hash,
                now,
            ),
        )
        first_sequence = (
            int(ledger["first_sequence"])
            if ledger["first_sequence"] is not None
            else int(event.sequence)
        )
        terminal_observed = bool(ledger["terminal_observed"]) or (
            event.event_type == ConversationEventType.TERMINAL_WARNING
        )
        conn.execute(
            """
            UPDATE conversation_ledgers
            SET first_sequence=?,last_sequence=?,last_event_hash=?,
                terminal_observed=?,updated_at=?
            WHERE conversation_key=?
            """,
            (
                first_sequence,
                int(event.sequence),
                event_hash,
                int(terminal_observed),
                now,
                key,
            ),
        )
        self._audit(
            conn,
            key,
            "EVENT_CAPTURED",
            {
                "event_id": event_id,
                "sequence": int(event.sequence),
                "event_hash": event_hash,
                "content_hash": content_hash,
                "gap_allowed": allow_gap,
            },
        )
        verify = conn.execute(
            """
            SELECT event_hash,content_hash FROM conversation_events
            WHERE conversation_key=? AND sequence=?
            """,
            (key, int(event.sequence)),
        ).fetchone()
        if (
            not verify
            or verify["event_hash"] != event_hash
            or verify["content_hash"] != content_hash
        ):
            raise RuntimeError("conversation event readback failed")
        return {
            "state": "EVENT_CAPTURED_VERIFIED",
            "conversation_key": key,
            "sequence": int(event.sequence),
            "event_id": event_id,
            "event_hash": event_hash,
            "content_hash": content_hash,
            "previous_event_hash": previous_hash,
            "idempotency_key": idempotency_key,
            "reused": False,
        }

    def append(
        self,
        event: ConversationEvent,
        *,
        allow_gap: bool = False,
    ) -> Dict[str, Any]:
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            result = self._append_locked(conn, event, allow_gap=allow_gap)
            conn.execute("COMMIT")
            return result
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def append_many(
        self,
        events: Iterable[ConversationEvent],
        *,
        allow_gap: bool = False,
    ) -> Dict[str, Any]:
        items = list(events)
        if not items:
            return {"state": "NO_EVENTS", "captured": 0, "receipts": []}
        keys = {_conversation_key(item.conversation_key) for item in items}
        if len(keys) != 1:
            raise ConversationIdentityConflict(
                "one atomic batch cannot span multiple conversations"
            )
        sequences = [int(item.sequence) for item in items]
        if sequences != sorted(sequences):
            raise ValueError("events must be supplied in ascending sequence order")
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            receipts = [
                self._append_locked(conn, item, allow_gap=allow_gap)
                for item in items
            ]
            conn.execute("COMMIT")
            return {
                "state": "EVENT_BATCH_CAPTURED_VERIFIED",
                "conversation_key": items[0].conversation_key.strip(),
                "captured": sum(not item["reused"] for item in receipts),
                "reused": sum(bool(item["reused"]) for item in receipts),
                "receipts": receipts,
            }
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def _events(self, conversation_key: str) -> List[sqlite3.Row]:
        key = _conversation_key(conversation_key)
        return list(
            self._conn()
            .execute(
                """
                SELECT * FROM conversation_events
                WHERE conversation_key=?
                ORDER BY sequence ASC
                """,
                (key,),
            )
            .fetchall()
        )

    def verify(self, conversation_key: str) -> Dict[str, Any]:
        key = _conversation_key(conversation_key)
        ledger = self._conn().execute(
            "SELECT * FROM conversation_ledgers WHERE conversation_key=?",
            (key,),
        ).fetchone()
        if not ledger:
            raise ConversationNotBound(key)
        rows = self._events(key)
        if not rows:
            return {
                "conversation_key": key,
                "namespace_key": ledger["namespace_key"],
                "integrity_state": TranscriptIntegrityState.EMPTY.value,
                "restore_mode": TranscriptRestoreMode.NO_TRANSCRIPT.value,
                "exact_context_complete": False,
                "sealed": ledger["status"].startswith("SEALED"),
                "event_count": 0,
                "missing_ranges": _missing_ranges(
                    [],
                    ledger["expected_first_sequence"],
                    ledger["expected_last_sequence"],
                ),
                "chain_head_hash": "",
                "merkle_root": "",
                "unavailable_sequences": [],
                "unresolved_artifacts": [],
                "truth_boundary": "NO_TRANSCRIPT_CAPTURED",
            }

        chain_valid = True
        findings: List[Dict[str, Any]] = []
        previous_hash = ""
        sequences: List[int] = []
        event_hashes: List[str] = []
        unavailable_sequences: List[int] = []
        unresolved_artifacts: List[Dict[str, Any]] = []
        role_counts: Dict[str, int] = {}

        for row in rows:
            event = self._row_to_event(row)
            sequences.append(event.sequence)
            role_counts[event.role.value] = role_counts.get(event.role.value, 0) + 1
            recomputed_content_hash, recomputed_event_hash = self._event_hashes(
                event,
                previous_hash,
            )
            if row["previous_event_hash"] != previous_hash:
                chain_valid = False
                findings.append(
                    {
                        "sequence": event.sequence,
                        "finding": "PREVIOUS_HASH_MISMATCH",
                    }
                )
            if row["content_hash"] != recomputed_content_hash:
                chain_valid = False
                findings.append(
                    {
                        "sequence": event.sequence,
                        "finding": "CONTENT_HASH_MISMATCH",
                    }
                )
            if row["event_hash"] != recomputed_event_hash:
                chain_valid = False
                findings.append(
                    {
                        "sequence": event.sequence,
                        "finding": "EVENT_HASH_MISMATCH",
                    }
                )
            if event.payload_availability != PayloadAvailability.RAW_GOVERNED:
                unavailable_sequences.append(event.sequence)
            for artifact in event.artifacts:
                if (
                    artifact.required_for_context
                    and artifact.availability
                    != ArtifactAvailability.VERIFIED_AVAILABLE
                ):
                    unresolved_artifacts.append(
                        {
                            "sequence": event.sequence,
                            "artifact_key": artifact.artifact_key,
                            "availability": artifact.availability.value,
                            "locator": artifact.locator,
                        }
                    )
            previous_hash = row["event_hash"]
            event_hashes.append(row["event_hash"])

        expected_first = (
            int(ledger["expected_first_sequence"])
            if ledger["expected_first_sequence"] is not None
            else sequences[0]
        )
        expected_last = (
            int(ledger["expected_last_sequence"])
            if ledger["expected_last_sequence"] is not None
            else None
        )
        missing = _missing_ranges(sequences, expected_first, expected_last)
        sealed = ledger["status"].startswith("SEALED")
        exact = (
            chain_valid
            and sealed
            and expected_last is not None
            and sequences[0] == expected_first
            and sequences[-1] == expected_last
            and not missing
            and not unavailable_sequences
            and not unresolved_artifacts
        )

        if not chain_valid:
            integrity = TranscriptIntegrityState.FAIL_HASH_CHAIN
            restore_mode = TranscriptRestoreMode.REJECT_TAMPERED
        elif exact:
            integrity = TranscriptIntegrityState.PASS_EXACT
            restore_mode = TranscriptRestoreMode.EXACT_TRANSCRIPT_RESTORE
        else:
            integrity = TranscriptIntegrityState.PASS_BOUNDED
            restore_mode = TranscriptRestoreMode.BOUNDED_TRANSCRIPT_RESTORE

        expected_count = (
            expected_last - expected_first + 1
            if expected_last is not None and expected_last >= expected_first
            else None
        )
        coverage_percent = (
            round((len(sequences) / expected_count) * 100, 4)
            if expected_count
            else None
        )
        return {
            "conversation_key": key,
            "namespace_key": ledger["namespace_key"],
            "source_provider": ledger["source_provider"],
            "title": ledger["title"],
            "status": ledger["status"],
            "integrity_state": integrity.value,
            "restore_mode": restore_mode.value,
            "exact_context_complete": exact,
            "start_to_finish_guarantee": exact,
            "sealed": sealed,
            "terminal_observed": bool(ledger["terminal_observed"]),
            "closure_reason": ledger["closure_reason"],
            "event_count": len(rows),
            "role_counts": role_counts,
            "first_sequence": sequences[0],
            "last_sequence": sequences[-1],
            "expected_first_sequence": expected_first,
            "expected_last_sequence": expected_last,
            "missing_ranges": missing,
            "unavailable_sequences": unavailable_sequences,
            "unresolved_artifacts": unresolved_artifacts,
            "coverage_percent": coverage_percent,
            "chain_head_hash": event_hashes[-1],
            "merkle_root": _merkle_root(event_hashes),
            "findings": findings,
            "truth_boundary": (
                "EXACT_START_TO_FINISH_CAPTURE_VERIFIED"
                if exact
                else "BOUNDED_CAPTURE_GAPS_OR_EXTERNAL_DEPENDENCIES_EXPLICIT"
            ),
        }

    def seal(
        self,
        conversation_key: str,
        *,
        expected_last_sequence: int,
        expected_first_sequence: int = 1,
        closure_reason: str = "MIGRATED_OR_COMPLETED",
        terminal_observed: bool = False,
    ) -> Dict[str, Any]:
        key = _conversation_key(conversation_key)
        if expected_first_sequence < 1:
            raise ValueError("expected_first_sequence must be >= 1")
        if expected_last_sequence < expected_first_sequence:
            raise ValueError("expected_last_sequence cannot precede expected_first_sequence")
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            ledger = conn.execute(
                "SELECT * FROM conversation_ledgers WHERE conversation_key=?",
                (key,),
            ).fetchone()
            if not ledger:
                raise ConversationNotBound(key)
            conn.execute(
                """
                UPDATE conversation_ledgers
                SET expected_first_sequence=?,expected_last_sequence=?,
                    terminal_observed=?,closure_reason=?,status='SEALED_PENDING_VERIFY',
                    updated_at=?
                WHERE conversation_key=?
                """,
                (
                    expected_first_sequence,
                    expected_last_sequence,
                    int(bool(ledger["terminal_observed"]) or terminal_observed),
                    closure_reason,
                    _now(),
                    key,
                ),
            )
            self._audit(
                conn,
                key,
                "CONVERSATION_SEALED",
                {
                    "expected_first_sequence": expected_first_sequence,
                    "expected_last_sequence": expected_last_sequence,
                    "closure_reason": closure_reason,
                    "terminal_observed": terminal_observed,
                },
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        verification = self.verify(key)
        final_status = (
            "SEALED_EXACT"
            if verification["exact_context_complete"]
            else "SEALED_BOUNDED"
        )
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """
                UPDATE conversation_ledgers SET status=?,updated_at=?
                WHERE conversation_key=?
                """,
                (final_status, _now(), key),
            )
            self._audit(
                conn,
                key,
                "SEAL_VERIFIED",
                {
                    "status": final_status,
                    "integrity_state": verification["integrity_state"],
                    "missing_ranges": verification["missing_ranges"],
                    "chain_head_hash": verification["chain_head_hash"],
                    "merkle_root": verification["merkle_root"],
                },
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return self.verify(key)

    def reconstruct(
        self,
        conversation_key: str,
        *,
        require_exact: bool = False,
    ) -> Dict[str, Any]:
        verification = self.verify(conversation_key)
        if (
            verification["integrity_state"]
            == TranscriptIntegrityState.FAIL_HASH_CHAIN.value
        ):
            raise TranscriptIntegrityError(
                "conversation ledger hash-chain verification failed"
            )
        if require_exact and not verification["exact_context_complete"]:
            raise IncompleteTranscript(
                "exact transcript is unavailable; inspect missing_ranges, payload "
                "availability and artifact dependencies"
            )

        events = [
            {
                **self._row_to_event(row).to_dict(),
                "event_id": row["event_id"],
                "content_hash": row["content_hash"],
                "previous_event_hash": row["previous_event_hash"],
                "event_hash": row["event_hash"],
                "captured_at": float(row["captured_at"]),
            }
            for row in self._events(conversation_key)
        ]
        return {
            "conversation_key": verification["conversation_key"],
            "namespace_key": verification["namespace_key"],
            "restore_mode": verification["restore_mode"],
            "exact_context_complete": verification["exact_context_complete"],
            "transcript": events,
            "context_manifest": {
                "event_count": verification["event_count"],
                "expected_first_sequence": verification[
                    "expected_first_sequence"
                ],
                "expected_last_sequence": verification["expected_last_sequence"],
                "missing_ranges": verification["missing_ranges"],
                "unavailable_sequences": verification["unavailable_sequences"],
                "unresolved_artifacts": verification["unresolved_artifacts"],
                "chain_head_hash": verification["chain_head_hash"],
                "merkle_root": verification["merkle_root"],
                "terminal_observed": verification["terminal_observed"],
                "closure_reason": verification["closure_reason"],
            },
            "proof": verification,
            "reconstruction_policy": (
                "REPLAY_CAPTURED_EVENTS_IN_SEQUENCE_NEVER_SYNTHESIZE_GAPS"
            ),
        }

    def status(self, conversation_key: str) -> Dict[str, Any]:
        key = _conversation_key(conversation_key)
        ledger = self._conn().execute(
            "SELECT * FROM conversation_ledgers WHERE conversation_key=?",
            (key,),
        ).fetchone()
        if not ledger:
            raise ConversationNotBound(key)
        return {**dict(ledger), "verification": self.verify(key)}

    def list_conversations(self) -> List[Dict[str, Any]]:
        return [
            dict(row)
            for row in self._conn()
            .execute(
                """
                SELECT * FROM conversation_ledgers
                ORDER BY updated_at DESC
                """
            )
            .fetchall()
        ]

    @classmethod
    def contract(cls) -> Dict[str, Any]:
        return {
            "version": cls.VERSION,
            "capture": cls.CAPTURE_POLICY,
            "restore": cls.RESTORE_POLICY,
            "identity": "EXACT_CONVERSATION_KEY_BOUND_TO_EXACT_NAMESPACE",
            "ordering": "MONOTONIC_SEQUENCE_APPEND_ONLY",
            "integrity": "SHA256_CONTENT_HASH_PLUS_PREVIOUS_EVENT_HASH_CHAIN_AND_MERKLE_ROOT",
            "coverage": "EXPECTED_START_END_WATERMARK_PLUS_EXPLICIT_MISSING_RANGES",
            "artifacts": "STABLE_REFERENCE_HASH_AVAILABILITY_MANIFEST",
            "terminal_rule": "TERMINAL_INTENT_IS_NOT_EXECUTION",
            "correction_rule": "APPEND_CORRECTION_EVENT_NEVER_REWRITE_HISTORY",
            "privacy": "GOVERNED_LOCAL_RAW_OR_EXPLICITLY_DOWNGRADED_AVAILABILITY",
            "legacy_rule": "IMPORT_WHAT_EXISTS_MARK_GAPS_NEVER_GUESS",
            "provider_boundary": (
                "CONNECTED_ADAPTER_MUST_SUPPLY_EVENTS; NO_INVISIBLE_NATIVE_CHAT_ACCESS"
            ),
        }
