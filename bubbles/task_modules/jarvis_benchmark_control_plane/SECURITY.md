# Security model

- The base registry is operator-controlled. The collector never accepts an arbitrary URL from an API request.
- Collection requires HTTPS, rejects redirects for explicit review, caps response size and time, and stores a digest rather than the fetched body.
- The API binds to loopback by default. Remote binding requires an explicit switch and a sufficiently long admin token.
- All network writes are disabled without the admin token. Token comparison is constant-time.
- Request bodies, ledger size and ledger line size are bounded.
- Every ledger append verifies the full existing chain, acquires an exclusive lock, flushes the write and re-verifies the result.
- Unknown private internal capabilities are excluded from scoring.
- Opportunity recommendations are non-effectful. A separate Formation-authorized executor is required to implement one.
- No active GitHub workflow is included, so this package does not expand the Federation Airlock workflow allowlist.
- The Federation command-bus adapter accepts only the committed public fixture, strips the runtime environment to a minimal allowlist, uses an ephemeral ledger, caps output and time, and exposes no commit, refresh, daemon, server or provider-write action.

Unresolved deployment controls: managed secret storage, TLS termination, platform identity, network policy, backups, runtime alert routing, signed build provenance and independent deployment canary.
