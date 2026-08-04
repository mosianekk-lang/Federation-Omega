# Security and authority boundary

The adapter has no network execution endpoint and does not expose a FastAPI route.

It may:

- read an authorised, case-walled EvidenceOps packet;
- invoke the local/provider CSE analytical runtime;
- store a derived recommendation, proof, checkpoint and hash-linked ledger event;
- verify, roll back and reapply its own derived state.

It may not:

- write or modify source evidence;
- write or modify verified facts;
- cross a case wall;
- send a message;
- file a legal document;
- publish;
- accept a contract;
- issue an invoice or payment;
- perform destructive action;
- disclose sensitive data;
- deploy to a material production target;
- expand its own authority.

Any future API must remain a separate, separately authorised release with independent security and workflow-specific proof.
