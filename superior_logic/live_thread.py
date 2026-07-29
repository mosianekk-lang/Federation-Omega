from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .live_thread_ui import render_live_thread_page, render_live_thread_root

ROOM_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
GENESIS_HASH = "0" * 64
MAX_HISTORY = 200
DEFAULT_MODEL = "gpt-5-mini"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_room_id(room_id: str) -> str:
    if not ROOM_ID_PATTERN.fullmatch(room_id):
        raise HTTPException(status_code=404, detail="Room not found.")
    return room_id


def canonical_hash(
    *,
    room_id: str,
    seq: int,
    sender: str,
    role: str,
    content: str,
    created_at: str,
    previous_hash: str,
) -> str:
    payload = {
        "room_id": room_id,
        "seq": seq,
        "sender": sender,
        "role": role,
        "content": content,
        "created_at": created_at,
        "previous_hash": previous_hash,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class MessageCreate(BaseModel):
    sender: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=12_000)
    request_ai: bool = True


class MessageRecord(BaseModel):
    room_id: str
    seq: int
    message_id: str
    sender: str
    role: str
    content: str
    created_at: str
    previous_hash: str
    content_hash: str


class DraftRecord(BaseModel):
    job_id: str
    trigger_seq: int
    sender: str = "Shared AI"
    content: str = ""
    state: str
    updated_at: str
    error_code: str | None = None


class RoomSnapshot(BaseModel):
    room_id: str
    messages: list[MessageRecord]
    draft: DraftRecord | None = None
    head_hash: str = GENESIS_HASH
    chain_valid: bool = True
    ai_ready: bool = False
    poll_after_ms: int = 900


class LiveThreadStore(Protocol):
    def append_message(
        self,
        *,
        room_id: str,
        sender: str,
        role: str,
        content: str,
    ) -> MessageRecord: ...

    def list_messages(
        self,
        *,
        room_id: str,
        after_seq: int = 0,
        limit: int = MAX_HISTORY,
    ) -> list[MessageRecord]: ...

    def room_snapshot(self, *, room_id: str, after_seq: int = 0) -> RoomSnapshot: ...

    def claim_ai_job(self, *, room_id: str, trigger_seq: int, job_id: str) -> bool: ...

    def update_draft(
        self,
        *,
        room_id: str,
        draft: DraftRecord | None,
        last_ai_trigger_seq: int | None = None,
    ) -> None: ...

    def health(self) -> dict[str, Any]: ...


@dataclass
class _MemoryRoom:
    messages: list[MessageRecord]
    draft: DraftRecord | None = None
    last_ai_trigger_seq: int = 0
    active_job_id: str | None = None


class InMemoryLiveThreadStore:
    """Deterministic store used for tests and local-only development."""

    def __init__(self) -> None:
        self._rooms: dict[str, _MemoryRoom] = {}
        self._lock = threading.RLock()

    def _room(self, room_id: str) -> _MemoryRoom:
        return self._rooms.setdefault(room_id, _MemoryRoom(messages=[]))

    def append_message(
        self,
        *,
        room_id: str,
        sender: str,
        role: str,
        content: str,
    ) -> MessageRecord:
        with self._lock:
            room = self._room(room_id)
            seq = len(room.messages) + 1
            previous_hash = room.messages[-1].content_hash if room.messages else GENESIS_HASH
            created_at = utc_now()
            sender = sender.strip()
            content = content.strip()
            record = MessageRecord(
                room_id=room_id,
                seq=seq,
                message_id=f"{room_id}:{seq:020d}",
                sender=sender,
                role=role,
                content=content,
                created_at=created_at,
                previous_hash=previous_hash,
                content_hash=canonical_hash(
                    room_id=room_id,
                    seq=seq,
                    sender=sender,
                    role=role,
                    content=content,
                    created_at=created_at,
                    previous_hash=previous_hash,
                ),
            )
            room.messages.append(record)
            return record

    def list_messages(
        self,
        *,
        room_id: str,
        after_seq: int = 0,
        limit: int = MAX_HISTORY,
    ) -> list[MessageRecord]:
        with self._lock:
            return [
                message.model_copy(deep=True)
                for message in self._room(room_id).messages
                if message.seq > after_seq
            ][:limit]

    def room_snapshot(self, *, room_id: str, after_seq: int = 0) -> RoomSnapshot:
        with self._lock:
            room = self._room(room_id)
            all_messages = [m.model_copy(deep=True) for m in room.messages]
            return RoomSnapshot(
                room_id=room_id,
                messages=[m for m in all_messages if m.seq > after_seq],
                draft=room.draft.model_copy(deep=True) if room.draft else None,
                head_hash=all_messages[-1].content_hash if all_messages else GENESIS_HASH,
                chain_valid=verify_chain(room_id, all_messages),
                ai_ready=bool(os.getenv("OPENAI_API_KEY")),
            )

    def claim_ai_job(self, *, room_id: str, trigger_seq: int, job_id: str) -> bool:
        with self._lock:
            room = self._room(room_id)
            if room.last_ai_trigger_seq >= trigger_seq or room.active_job_id:
                return False
            room.active_job_id = job_id
            room.draft = DraftRecord(
                job_id=job_id,
                trigger_seq=trigger_seq,
                state="generating",
                updated_at=utc_now(),
            )
            return True

    def update_draft(
        self,
        *,
        room_id: str,
        draft: DraftRecord | None,
        last_ai_trigger_seq: int | None = None,
    ) -> None:
        with self._lock:
            room = self._room(room_id)
            room.draft = draft.model_copy(deep=True) if draft else None
            if last_ai_trigger_seq is not None:
                room.last_ai_trigger_seq = max(room.last_ai_trigger_seq, last_ai_trigger_seq)
                room.active_job_id = None

    def health(self) -> dict[str, Any]:
        return {"store": "memory", "ready": True}


class FirestoreLiveThreadStore:
    """Persistent, cross-instance store backed by Firestore Native mode."""

    def __init__(
        self,
        *,
        project: str | None = None,
        collection: str = "live_thread_rooms",
    ) -> None:
        from google.cloud import firestore

        self._firestore = firestore
        self._db = firestore.Client(project=project)
        self._collection = collection

    def _room_ref(self, room_id: str):
        return self._db.collection(self._collection).document(room_id)

    def append_message(
        self,
        *,
        room_id: str,
        sender: str,
        role: str,
        content: str,
    ) -> MessageRecord:
        sender = sender.strip()
        content = content.strip()
        room_ref = self._room_ref(room_id)
        transaction = self._db.transaction()
        firestore = self._firestore

        @firestore.transactional
        def append(tx):
            room_snapshot = room_ref.get(transaction=tx)
            room_data = room_snapshot.to_dict() if room_snapshot.exists else {}
            seq = int(room_data.get("next_seq", 0)) + 1
            previous_hash = str(room_data.get("head_hash", GENESIS_HASH))
            created_at = utc_now()
            record = MessageRecord(
                room_id=room_id,
                seq=seq,
                message_id=f"{room_id}:{seq:020d}",
                sender=sender,
                role=role,
                content=content,
                created_at=created_at,
                previous_hash=previous_hash,
                content_hash=canonical_hash(
                    room_id=room_id,
                    seq=seq,
                    sender=sender,
                    role=role,
                    content=content,
                    created_at=created_at,
                    previous_hash=previous_hash,
                ),
            )
            message_ref = room_ref.collection("messages").document(f"{seq:020d}")
            tx.set(message_ref, record.model_dump())
            tx.set(
                room_ref,
                {
                    "room_id": room_id,
                    "next_seq": seq,
                    "head_hash": record.content_hash,
                    "updated_at": created_at,
                },
                merge=True,
            )
            return record

        return append(transaction)

    def list_messages(
        self,
        *,
        room_id: str,
        after_seq: int = 0,
        limit: int = MAX_HISTORY,
    ) -> list[MessageRecord]:
        from google.cloud.firestore_v1.base_query import FieldFilter

        query = (
            self._room_ref(room_id)
            .collection("messages")
            .where(filter=FieldFilter("seq", ">", after_seq))
            .order_by("seq")
            .limit(limit)
        )
        return [MessageRecord.model_validate(doc.to_dict()) for doc in query.stream()]

    def room_snapshot(self, *, room_id: str, after_seq: int = 0) -> RoomSnapshot:
        room_ref = self._room_ref(room_id)
        room_doc = room_ref.get()
        room_data = room_doc.to_dict() if room_doc.exists else {}
        all_messages = self.list_messages(room_id=room_id, after_seq=0)
        draft_data = room_data.get("draft")
        draft = DraftRecord.model_validate(draft_data) if draft_data else None
        return RoomSnapshot(
            room_id=room_id,
            messages=[m for m in all_messages if m.seq > after_seq],
            draft=draft,
            head_hash=str(room_data.get("head_hash", GENESIS_HASH)),
            chain_valid=verify_chain(room_id, all_messages),
            ai_ready=bool(os.getenv("OPENAI_API_KEY")),
        )

    def claim_ai_job(self, *, room_id: str, trigger_seq: int, job_id: str) -> bool:
        room_ref = self._room_ref(room_id)
        transaction = self._db.transaction()
        firestore = self._firestore

        @firestore.transactional
        def claim(tx):
            snapshot = room_ref.get(transaction=tx)
            data = snapshot.to_dict() if snapshot.exists else {}
            if int(data.get("last_ai_trigger_seq", 0)) >= trigger_seq:
                return False
            current = data.get("draft")
            if current and current.get("state") == "generating":
                return False
            draft = DraftRecord(
                job_id=job_id,
                trigger_seq=trigger_seq,
                state="generating",
                updated_at=utc_now(),
            )
            tx.set(
                room_ref,
                {
                    "room_id": room_id,
                    "draft": draft.model_dump(),
                    "updated_at": draft.updated_at,
                },
                merge=True,
            )
            return True

        return bool(claim(transaction))

    def update_draft(
        self,
        *,
        room_id: str,
        draft: DraftRecord | None,
        last_ai_trigger_seq: int | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "draft": draft.model_dump() if draft else None,
            "updated_at": utc_now(),
        }
        if last_ai_trigger_seq is not None:
            payload["last_ai_trigger_seq"] = last_ai_trigger_seq
        self._room_ref(room_id).set(payload, merge=True)

    def health(self) -> dict[str, Any]:
        self._db.collection(self._collection).limit(1).get()
        return {"store": "firestore", "ready": True}


def verify_chain(room_id: str, messages: list[MessageRecord]) -> bool:
    previous_hash = GENESIS_HASH
    expected_seq = 1
    for message in messages:
        if message.room_id != room_id or message.seq != expected_seq:
            return False
        if message.previous_hash != previous_hash:
            return False
        expected = canonical_hash(
            room_id=message.room_id,
            seq=message.seq,
            sender=message.sender,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
            previous_hash=message.previous_hash,
        )
        if expected != message.content_hash:
            return False
        previous_hash = message.content_hash
        expected_seq += 1
    return True


class SharedAIResponder:
    def __init__(
        self,
        *,
        store: LiveThreadStore,
        model: str | None = None,
    ) -> None:
        self.store = store
        self.model = model or os.getenv("LIVE_THREAD_MODEL", DEFAULT_MODEL)

    def _instructions(self) -> str:
        return (
            "You are the neutral assistant in a conversation that every participant sees. "
            "Give one canonical answer for the shared room. Be accurate, direct, and respectful. "
            "Distinguish facts, inferences, and unknowns. Do not endorse threats, punishment, "
            "humiliation, coercive control, surveillance, or forced obedience. Encourage clear "
            "boundaries, mutual accountability, and safety. Do not claim to know what a participant "
            "privately thinks, intended, read, or understood unless the record establishes it."
        )

    def reply(self, *, room_id: str, trigger_seq: int) -> None:
        job_id = uuid.uuid4().hex
        if not self.store.claim_ai_job(
            room_id=room_id,
            trigger_seq=trigger_seq,
            job_id=job_id,
        ):
            return

        draft = DraftRecord(
            job_id=job_id,
            trigger_seq=trigger_seq,
            state="generating",
            updated_at=utc_now(),
        )
        self.store.update_draft(room_id=room_id, draft=draft)

        try:
            from openai import OpenAI

            client = OpenAI()
            history = self.store.list_messages(room_id=room_id, after_seq=0)
            input_items = []
            for message in history[-40:]:
                role = "assistant" if message.role == "assistant" else "user"
                text = message.content if role == "assistant" else f"[{message.sender}]: {message.content}"
                input_items.append({"role": role, "content": text})

            stream = client.responses.create(
                model=self.model,
                instructions=self._instructions(),
                input=input_items,
                stream=True,
                store=False,
            )

            content_parts: list[str] = []
            last_flush = 0.0
            last_flushed_length = 0
            current_length = 0
            for event in stream:
                if getattr(event, "type", "") != "response.output_text.delta":
                    continue
                delta = getattr(event, "delta", "")
                if not delta:
                    continue
                content_parts.append(delta)
                current_length += len(delta)
                now = time.monotonic()
                if now - last_flush >= 0.45 or current_length - last_flushed_length >= 180:
                    draft = DraftRecord(
                        job_id=job_id,
                        trigger_seq=trigger_seq,
                        content="".join(content_parts),
                        state="generating",
                        updated_at=utc_now(),
                    )
                    self.store.update_draft(room_id=room_id, draft=draft)
                    last_flush = now
                    last_flushed_length = current_length

            final_text = "".join(content_parts).strip()
            if not final_text:
                raise RuntimeError("empty_ai_response")

            self.store.append_message(
                room_id=room_id,
                sender="Shared AI",
                role="assistant",
                content=final_text,
            )
            self.store.update_draft(
                room_id=room_id,
                draft=None,
                last_ai_trigger_seq=trigger_seq,
            )
        except Exception:
            failed = DraftRecord(
                job_id=job_id,
                trigger_seq=trigger_seq,
                content=(
                    "The shared AI reply could not be generated. "
                    "The human message remains stored and integrity-verified."
                ),
                state="failed",
                updated_at=utc_now(),
                error_code="AI_GENERATION_FAILED",
            )
            self.store.update_draft(
                room_id=room_id,
                draft=failed,
                last_ai_trigger_seq=trigger_seq,
            )


def build_default_store() -> LiveThreadStore:
    mode = os.getenv("LIVE_THREAD_STORE", "firestore").strip().lower()
    if mode == "memory":
        return InMemoryLiveThreadStore()
    if mode != "firestore":
        raise RuntimeError(f"Unsupported LIVE_THREAD_STORE={mode!r}")
    return FirestoreLiveThreadStore(project=os.getenv("GCP_PROJECT"))


def create_live_thread_router(
    *,
    store: LiveThreadStore,
    responder: SharedAIResponder | None = None,
) -> APIRouter:
    router = APIRouter()
    responder = responder or SharedAIResponder(store=store)

    @router.get("/live", response_class=HTMLResponse)
    def live_root() -> str:
        return render_live_thread_root()

    @router.get("/live/r/{room_id}", response_class=HTMLResponse)
    def live_room(room_id: str, name: str = Query(default="")) -> str:
        room_id = validate_room_id(room_id)
        return render_live_thread_page(room_id=room_id, suggested_name=name[:80])

    @router.get("/live/health")
    def live_health() -> dict[str, Any]:
        try:
            store_health = store.health()
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail={"status": "UNAVAILABLE", "reason": type(exc).__name__},
            ) from exc
        return {
            "status": "HEALTHY",
            "service": "MOSIANE_LIVE_THREAD",
            "store": store_health,
            "ai_ready": bool(os.getenv("OPENAI_API_KEY")),
            "model": os.getenv("LIVE_THREAD_MODEL", DEFAULT_MODEL),
            "privacy": {
                "read_tracking": False,
                "presence_tracking": False,
                "canonical_content_hashes": True,
            },
        }

    @router.get(
        "/live/api/rooms/{room_id}/messages",
        response_model=RoomSnapshot,
    )
    def get_messages(
        room_id: str,
        after: int = Query(default=0, ge=0),
    ) -> RoomSnapshot:
        room_id = validate_room_id(room_id)
        return store.room_snapshot(room_id=room_id, after_seq=after)

    @router.post(
        "/live/api/rooms/{room_id}/messages",
        response_model=MessageRecord,
        status_code=201,
    )
    def post_message(
        room_id: str,
        request: MessageCreate,
        background_tasks: BackgroundTasks,
    ) -> MessageRecord:
        room_id = validate_room_id(room_id)
        sender = " ".join(request.sender.split())
        content = request.content.strip()
        if not sender or not content:
            raise HTTPException(status_code=422, detail="Sender and content are required.")

        record = store.append_message(
            room_id=room_id,
            sender=sender,
            role="user",
            content=content,
        )
        if request.request_ai:
            background_tasks.add_task(
                responder.reply,
                room_id=room_id,
                trigger_seq=record.seq,
            )
        return record

    return router


def include_live_thread_if_enabled(api) -> None:
    if os.getenv("LIVE_THREAD_ENABLED", "0") != "1":
        return
    store = build_default_store()
    api.include_router(create_live_thread_router(store=store))
