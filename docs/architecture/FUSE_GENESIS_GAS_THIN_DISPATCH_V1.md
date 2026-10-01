# FUSE Genesis GAS Thin Signed Dispatch v1

F328 narrows Google Apps Script to one role: scheduling authority and signed dispatch issuer.

## Contract

A scheduler tick may only:

1. read bounded task metadata;
2. decide due/not-due;
3. reference an immutable task payload by payload_ref + payload_sha256;
4. bind current source_epoch_digest;
5. derive period-bound idempotency;
6. build the canonical Genesis DispatchEnvelope;
7. sign canonical bytes using RSA-SHA256 with a provider-side private key;
8. append one signed dispatch to the outbox with exact readback;
9. write a scheduler-only receipt;
10. exit.

The tick must not execute business/task logic, send mail, perform provider business calls, embed full prompts, claim semantic completion, or hold an execution lease beyond dispatch admission.

The private signing key remains in Apps Script Script Properties and never enters Sheets, GitHub, logs, receipts or Genesis.

F328 is source-only. It does not install a trigger or mutate the live Apps Script project. Live owner-context deployment, singleton trigger proof, natural unattended cycles, GAS->Genesis admission, task execution, missed-run recovery and rollback remain separate runtime predicates.
