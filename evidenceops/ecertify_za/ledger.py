from __future__ import annotations
import hashlib, json, sqlite3, time, uuid
from pathlib import Path
from typing import Any

class HashChainLedger:
    """Append-only hash-linked event ledger for decision and certification receipts."""
    def __init__(self, path: str | Path = ":memory:"):
        self.db = sqlite3.connect(str(path))
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE,ts INTEGER,event_type TEXT,payload TEXT,prev_hash TEXT,event_hash TEXT UNIQUE)")
        self.db.commit()

    def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        prev = self.db.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        prev_hash = prev[0] if prev else "GENESIS"
        event_id = str(uuid.uuid4()); ts = int(time.time())
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        material = f"{event_id}|{ts}|{event_type}|{canonical}|{prev_hash}".encode()
        event_hash = hashlib.sha256(material).hexdigest()
        self.db.execute("INSERT INTO events(event_id,ts,event_type,payload,prev_hash,event_hash) VALUES(?,?,?,?,?,?)",(event_id,ts,event_type,canonical,prev_hash,event_hash))
        self.db.commit()
        return {"event_id":event_id,"ts":ts,"event_type":event_type,"prev_hash":prev_hash,"event_hash":event_hash}

    def verify(self) -> bool:
        expected_prev="GENESIS"
        for event_id,ts,event_type,payload,prev_hash,event_hash in self.db.execute("SELECT event_id,ts,event_type,payload,prev_hash,event_hash FROM events ORDER BY seq"):
            if prev_hash != expected_prev: return False
            if hashlib.sha256(f"{event_id}|{ts}|{event_type}|{payload}|{prev_hash}".encode()).hexdigest()!=event_hash: return False
            expected_prev=event_hash
        return True

    def close(self): self.db.close()
