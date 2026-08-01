# EvidenceOps AI ICT durable runtime overlay v2.6

This non-secret production overlay strengthens the SDK supply-chain attestation and closes
resume replay, stale approval, trace export and managed state-protection gaps.

It adds:

- an exact OpenAI Agents SDK pin of `openai-agents==0.19.2`;
- a SHA-256-locked wheel receipt for the Trusted Publishing artifact;
- exact SDK trace-ID validation and immediate `flush_traces()` delivery;
- receipt-level confirmation that trace flushing completed;
- state-version approval binding and exact approval coverage before resume;
- atomic resume claims with unguessable fencing tokens and expiring leases;
- stale-version, duplicate-resume and stale-worker completion rejection;
- automatic claim release after a failed model call;
- durable re-pause when a resumed run produces another approval interruption;
- approval cleanup between state versions;
- encrypted state scrubbing after successful completion to prevent replay;
- a Google Cloud KMS `StateProtector` using ADC service identity, mission/version
  AAD, and mandatory CRC32C request/response integrity verification;
- PostgreSQL migration packaging for resume fencing and state-version approvals.

Production remains fail-closed until an authorised OpenAI credential, a bound
Cloud KMS key, private PostgreSQL, persistent Cloud Run hosting, and canonical
write/readback access are available.

Boundary owner: `WORKFORCE`  
Boundary state: `ACTIVE_REPAIR`
