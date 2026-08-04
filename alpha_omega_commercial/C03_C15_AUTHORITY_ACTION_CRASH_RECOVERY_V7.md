# C03→C15 Authority Action Crash Recovery v7

## Verified dependency

This slice follows the merged authority action atomicity control in PR #127 at
`04d8677e07df8b2cf66d2e586defe0898c303f96`.

## Material defect closed

The v6 control plane restored all governed local persistence surfaces when a
failure was raised inside the running process. Its backup remained in memory,
so an abrupt process exit after `ACTION_PREPARED` could leave valid but partial
commercial state without a terminal transaction event. A restart could verify
the ledger but could not reconstruct the pre-action files.

## Smallest complete operational slice

`CrashSafeAtomicAuthoritySnapshotCommercialControlPlane` now:

1. captures every governed local state and ledger file before mutation;
2. writes the captured bytes into a temporary recovery bundle inside the state
   root;
3. hashes every captured file and the complete recovery manifest;
4. fsyncs the bundle and atomically renames it into place before
   `ACTION_PREPARED` is recorded;
5. binds the prepared transaction event to the recovery-manifest SHA-256;
6. restores an unterminated prepared transaction before any new consequential
   action is permitted after restart;
7. records `ACTION_ROLLED_BACK` with `PROCESS_RESTART_RECOVERY` after exact
   restoration;
8. retries the same restoration safely if the process exits during recovery;
9. fails closed when a required bundle is missing, path-invalid or tampered;
10. removes recovery bundles after successful commit or verified rollback and
    removes pre-prepare orphan bundles without promoting authority.

Covered local surfaces are commercial state, the commercial hash-linked ledger,
governed owner-authority state and ledger, and external-evidence state and
ledger.

## Scope limitation

This is local durable transaction recovery. It does not claim distributed
atomicity with an external cloud, payment, customer, partner or communication
provider. Live Cloud Run and payment-provider authority remain unavailable.
Customer demand, contracts, customer outcomes, enterprise assurance, partner
adoption and production scale remain unproven.

## Strategy and authority boundary

The service-enabled platform remains first and self-service SaaS remains held.
Verified live revenue remains zero.

Financial commitments, contracts, external communications, consequential
releases and revenue recognition remain owner-reserved.
