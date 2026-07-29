from fastapi import FastAPI
from fastapi.testclient import TestClient

from superior_logic.live_thread import (
    GENESIS_HASH,
    InMemoryLiveThreadStore,
    canonical_hash,
    create_live_thread_router,
    verify_chain,
)

ROOM = "room_1234567890abcdef"


class NoopResponder:
    def __init__(self):
        self.calls = []

    def reply(self, *, room_id: str, trigger_seq: int) -> None:
        self.calls.append((room_id, trigger_seq))


def test_canonical_hash_is_deterministic():
    params = dict(
        room_id=ROOM,
        seq=1,
        sender="Kim",
        role="user",
        content="Hello",
        created_at="2026-07-29T07:00:00+00:00",
        previous_hash=GENESIS_HASH,
    )
    assert canonical_hash(**params) == canonical_hash(**params)
    changed = dict(params)
    changed["content"] = "Different"
    assert canonical_hash(**params) != canonical_hash(**changed)


def test_memory_store_builds_valid_hash_chain():
    store = InMemoryLiveThreadStore()
    first = store.append_message(room_id=ROOM, sender="Kim", role="user", content="First")
    second = store.append_message(
        room_id=ROOM,
        sender="Shared AI",
        role="assistant",
        content="Second",
    )
    messages = store.list_messages(room_id=ROOM)
    assert first.seq == 1
    assert second.seq == 2
    assert second.previous_hash == first.content_hash
    assert verify_chain(ROOM, messages)
    assert store.room_snapshot(room_id=ROOM).chain_valid


def test_router_posts_and_returns_same_canonical_record(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    store = InMemoryLiveThreadStore()
    responder = NoopResponder()
    app = FastAPI()
    app.include_router(create_live_thread_router(store=store, responder=responder))
    client = TestClient(app)

    post = client.post(
        f"/live/api/rooms/{ROOM}/messages",
        json={"sender": "Kim", "content": "Shared message", "request_ai": False},
    )
    assert post.status_code == 201
    posted = post.json()

    fetched = client.get(f"/live/api/rooms/{ROOM}/messages")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["chain_valid"] is True
    assert body["messages"] == [posted]


def test_invalid_room_id_is_not_accepted():
    store = InMemoryLiveThreadStore()
    app = FastAPI()
    app.include_router(create_live_thread_router(store=store, responder=NoopResponder()))
    client = TestClient(app)
    response = client.get("/live/api/rooms/too-short/messages")
    assert response.status_code == 404


def test_live_page_states_no_read_tracking():
    store = InMemoryLiveThreadStore()
    app = FastAPI()
    app.include_router(create_live_thread_router(store=store, responder=NoopResponder()))
    client = TestClient(app)
    response = client.get(f"/live/r/{ROOM}?name=Kim")
    assert response.status_code == 200
    assert "No read or presence tracking" in response.text
    assert "same canonical message IDs and hashes" in response.text
