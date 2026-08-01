BEGIN;
ALTER TABLE durable_agent_runs
  ADD COLUMN IF NOT EXISTS resume_token TEXT,
  ADD COLUMN IF NOT EXISTS resume_lease_until TIMESTAMPTZ;

ALTER TABLE durable_agent_runs DROP CONSTRAINT IF EXISTS durable_agent_runs_status_check;
ALTER TABLE durable_agent_runs
  ADD CONSTRAINT durable_agent_runs_status_check
  CHECK (status IN ('WAITING_APPROVAL','RESUMING','COMPLETE','FAILED'));

ALTER TABLE durable_agent_approvals
  ADD COLUMN IF NOT EXISTS state_version BIGINT NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS durable_agent_runs_resume_lease_idx
  ON durable_agent_runs(status, resume_lease_until)
  WHERE status = 'RESUMING';

CREATE INDEX IF NOT EXISTS durable_agent_approvals_version_idx
  ON durable_agent_approvals(mission_id, state_version);
COMMIT;
