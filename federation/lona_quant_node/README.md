# Federation LONA Quant Node v2

Purpose: make LONA a governed quantitative research and backtest execution node inside Federation-Omega. This node is research-only. It does not expose or authorize live broker execution.

## Proven v1 path

1. Resolve/download market data in LONA.
2. Create deterministic Backtrader strategy code.
3. Read the native strategy code back and hash it.
4. Dispatch a backtest with explicit dates, frequency, cash, commission, leverage and parameters.
5. Treat the returned report ID as dispatched work only.
6. Poll status until COMPLETED or FAILED.
7. Retrieve the full report and preserve metrics/trades/report ID.
8. Reconcile the native evidence into a manifest.
9. Version strategy changes immutably and repeat under identical assumptions.
10. Admit execution capability independently from strategy suitability for live capital.

## v1 canary evidence

Dataset: SPY, daily, TIINGO, LONA symbol `9e60d261-2ffe-4f9f-8412-35f59224b6cd`.

v1 strategy: LONA `c9dc8521-938e-45e0-8708-fda32c080231`; report `bc6c79d0-3951-4b87-804a-c1fc3911e703`; total return 71.08%; CAGR 8.41%; Sharpe 0.55; maximum drawdown 28.30%.

v2 risk-control strategy: LONA `9761cff0-0f2b-48e4-9c18-83c1476dbaf8`; standard report `de6d3b60-df68-44af-9ab0-93de50d48952`; total return 71.67%; CAGR 8.47%; Sharpe 0.56; maximum drawdown 28.04%.

Commission-stress report: `9f774799-0f4e-44db-93cc-aff6e8e9a92f`; commission 0.30%; total return 63.17%; CAGR 7.64%; Sharpe 0.50; maximum drawdown 29.52%.

These results prove the LONA research execution/readback/versioning lane. They do not prove profitability out of sample, live execution quality, or suitability for real capital.

## v2 robustness escalation

The v2 layer adds four proof classes before any strategy can advance beyond a basic research canary:

- **Walk-forward / holdout evidence:** separate in-sample and later holdout periods. A full-history backtest is never treated as out-of-sample proof.
- **Parameter perturbation:** rerun nearby parameter sets to detect fragile single-point optima.
- **Cross-asset survival:** rerun the same strategy on independent assets when the hypothesis should generalize.
- **Benchmark-relative scoring:** compare the candidate against a transparent buy-and-hold benchmark under the same period, cash and commission assumptions.

Current robustness canary datasets are SPY, QQQ and IWM daily data from TIINGO. Exact LONA IDs and report IDs are recorded in `v2_robustness_manifest.json`.

`robustness.py` implements conservative research promotion scoring. Positive return alone is insufficient. The scorer also considers holdout Sharpe, benchmark-relative return, drawdown, trade count, perturbation survival, cross-asset survival and adverse-cost evidence. Its strongest state is `ROBUSTNESS_RESEARCH_ADMITTED`; that state still does not authorize paper trading or live capital.

## Required experiment identity

Use `experiment_identity.py` to fingerprint all economically material inputs: source-code hash, data IDs, candle frequency, period, cash, commission, leverage, buy-on-close and strategy parameters. Two reports with different fingerprints must never be treated as an apples-to-apples result.

## Promotion ladder

`DISPATCHED_NOT_VERIFIED` → `CANARY_EXECUTION_VERIFIED` → `ROBUSTNESS_RESEARCH_ADMITTED` → separate paper-trading gate → separate live-broker gate.

A strategy remains research-only until it survives independent holdout periods, parameter perturbation, adverse costs, cross-instrument/regime tests where appropriate, simple benchmark comparison, data-provenance controls and a separate paper-trading execution lane. Live brokerage requires a separate provider adapter, capital/risk limits, kill switch, order/fill reconciliation and explicit owner authorization.
