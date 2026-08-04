# Federation Omega Copilot Instructions

Follow the root `AGENTS.md` governance contract for every task.

Before editing:

- Read `AGENTS.md`.
- Treat `main` as protected even when provider protection is not yet active.
- Work only on a purpose-specific branch and submit a pull request.

Never:

- commit or push directly to `main`;
- bypass checks with `[skip ci]`;
- add a workflow that commits or pushes generated files;
- grant elevated workflow permissions outside the Phoenix allowlist;
- use mutable action tags;
- commit runtime receipts, trigger files, queue state, snapshots or generated execution output;
- re-enable a Phoenix-disabled workflow;
- store or expose credentials;
- claim provider activation without exact provider readback.

Workflow changes are default-deny. Runtime outputs belong in immutable artifacts or the approved external evidence plane. Completion requires green Airlock admission, source-provenance tests, leak guard and merge-result readback on the exact pull-request head.
