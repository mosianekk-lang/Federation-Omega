from __future__ import annotations

import json
import sqlite3
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pytest

from live_bible_fabric.fabric import CaptureError, CaptureEvent, EventStore, LiveBibleEngine, _Handler, ensure_token
from http.server import ThreadingHTTPServer

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc).isoformat()


def event(**overrides):
    base = {
        "source_id": "test-source",
        "source_type": "TURN_CONNECTOR",
        "conversation_id": "conversation-1",
        "message_id": "message-1",
        "sequence": 1,
        "role": "user",
        "content": "hello world",
        "occurred_at": NOW,
        "privacy_tier": "P2_CONFIDENTIAL",
        "authority_class": "A1",
        "case_wall": "GENERAL",
        "metadata": {},
    }
    base.update(overrides)
    return CaptureEvent(**base)


def setup(tmp_path: Path):
    store = EventStore(tmp_path / "db.sqlite3")
    engine = LiveBibleEngine(store, tmp_path / "out")
    return store, engine


def test_event_id_is_deterministic():
    assert event().deterministic_id == event().deterministic_id


def test_unknown_field_fails_closed():
    value = event().to_dict()
    value["unexpected"] = True
    with pytest.raises(CaptureError):
        CaptureEvent.from_dict(value)


def test_duplicate_is_idempotent(tmp_path):
    store, engine = setup(tmp_path)
    first = engine.ingest(event())
    second = engine.ingest(event())
    assert first["event_id"] == second["event_id"]
    assert second["idempotent_replay"] is True
    assert len(store.events("conversation-1")) == 1


def test_chain_verifies(tmp_path):
    store, engine = setup(tmp_path)
    engine.ingest(event())
    engine.ingest(event(message_id="message-2", sequence=2, role="assistant", content="reply"))
    report = store.verify_chain("conversation-1")
    assert report["valid"] is True
    assert report["event_count"] == 2
    assert report["database_quick_check"] == "ok"


def test_gap_detection_and_resolution(tmp_path):
    store, engine = setup(tmp_path)
    engine.ingest(event(sequence=1))
    engine.ingest(event(message_id="message-3", sequence=3, content="third"))
    assert [x["missing_sequence"] for x in store.unresolved_gaps("conversation-1")] == [2]
    engine.ingest(event(message_id="message-2", sequence=2, content="second"))
    assert store.unresolved_gaps("conversation-1") == []


def test_out_of_order_is_recorded_and_chain_remains_valid(tmp_path):
    store, engine = setup(tmp_path)
    engine.ingest(event(sequence=2))
    receipt = engine.ingest(event(message_id="message-old", sequence=1, content="old"))
    assert receipt["out_of_order"] is True
    assert store.verify_chain("conversation-1")["valid"] is True


def test_secret_is_redacted_not_persisted(tmp_path):
    store, engine = setup(tmp_path)
    secret = "sk-proj-THISISASECRETTHATSHOULDNOTPERSIST123456"
    receipt = engine.ingest(event(content=f"token={secret}"))
    row = store.events("conversation-1")[0]
    assert secret not in row["content"]
    assert row["quarantined"] is True
    assert receipt["quarantined"] is True


def test_tampering_is_detected(tmp_path):
    store, engine = setup(tmp_path)
    engine.ingest(event())
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE events SET content='tampered' WHERE conversation_id='conversation-1'")
    assert store.verify_chain("conversation-1")["valid"] is False


def test_projection_created(tmp_path):
    store, engine = setup(tmp_path)
    engine.ingest(event())
    paths = engine.project("conversation-1")
    assert Path(paths["markdown"]).is_file()
    assert "hello world" in Path(paths["markdown"]).read_text(encoding="utf-8")
    state = json.loads(Path(paths["state"]).read_text(encoding="utf-8"))
    assert state["chain_valid"] is True


def test_chat_export_import(tmp_path):
    store, engine = setup(tmp_path)
    export = tmp_path / "chat.json"
    export.write_text(
        json.dumps(
            {
                "conversation_id": "exported-chat",
                "messages": [
                    {"id": "a", "role": "user", "content": "question", "created_at": NOW},
                    {"id": "b", "role": "assistant", "content": "answer", "created_at": NOW},
                ],
            }
        ),
        encoding="utf-8",
    )
    receipts = engine.import_export(export)
    assert len(receipts) == 2
    assert store.verify_chain("exported-chat")["valid"] is True


def test_outbox_moves_good_and_bad_files(tmp_path):
    store, engine = setup(tmp_path)
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "good.json").write_text(json.dumps(event().to_dict()), encoding="utf-8")
    (outbox / "bad.json").write_text("{bad", encoding="utf-8")
    result = engine.process_outbox(outbox)
    assert result == {"accepted_events": 1, "rejected_files": 1}
    assert len(list((outbox / "processed").iterdir())) == 1
    assert len(list((outbox / "dead_letter").iterdir())) == 1


def test_equivalent_browser_replay_with_new_observed_time_is_idempotent(tmp_path):
    store, engine = setup(tmp_path)
    first = event(source_type="BROWSER_CAPTURE", occurred_at="2026-08-04T12:00:00+00:00")
    second = event(source_type="BROWSER_CAPTURE", occurred_at="2026-08-04T12:01:00+00:00")
    first_receipt = engine.ingest(first)
    second_receipt = engine.ingest(second)
    assert second_receipt["event_id"] == first_receipt["event_id"]
    assert second_receipt["idempotent_replay"] is True
    assert second_receipt["equivalent_source_event"] is True
    assert len(store.events("conversation-1")) == 1


def test_invalid_authority_rejected():
    with pytest.raises(CaptureError):
        event(authority_class="A9").normalized()


def test_remote_bind_is_not_exposed_by_default(tmp_path):
    token = ensure_token(tmp_path)
    assert len(token) >= 32
    assert (tmp_path / "pairing.token").exists()


def test_http_receiver_authentication(tmp_path):
    store, engine = setup(tmp_path)
    token = "x" * 40
    handler = type("TestHandler", (_Handler,), {"engine": engine, "token": token})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/v1/events"
    body = json.dumps(event().to_dict()).encode()
    bad = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(bad, timeout=3)
    assert exc.value.code == 401
    good = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "X-Live-Bible-Token": token},
    )
    with urllib.request.urlopen(good, timeout=3) as response:
        payload = json.loads(response.read())
    assert payload["count"] == 1
    server.shutdown()
    server.server_close()


def test_database_file_permissions_best_effort(tmp_path):
    store, _ = setup(tmp_path)
    assert store.path.exists()


def test_missing_timezone_rejected():
    with pytest.raises(CaptureError):
        event(occurred_at="2026-08-04T12:00:00").normalized()


def test_content_size_limit():
    with pytest.raises(CaptureError):
        event(content="x" * 2_000_001).normalized()
