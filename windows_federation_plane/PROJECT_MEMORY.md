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
# 2026-09-14 Secure MCP Tunnel extension

- Reused the canonical WindowsPlane policy, typed task envelope, SHA-256 receipt and privacy-minimized inventory instead of creating a second execution engine.
- Added a private stdio MCP profile for the official OpenAI Secure MCP Tunnel.
- Added a zero-admin current-user installer, DPAPI secret custody, bounded-backoff supervisor, health canary, stop switch and retained-release rollback.
- The physical endpoint `MosianeKK-LPT` was offline during the source build. Installation, ChatGPT discovery, persistence and rollback remain provider/runtime proof gates.
- No arbitrary shell, subprocess tool, package-install tool, unrestricted file access or inbound listener was introduced.
- Live secret-safe preflight later found the Remote Desktop service context was Windows NT 10.0.26200 but did not expose `$env:OS`. The four direct-tunnel scripts were corrected to use `[Environment]::OSVersion.Platform`, and the source court now rejects regression to environment-variable OS detection.
- The same preflight proved Python and the FUSE root present, but `tunnel-client`, Git, the tunnel ID handle and the scoped runtime-key handle absent. This is an active provider/package dependency, not a deployment claim.
