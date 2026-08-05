from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from .evolution_common import AUTHORITY_CEILING, canonical_json, clamp_metric, digest, utc_now


class AlgorithmLedgerCandidateMixin:
    def create_candidate(
        self,
        *,
        algorithm_id: str,
        candidate_version: str,
        configuration: Mapping[str, Any],
        source_lessons: Sequence[str],
        expected_benefit: str,
        candidate_id: str | None = None,
    ) -> dict[str, Any]:
        self._validate_configuration(configuration)
        active = self.active_version(algorithm_id)
        candidate_id = candidate_id or f"CAND-{digest([algorithm_id, candidate_version, configuration])[:20].upper()}"
        created_at = utc_now()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM candidates WHERE candidate_id=?", (candidate_id,)
            ).fetchone()
            if existing:
                return {
                    "candidate_id": existing["candidate_id"],
                    "algorithm_id": existing["algorithm_id"],
                    "baseline_version": existing["baseline_version"],
                    "candidate_version": existing["candidate_version"],
                    "status": existing["status"],
                    "idempotent": True,
                }
            connection.execute(
                """
                INSERT INTO candidates(
                    candidate_id,algorithm_id,baseline_version,candidate_version,
                    configuration_json,source_lessons_json,expected_benefit,
                    rollback_version,status,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    candidate_id,
                    algorithm_id,
                    active["version"],
                    candidate_version,
                    canonical_json(configuration),
                    canonical_json(sorted(set(source_lessons))),
                    expected_benefit,
                    active["version"],
                    "CANDIDATE",
                    created_at,
                ),
            )
            event = self._append_event(
                connection,
                event_type="INNOVATION_CANDIDATE",
                algorithm_id=algorithm_id,
                candidate_id=candidate_id,
                payload={
                    "baseline_version": active["version"],
                    "candidate_version": candidate_version,
                    "expected_benefit": expected_benefit,
                    "source_lessons": sorted(set(source_lessons)),
                },
            )
        return {
            "candidate_id": candidate_id,
            "algorithm_id": algorithm_id,
            "baseline_version": active["version"],
            "candidate_version": candidate_version,
            "status": "CANDIDATE",
            "event_hash": event["event_hash"],
            "idempotent": False,
        }

    def candidate(self, candidate_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM candidates WHERE candidate_id=?", (candidate_id,)
            ).fetchone()
        if not row:
            raise KeyError(candidate_id)
        return {
            "candidate_id": row["candidate_id"],
            "algorithm_id": row["algorithm_id"],
            "baseline_version": row["baseline_version"],
            "candidate_version": row["candidate_version"],
            "configuration": json.loads(row["configuration_json"]),
            "source_lessons": json.loads(row["source_lessons_json"]),
            "expected_benefit": row["expected_benefit"],
            "rollback_version": row["rollback_version"],
            "status": row["status"],
        }

    def record_evaluation(
        self,
        *,
        candidate_id: str,
        baseline_metrics: Mapping[str, float],
        candidate_metrics: Mapping[str, float],
        decision: str,
        reasons: Sequence[str],
        hard_regressions: Sequence[str],
        baseline_score: float,
        candidate_score: float,
        gain: float,
    ) -> str:
        evaluation_id = f"EVAL-{digest([candidate_id, candidate_metrics, decision])[:20].upper()}"
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT evaluation_id FROM evaluations WHERE evaluation_id=?",
                (evaluation_id,),
            ).fetchone()
            if existing:
                return evaluation_id
            connection.execute(
                """
                INSERT INTO evaluations(
                    evaluation_id,candidate_id,baseline_metrics_json,
                    candidate_metrics_json,decision,reasons_json,
                    hard_regressions_json,baseline_score,candidate_score,gain,
                    created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    evaluation_id,
                    candidate_id,
                    canonical_json(baseline_metrics),
                    canonical_json(candidate_metrics),
                    decision,
                    canonical_json(list(reasons)),
                    canonical_json(list(hard_regressions)),
                    baseline_score,
                    candidate_score,
                    gain,
                    utc_now(),
                ),
            )
            candidate = connection.execute(
                "SELECT algorithm_id FROM candidates WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
            if not candidate:
                raise KeyError(candidate_id)
            connection.execute(
                "UPDATE candidates SET status=? WHERE candidate_id=?",
                ("EVALUATED_ACCEPTED" if decision == "ACCEPT" else "EVALUATED_REJECTED", candidate_id),
            )
            self._append_event(
                connection,
                event_type="EXPERIMENT_RESULT" if decision == "ACCEPT" else "NEGATIVE_RESULT",
                algorithm_id=str(candidate["algorithm_id"]),
                candidate_id=candidate_id,
                payload={
                    "evaluation_id": evaluation_id,
                    "decision": decision,
                    "baseline_score": baseline_score,
                    "candidate_score": candidate_score,
                    "gain": gain,
                    "reasons": list(reasons),
                    "hard_regressions": list(hard_regressions),
                },
            )
        return evaluation_id

    def promote(self, candidate_id: str, metrics: Mapping[str, float]) -> dict[str, Any]:
        clean_metrics = {key: clamp_metric(value) for key, value in metrics.items()}
        candidate = self.candidate(candidate_id)
        with self._connect() as connection:
            status_row = connection.execute(
                "SELECT status FROM candidates WHERE candidate_id=?", (candidate_id,)
            ).fetchone()
            if status_row["status"] == "PROMOTED":
                return {"candidate_id": candidate_id, "promoted": True, "idempotent": True}
            if status_row["status"] != "EVALUATED_ACCEPTED":
                raise ValueError("candidate has not passed evaluation")
            connection.execute(
                """
                UPDATE algorithm_versions SET status='ROLLBACK'
                WHERE algorithm_id=? AND status='ACTIVE'
                """,
                (candidate["algorithm_id"],),
            )
            connection.execute(
                """
                INSERT INTO algorithm_versions(
                    algorithm_id,version,configuration_json,metrics_json,status,
                    previous_version,created_at
                ) VALUES(?,?,?,?,?,?,?)
                """,
                (
                    candidate["algorithm_id"],
                    candidate["candidate_version"],
                    canonical_json(candidate["configuration"]),
                    canonical_json(clean_metrics),
                    "ACTIVE",
                    candidate["baseline_version"],
                    utc_now(),
                ),
            )
            connection.execute(
                "UPDATE candidates SET status='PROMOTED' WHERE candidate_id=?",
                (candidate_id,),
            )
            event = self._append_event(
                connection,
                event_type="PROMOTION",
                algorithm_id=candidate["algorithm_id"],
                candidate_id=candidate_id,
                payload={
                    "version": candidate["candidate_version"],
                    "rollback_version": candidate["rollback_version"],
                    "metrics": clean_metrics,
                },
            )
        return {
            "candidate_id": candidate_id,
            "promoted": True,
            "idempotent": False,
            "active_version": candidate["candidate_version"],
            "rollback_version": candidate["rollback_version"],
            "event_hash": event["event_hash"],
        }

    def rollback(self, algorithm_id: str) -> dict[str, Any]:
        active = self.active_version(algorithm_id)
        rollback_version = active.get("previous_version")
        if not rollback_version:
            raise ValueError("active version has no rollback predecessor")
        with self._connect() as connection:
            predecessor = connection.execute(
                """
                SELECT * FROM algorithm_versions
                WHERE algorithm_id=? AND version=?
                """,
                (algorithm_id, rollback_version),
            ).fetchone()
            if not predecessor:
                raise KeyError(rollback_version)
            connection.execute(
                "UPDATE algorithm_versions SET status='RETIRED' WHERE algorithm_id=? AND status='ACTIVE'",
                (algorithm_id,),
            )
            connection.execute(
                "UPDATE algorithm_versions SET status='ACTIVE' WHERE algorithm_id=? AND version=?",
                (algorithm_id, rollback_version),
            )
            event = self._append_event(
                connection,
                event_type="ROLLBACK",
                algorithm_id=algorithm_id,
                candidate_id=None,
                payload={"from_version": active["version"], "to_version": rollback_version},
            )
        return {
            "algorithm_id": algorithm_id,
            "rolled_back": True,
            "from_version": active["version"],
            "to_version": rollback_version,
            "event_hash": event["event_hash"],
        }

    def verify_chain(self) -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM evolution_events ORDER BY sequence"
            ).fetchall()
        previous_hash = "GENESIS"
        errors: list[str] = []
        for sequence, row in enumerate(rows, start=1):
            body = {
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "algorithm_id": row["algorithm_id"],
                "candidate_id": row["candidate_id"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
                "previous_hash": row["previous_hash"],
                "authority_ceiling": AUTHORITY_CEILING,
                "external_effect": False,
            }
            if row["previous_hash"] != previous_hash:
                errors.append(f"event {sequence}: previous hash mismatch")
            if digest(body) != row["event_hash"]:
                errors.append(f"event {sequence}: event hash mismatch")
            previous_hash = str(row["event_hash"])
        return {
            "status": "PASSED" if not errors else "FAILED",
            "event_count": len(rows),
            "ledger_head_hash": previous_hash,
            "errors": errors,
            "authority_ceiling": AUTHORITY_CEILING,
            "external_effect": False,
        }
