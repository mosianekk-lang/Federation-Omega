# Federation Capital Intelligence & Execution Suite v1

This package is the execution-side half of the Federation capital architecture. It is deliberately separated from EvidenceOps Capital Intelligence OS (CIOS).

## Authority split

- **LONA / Quant Evidence Fabric**: research, backtests, walk-forward, robustness and evidence admission.
- **CIOS**: portfolio intelligence and non-executable capital intent.
- **Capital Constitution**: mode and authority gate.
- **Risk Governor**: independent deterministic veto.
- **Digital Twin**: shadow execution against observed venue liquidity.
- **Venue adapters**: market observation only in v1. Luno is the first adapter.
- **Reconciler**: independent comparison of intent, market snapshot and simulated outcome.
- **Failure-Win**: consumes structured failures and produces mutation hypotheses; it does not self-authorize capital.

## v1 hard boundaries

`LIVE_ORDER`, `CANCEL_ORDER`, `CONVERT`, `WITHDRAWAL`, `TRANSFER`, `SEND`, and any other real financial effect are not implemented by this package.

The Luno adapter exposes public market-data GET operations only. Authenticated account observation is a separately bindable read-only extension and is not proven merely because a Luno account exists.

The only execution mode implemented in v1 is `SHADOW`. Paper and real-capital modes require later independent proof gates.

## Convergence path

`LONA research -> Quant Evidence Fabric -> CIOS portfolio decision -> CapitalIntent -> Capital Constitution -> Risk Governor -> Digital Twin -> venue snapshot -> ReconciliationReceipt -> Evidence/Failure-Win`

Every state transition is deterministic, hash-addressable and fail-closed. A positive research result cannot directly become an order, and a technically valid shadow fill cannot prove investment alpha.
