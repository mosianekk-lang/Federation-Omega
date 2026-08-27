# Federation Quant Evidence Fabric v3

Research-only orchestration and evidence layer around LONA. It does not authorize paper trading, broker connectivity, or real-capital execution.

## Authority separation

- GitHub/Federation-Omega: canonical code, tests, governance, admitted manifests.
- LONA: provider-native market data, strategy objects, backtest execution, reports and immutable strategy versions.
- Federation Quant Evidence Ledger (Google Sheets): human-readable experiment/tournament/decision projection.
- SOVARA: event transport only after a direct runtime binding is separately proven. It is not canonical experiment storage.

## Pipeline

`hypothesis -> provider tournament -> source readback/hash -> smoke test -> walk-forward -> parameter neighborhood -> cross-asset -> adverse cost -> benchmark comparison -> evidence receipt -> REJECT/REVISE/RESEARCH_ADMITTED`

Every state transition is proof-bound. A generation job, saved strategy, backtest report ID or GitHub commit is not equivalent to verified evidence.

## v3 controls

- `queue.py`: legal experiment state transitions, deterministic experiment IDs, duplicate suppression.
- `evidence.py`: SHA-256 hash-chained append-only receipts.
- `tournament.py`: provider identity/fairness and candidate eligibility checks.
- `walkforward.py`: expanding train/holdout windows plus parameter/cost/asset survival batteries.
- `mutation.py`: Failure-Win mutation proposals causally derived from observed failure signatures.
- `tournament_g1.json`: live first-generation provider tournament provenance and LONA report IDs.

## G1 fairness

OpenAI, Google, Anthropic, xAI and OpenRouter received the same strategy specification. xAI failed because its LONA provider configuration lacks `XAI_API_KEY`; that failure is preserved and no provider is substituted under the xAI label.

The four completed providers have native strategy IDs and source SHA-256 identities. Their original generated source is tested before any repair. LONA generation-review scores are metadata only and do not count as empirical performance evidence.

## Promotion boundaries

`RESEARCH_ADMITTED` means only that a strategy survived the configured historical evidence battery. It never implies future profitability, paper-trading approval, or authorization to place real orders. Any future broker node requires a separate provider contract, risk limits, kill switch, order/fill reconciliation, paper-trading proof and explicit owner authorization.
