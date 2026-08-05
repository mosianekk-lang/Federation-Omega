from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Mapping

from .evolution_common import (
    AUTHORITY_CEILING, FORBIDDEN_CONFIG_KEYS, _walk_keys,
    canonical_json, clamp_metric, digest, utc_now,
)

class AlgorithmLedgerStorageMixin:
    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS algorithm_versions(
                    algorithm_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    configuration_json TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    previous_version TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(algorithm_id, version)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_version_per_algorithm
                ON algorithm_versions(algorithm_id) WHERE status='ACTIVE';
                CREATE TABLE IF NOT EXISTS candidates(
                    candidate_id TEXT PRIMARY KEY,
                    algorithm_id TEXT NOT NULL,
                    baseline_version TEXT NOT NULL,
                    candidate_version TEXT NOT NULL,
                    configuration_json TEXT NOT NULL,
                    source_lessons_json TEXT NOT NULL,
                    expected_benefit TEXT NOT NULL,
                    rollback_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(algorithm_id, candidate_version)
                );
                CREATE TABLE IF NOT EXISTS evaluations(
                    evaluation_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    baseline_metrics_json TEXT NOT NULL,
                    candidate_metrics_json TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reasons_json TEXT NOT NULL,
                    hard_regressions_json TEXT NOT NULL,
                    baseline_score REAL NOT NULL,
                    candidate_score REAL NOT NULL,
                    gain REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
                );
                CREATE TABLE IF NOT EXISTS evolution_events(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    event_type TEXT NOT NULL,
                    algorithm_id TEXT NOT NULL,
                    candidate_id TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT UNIQUE NOT NULL
                );
            """)

    def _append_event(self, connection: sqlite3.Connection, *, event_type: str, algorithm_id: str, candidate_id: str | None, payload: Mapping[str, Any]) -> dict[str, Any]:
        row = connection.execute("SELECT event_hash FROM evolution_events ORDER BY sequence DESC LIMIT 1").fetchone()
        previous_hash = str(row["event_hash"]) if row else "GENESIS"
        created_at = utc_now()
        event_id = f"EVOL-{uuid.uuid4().hex.upper()}"
        body = {
            "event_id": event_id, "event_type": event_type,
            "algorithm_id": algorithm_id, "candidate_id": candidate_id,
            "payload": dict(payload), "created_at": created_at,
            "previous_hash": previous_hash,
            "authority_ceiling": AUTHORITY_CEILING, "external_effect": False,
        }
        event_hash = digest(body)
        connection.execute("""INSERT INTO evolution_events(event_id,event_type,algorithm_id,candidate_id,payload_json,created_at,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?,?)""", (event_id,event_type,algorithm_id,candidate_id,canonical_json(body["payload"]),created_at,previous_hash,event_hash))
        return {**body, "event_hash": event_hash}

    def initialize_algorithm(self, *, algorithm_id: str, version: str, configuration: Mapping[str, Any], metrics: Mapping[str, float]) -> None:
        self._validate_configuration(configuration)
        clean_metrics = {key: clamp_metric(value) for key, value in metrics.items()}
        with self._connect() as connection:
            active = connection.execute("SELECT version FROM algorithm_versions WHERE algorithm_id=? AND status='ACTIVE'", (algorithm_id,)).fetchone()
            if active:
                if active["version"] == version:
                    return
                raise ValueError(f"algorithm already has active version {active['version']}")
            connection.execute("""INSERT INTO algorithm_versions(algorithm_id,version,configuration_json,metrics_json,status,previous_version,created_at) VALUES(?,?,?,?,?,?,?)""", (algorithm_id,version,canonical_json(configuration),canonical_json(clean_metrics),"ACTIVE",None,utc_now()))
            self._append_event(connection, event_type="BASELINE_REGISTERED", algorithm_id=algorithm_id, candidate_id=None, payload={"version": version, "metrics": clean_metrics})

    @staticmethod
    def _validate_configuration(configuration: Mapping[str, Any]) -> None:
        forbidden = sorted(_walk_keys(configuration) & FORBIDDEN_CONFIG_KEYS)
        if forbidden:
            raise ValueError("algorithm configuration contains prohibited authority/secret fields: " + ", ".join(forbidden))
        if configuration.get("authority_ceiling", AUTHORITY_CEILING) != AUTHORITY_CEILING:
            raise ValueError("algorithm configuration cannot exceed A1_INTERNAL")
        if configuration.get("external_effect", False) is not False:
            raise ValueError("algorithm configuration cannot create an external effect")

    def active_version(self, algorithm_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM algorithm_versions WHERE algorithm_id=? AND status='ACTIVE'", (algorithm_id,)).fetchone()
        if not row:
            raise KeyError(f"no active version for {algorithm_id}")
        return {
            "algorithm_id": row["algorithm_id"], "version": row["version"],
            "configuration": json.loads(row["configuration_json"]),
            "metrics": json.loads(row["metrics_json"]),
            "previous_version": row["previous_version"],
            "status": row["status"], "created_at": row["created_at"],
        }
