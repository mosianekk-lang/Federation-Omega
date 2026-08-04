BEGIN TRANSACTION;
CREATE TABLE checkpoints(
    checkpoint_id TEXT PRIMARY KEY,
    ledger_head_hash TEXT NOT NULL,
    database_semantic_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE ledger(
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    record_id TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE proofs(
    proof_id TEXT PRIMARY KEY,
    recommendation_id TEXT NOT NULL UNIQUE,
    proof_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(recommendation_id) REFERENCES recommendations(recommendation_id)
);
CREATE TABLE recommendations(
    recommendation_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    matter_id TEXT NOT NULL,
    case_wall_id TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    output_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
DELETE FROM "sqlite_sequence";
COMMIT;
