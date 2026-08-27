CREATE TABLE IF NOT EXISTS cios_audit_records (
  sequence_no BIGINT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  action TEXT NOT NULL,
  resource TEXT NOT NULL,
  outcome TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  previous_hash TEXT NOT NULL,
  record_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);

CREATE OR REPLACE FUNCTION cios_reject_audit_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'CIOS_AUDIT_APPEND_ONLY';
END;
$$;

DROP TRIGGER IF EXISTS cios_audit_no_update ON cios_audit_records;
CREATE TRIGGER cios_audit_no_update
BEFORE UPDATE ON cios_audit_records
FOR EACH ROW EXECUTE FUNCTION cios_reject_audit_mutation();

DROP TRIGGER IF EXISTS cios_audit_no_delete ON cios_audit_records;
CREATE TRIGGER cios_audit_no_delete
BEFORE DELETE ON cios_audit_records
FOR EACH ROW EXECUTE FUNCTION cios_reject_audit_mutation();
