BEGIN;
CREATE TABLE IF NOT EXISTS ecertify_receipt_replay (
  provider TEXT NOT NULL,
  transaction_id TEXT NOT NULL,
  seen_at BIGINT NOT NULL,
  PRIMARY KEY (provider, transaction_id)
);
CREATE TABLE IF NOT EXISTS ecertify_public_verification (
  verification_code TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  legal_label TEXT NOT NULL,
  document_sha256 CHAR(64) NOT NULL,
  issued_at BIGINT NOT NULL,
  expires_at BIGINT NULL
);
COMMIT;
