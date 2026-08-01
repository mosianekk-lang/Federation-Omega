BEGIN;
CREATE TABLE IF NOT EXISTS durable_agent_runs (
  mission_id TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK (status IN ('WAITING_APPROVAL','RUNNING','COMPLETE','FAILED')),
  state_version BIGINT NOT NULL,
  state_ciphertext BYTEA NOT NULL,
  state_sha256 CHAR(64) NOT NULL,
  protector_key_id TEXT NOT NULL,
  interruptions_json JSONB NOT NULL,
  session_id TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS durable_agent_approvals (
  mission_id TEXT NOT NULL REFERENCES durable_agent_runs(mission_id) ON DELETE CASCADE,
  call_id TEXT NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN ('APPROVE','REJECT')),
  approver TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (mission_id, call_id)
);
CREATE INDEX IF NOT EXISTS durable_agent_runs_status_updated_idx
  ON durable_agent_runs(status, updated_at);
COMMIT;
