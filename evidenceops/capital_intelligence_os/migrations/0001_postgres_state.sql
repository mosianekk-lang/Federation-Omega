CREATE TABLE IF NOT EXISTS cios_events (
  tenant_id TEXT NOT NULL,
  event_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  source TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  payload_json JSONB NOT NULL,
  domain TEXT NOT NULL,
  information_class TEXT NOT NULL,
  materiality DOUBLE PRECISION NOT NULL,
  occurred_at TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (tenant_id, event_id)
);

CREATE TABLE IF NOT EXISTS cios_claims (
  tenant_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  predicate TEXT NOT NULL,
  value_json JSONB NOT NULL,
  status TEXT NOT NULL,
  evidence_json JSONB NOT NULL,
  information_class TEXT NOT NULL,
  domain TEXT NOT NULL,
  confidence DOUBLE PRECISION NOT NULL,
  assumptions_json JSONB NOT NULL,
  supersedes TEXT,
  created_at TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  PRIMARY KEY (tenant_id, claim_id)
);
CREATE INDEX IF NOT EXISTS idx_cios_claims_tenant_subject
  ON cios_claims(tenant_id, subject_id, predicate);

CREATE TABLE IF NOT EXISTS cios_dependencies (
  tenant_id TEXT NOT NULL,
  source_subject TEXT NOT NULL,
  dependent_subject TEXT NOT NULL,
  PRIMARY KEY (tenant_id, source_subject, dependent_subject)
);

CREATE TABLE IF NOT EXISTS cios_idempotency (
  tenant_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  result_json JSONB NOT NULL,
  result_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (tenant_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS cios_learning_events (
  tenant_id TEXT NOT NULL,
  sequence_no BIGINT NOT NULL,
  event_type TEXT NOT NULL,
  category TEXT NOT NULL,
  payload_json JSONB NOT NULL,
  previous_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (tenant_id, sequence_no),
  UNIQUE (tenant_id, event_hash)
);

CREATE TABLE IF NOT EXISTS cios_restrictions (
  tenant_id TEXT NOT NULL,
  restriction_id TEXT NOT NULL,
  issuer_id TEXT,
  security_id TEXT,
  reason TEXT NOT NULL,
  information_class TEXT NOT NULL,
  start_at TEXT NOT NULL,
  review_at TEXT,
  cleared_at TEXT,
  PRIMARY KEY (tenant_id, restriction_id)
);
CREATE INDEX IF NOT EXISTS idx_cios_restrictions_lookup
  ON cios_restrictions(tenant_id, issuer_id, security_id, cleared_at);

CREATE TABLE IF NOT EXISTS cios_outcome_consents (
  tenant_id TEXT PRIMARY KEY,
  share_aggregated BOOLEAN NOT NULL,
  minimum_cohort INTEGER NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cios_outcomes (
  observation_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  cohort TEXT NOT NULL,
  metric TEXT NOT NULL,
  predicted DOUBLE PRECISION NOT NULL,
  actual DOUBLE PRECISION NOT NULL,
  observed_at TEXT NOT NULL,
  metadata_json JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cios_outcomes_cohort_metric
  ON cios_outcomes(cohort, metric);
