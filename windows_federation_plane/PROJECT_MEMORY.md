# Project Memory

## Decision

Extend the existing BEF/ChatBridge Windows lineage and Federation controls. Do not create another sovereign runtime. Deploy the zero-secret hosted Windows plane first; keep owner-PC binding distinct.

## Current truth

- Existing BEF canary provides DPAPI spool, Edge native messaging, progressive proof and scoped rollback.
- Before this component, no general Federation Windows job existed.
- The public repository requires an allowlisted, no-secret, read-only hosted canary.

## Invariants

- no arbitrary commands;
- no private evidence in public artifacts;
- no Windows-owner-PC claim from a GitHub-hosted receipt;
- source, hosted execution, owner-host binding, provider effect and value remain separate.
