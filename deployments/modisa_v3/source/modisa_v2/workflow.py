from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from .audit import AuditLog
from .db import Repository
from .ids import new_id
from .schemas import WorkflowCreateRequest, WorkflowRecord, WorkflowStatus


class DurableWorkflowStore:
    """Database-backed leases and retries for crash-safe local orchestration.

    This is the verified local durable runtime. A Temporal/Restate/Dapr adapter may replace
    the scheduler while preserving these mission and proof contracts.
    """

    def __init__(self, repo: Repository, audit: AuditLog):
        self.repo = repo
        self.audit = audit

    @staticmethod
    def _from_row(repo: Repository, row: Any) -> WorkflowRecord:
        return WorkflowRecord(
            workflow_id=row["workflow_id"],
            matter_id=row["matter_id"],
            mission_id=row["mission_id"],
            workflow_type=row["workflow_type"],
            status=WorkflowStatus(row["status"]),
            input_payload=repo.loads(row["input_json"], {}),
            state_payload=repo.loads(row["state_json"], {}),
            attempts=int(row["attempts"]),
            max_attempts=int(row["max_attempts"]),
            lease_owner=row["lease_owner"],
            lease_expires_at=datetime.fromisoformat(row["lease_expires_at"]) if row["lease_expires_at"] else None,
            lease_generation=int(row["lease_generation"]),
            state_version=int(row["state_version"]),
            next_run_at=datetime.fromisoformat(row["next_run_at"]),
            last_error=row["last_error"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def create(self, request: WorkflowCreateRequest, actor_id: str) -> WorkflowRecord:
        self.repo.ensure_matter(request.matter_id)
        workflow_id = new_id("WF")
        now = datetime.now(UTC)
        self.repo.execute(
            """INSERT INTO workflows(
               workflow_id,matter_id,mission_id,workflow_type,status,input_json,state_json,
               attempts,max_attempts,next_run_at,created_at,updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                workflow_id,
                request.matter_id,
                request.mission_id,
                request.workflow_type,
                WorkflowStatus.PENDING.value,
                self.repo.dumps(request.input_payload),
                self.repo.dumps({}),
                0,
                request.max_attempts,
                now.isoformat(),
                now.isoformat(),
                now.isoformat(),
            ),
        )
        self._event(workflow_id, "WORKFLOW_CREATED", request.input_payload)
        self.audit.append(
            actor_id=actor_id,
            event_type="WORKFLOW_CREATED",
            matter_id=request.matter_id,
            object_id=workflow_id,
            payload={"mission_id": request.mission_id, "workflow_type": request.workflow_type},
        )
        record = self.get(workflow_id)
        assert record is not None
        return record

    def _event(self, workflow_id: str, event_type: str, payload: dict[str, Any]) -> str:
        event_id = new_id("WFE")
        self.repo.execute(
            "INSERT INTO workflow_events(event_id,workflow_id,event_type,payload_json,created_at) VALUES(?,?,?,?,?)",
            (event_id, workflow_id, event_type, self.repo.dumps(payload), self.repo.now()),
        )
        return event_id

    def get(self, workflow_id: str) -> WorkflowRecord | None:
        row = self.repo.fetch_one("SELECT * FROM workflows WHERE workflow_id=?", (workflow_id,))
        return self._from_row(self.repo, row) if row else None

    def lease(self, workflow_id: str, worker_id: str, lease_seconds: int = 120) -> WorkflowRecord:
        now = datetime.now(UTC)
        lease_until = now + timedelta(seconds=lease_seconds)
        with self.repo.connect(immediate=True) as conn:
            row = conn.execute("SELECT * FROM workflows WHERE workflow_id=?", (workflow_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown workflow")
            if row["status"] not in {WorkflowStatus.PENDING.value, WorkflowStatus.RUNNING.value}:
                raise ValueError("Workflow is not leaseable")
            if row["lease_expires_at"] and datetime.fromisoformat(row["lease_expires_at"]) > now and row["lease_owner"] != worker_id:
                raise ValueError("Workflow is already leased")
            same_active_owner = (
                row["lease_owner"] == worker_id
                and row["lease_expires_at"]
                and datetime.fromisoformat(row["lease_expires_at"]) > now
            )
            attempts = int(row["attempts"]) if same_active_owner else int(row["attempts"]) + 1
            if attempts > int(row["max_attempts"]):
                raise ValueError("Workflow attempts exhausted")
            generation = int(row["lease_generation"]) + 1
            conn.execute(
                """UPDATE workflows SET status=?,attempts=?,lease_owner=?,lease_expires_at=?,
                   lease_generation=?,updated_at=?
                   WHERE workflow_id=?""",
                (WorkflowStatus.RUNNING.value, attempts, worker_id, lease_until.isoformat(), generation, now.isoformat(), workflow_id),
            )
        self._event(workflow_id, "LEASE_ACQUIRED", {"worker_id": worker_id, "lease_generation": generation, "lease_until": lease_until.isoformat()})
        record = self.get(workflow_id)
        assert record is not None
        return record

    def lease_next(self, worker_id: str, lease_seconds: int = 120) -> WorkflowRecord | None:
        now = datetime.now(UTC)
        lease_until = now + timedelta(seconds=lease_seconds)
        with self.repo.connect(immediate=True) as conn:
            row = conn.execute(
                """
                SELECT * FROM workflows
                WHERE status IN (?,?)
                  AND next_run_at<=?
                  AND (lease_expires_at IS NULL OR lease_expires_at<=?)
                  AND attempts<max_attempts
                ORDER BY next_run_at, created_at
                LIMIT 1
                """,
                (WorkflowStatus.PENDING.value, WorkflowStatus.RUNNING.value, now.isoformat(), now.isoformat()),
            ).fetchone()
            if row is None:
                return None
            attempts = int(row["attempts"]) + 1
            generation = int(row["lease_generation"]) + 1
            conn.execute(
                """UPDATE workflows SET status=?,attempts=?,lease_owner=?,lease_expires_at=?,
                   lease_generation=?,updated_at=?
                   WHERE workflow_id=?""",
                (
                    WorkflowStatus.RUNNING.value,
                    attempts,
                    worker_id,
                    lease_until.isoformat(),
                    generation,
                    now.isoformat(),
                    row["workflow_id"],
                ),
            )
        self._event(row["workflow_id"], "LEASE_ACQUIRED", {"worker_id": worker_id, "lease_generation": generation, "lease_until": lease_until.isoformat()})
        return self.get(row["workflow_id"])

    def _lease_update(
        self,
        workflow_id: str,
        worker_id: str,
        lease_generation: int,
        assignments: str,
        values: tuple[Any, ...],
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self.repo.connect(immediate=True) as conn:
            cursor = conn.execute(
                f"""UPDATE workflows SET {assignments},state_version=state_version+1,updated_at=?
                    WHERE workflow_id=? AND status=? AND lease_owner=?
                      AND lease_generation=? AND lease_expires_at>?""",
                (*values, now, workflow_id, WorkflowStatus.RUNNING.value, worker_id, lease_generation, now),
            )
            if cursor.rowcount != 1:
                raise ValueError("Stale, expired, or unowned workflow lease")

    def heartbeat(self, workflow_id: str, worker_id: str, lease_generation: int, lease_seconds: int = 120) -> WorkflowRecord:
        lease_until = datetime.now(UTC) + timedelta(seconds=lease_seconds)
        self._lease_update(
            workflow_id, worker_id, lease_generation, "lease_expires_at=?", (lease_until.isoformat(),)
        )
        self._event(workflow_id, "HEARTBEAT", {"worker_id": worker_id, "lease_generation": lease_generation, "lease_until": lease_until.isoformat()})
        updated = self.get(workflow_id)
        assert updated is not None
        return updated

    def update_state(self, workflow_id: str, worker_id: str, lease_generation: int, state: dict[str, Any]) -> WorkflowRecord:
        self._lease_update(
            workflow_id, worker_id, lease_generation, "state_json=?", (self.repo.dumps(state),)
        )
        self._event(workflow_id, "STATE_UPDATED", {"state_keys": sorted(state)})
        updated = self.get(workflow_id)
        assert updated is not None
        return updated

    def wait_for_approval(self, workflow_id: str, worker_id: str, lease_generation: int, state: dict[str, Any]) -> WorkflowRecord:
        self._lease_update(
            workflow_id,
            worker_id,
            lease_generation,
            "status=?,state_json=?,lease_owner=NULL,lease_expires_at=NULL",
            (WorkflowStatus.WAITING_APPROVAL.value, self.repo.dumps(state)),
        )
        self._event(workflow_id, "WAITING_APPROVAL", state)
        updated = self.get(workflow_id)
        assert updated is not None
        return updated

    def resume_after_approval(self, workflow_id: str, actor_id: str) -> WorkflowRecord:
        record = self.get(workflow_id)
        if record is None:
            raise ValueError("Unknown workflow")
        if record.status != WorkflowStatus.WAITING_APPROVAL:
            raise ValueError("Workflow is not waiting for approval")
        now = self.repo.now()
        self.repo.execute(
            """UPDATE workflows SET status=?,next_run_at=?,state_version=state_version+1,updated_at=? WHERE workflow_id=?""",
            (WorkflowStatus.PENDING.value, now, now, workflow_id),
        )
        self._event(workflow_id, "APPROVAL_RESUME", {"actor_id": actor_id})
        updated = self.get(workflow_id)
        assert updated is not None
        return updated

    def complete(self, workflow_id: str, worker_id: str, lease_generation: int, state: dict[str, Any]) -> WorkflowRecord:
        self._lease_update(
            workflow_id,
            worker_id,
            lease_generation,
            "status=?,state_json=?,lease_owner=NULL,lease_expires_at=NULL",
            (WorkflowStatus.COMPLETED.value, self.repo.dumps(state)),
        )
        self._event(workflow_id, "WORKFLOW_COMPLETED", state)
        updated = self.get(workflow_id)
        assert updated is not None
        return updated

    def block(self, workflow_id: str, worker_id: str, lease_generation: int, reason: str) -> WorkflowRecord:
        """Terminally block a workflow on a non-retryable authority or configuration gate."""
        self._lease_update(
            workflow_id,
            worker_id,
            lease_generation,
            "status=?,lease_owner=NULL,lease_expires_at=NULL,last_error=?",
            (WorkflowStatus.BLOCKED.value, reason[:4000]),
        )
        self._event(workflow_id, "WORKFLOW_BLOCKED", {"reason": reason})
        updated = self.get(workflow_id)
        assert updated is not None
        return updated

    def fail(self, workflow_id: str, worker_id: str, lease_generation: int, error: str, retry_delay_seconds: int = 60) -> WorkflowRecord:
        record = self.get(workflow_id)
        if record is None or record.lease_owner != worker_id or record.lease_generation != lease_generation:
            raise ValueError("Worker does not hold the workflow lease")
        terminal = record.attempts >= record.max_attempts
        status = WorkflowStatus.FAILED if terminal else WorkflowStatus.PENDING
        next_run = datetime.now(UTC) + timedelta(seconds=retry_delay_seconds)
        self._lease_update(
            workflow_id,
            worker_id,
            lease_generation,
            "status=?,lease_owner=NULL,lease_expires_at=NULL,next_run_at=?,last_error=?",
            (status.value, next_run.isoformat(), error[:4000]),
        )
        self._event(workflow_id, "WORKFLOW_FAILED" if terminal else "WORKFLOW_RETRY_SCHEDULED", {"error": error, "next_run_at": next_run.isoformat()})
        updated = self.get(workflow_id)
        assert updated is not None
        return updated

    def save_agent_run_state(
        self,
        *,
        mission_id: str,
        matter_id: str,
        session_id: str,
        run_state_json: str,
        approval_items: list[dict[str, Any]],
    ) -> None:
        now = self.repo.now()
        self.repo.execute(
            """INSERT INTO pending_agent_runs(
               mission_id,matter_id,session_id,run_state_json,approval_items_json,created_at,updated_at
               ) VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(mission_id) DO UPDATE SET
                 run_state_json=excluded.run_state_json,
                 approval_items_json=excluded.approval_items_json,
                 updated_at=excluded.updated_at""",
            (mission_id, matter_id, session_id, run_state_json, self.repo.dumps(approval_items), now, now),
        )

    def load_agent_run_state(self, mission_id: str) -> dict[str, Any] | None:
        row = self.repo.fetch_one("SELECT * FROM pending_agent_runs WHERE mission_id=?", (mission_id,))
        if row is None:
            return None
        return {
            "mission_id": row["mission_id"],
            "matter_id": row["matter_id"],
            "session_id": row["session_id"],
            "run_state_json": row["run_state_json"],
            "approval_items": self.repo.loads(row["approval_items_json"], []),
        }

    def delete_agent_run_state(self, mission_id: str) -> None:
        self.repo.execute("DELETE FROM pending_agent_runs WHERE mission_id=?", (mission_id,))
