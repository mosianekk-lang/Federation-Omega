# Apps Script Fleet Hardening — Source-Control Gate

This control is a reusable static-analysis and restructuring gate for privileged Google Apps Script fleets.

## Why the fleet is held

The reviewed backup combines a broadly reachable web application, deployer-level execution, cloud/project/deployment scopes, a source-literal approval value, default approval injection, raw approval persistence, duplicate global web and code-mutation handlers, a legacy transport project default, and transport/self-readback promoted as completion.

That combination must remain `SECURITY_HOLD` for provider mutation. Read-only/status transport may be preserved while the source is restructured.

## Required restructuring

1. Split the fleet into two projects:
   - **Private privileged admin plane** — broad scopes, no public web entry, exact target/consumer/principal binding, signed mutation engine.
   - **Minimal public gateway** — one `doGet`/`doPost`, minimum scopes, HMAC timestamp/nonce/body binding, no raw provider credentials and no direct privileged API calls.
2. Namespace all internal code. Exactly one global web router may exist per project.
3. Remove static/default approvals. Missing authentication is rejection, never a fallback approval.
4. Never write raw authentication material to Sheets, logs or receipts.
5. Treat legacy and OAuth-consumer projects as separate lineages. They cannot mutate the canonical target by inference.
6. Keep one backup-first, signed code-mutation engine. Remove or quarantine weaker duplicate mutators.
7. Separate queue transport proof from downstream provider-semantic proof.
8. Promote only after hostile ingress, replay, identity-lineage, source-hash, rollback and action-specific semantic canaries pass.

## What this source change proves

It proves deterministic detection of the identified defect classes and produces a compact, reusable restructuring plan. It does not change the live Apps Script project or establish Google provider authority.
