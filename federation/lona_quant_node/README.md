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
8. Reconcile native evidence into a manifest.
9. Version strategy changes immutably and repeat under identical assumptions.
10. Admit execution capability independently from strategy suitability for live capital.

## v1 execution canary

Dataset: SPY, daily, TIINGO, LONA symbol `9e60d261-2ffe-4f9f-8412-35f59224b6cd`.

- v1 strategy report `bc6c79d0-3951-4b87-804a-c1fc3911e703`: return 71.08%, Sharpe 0.55, max drawdown 28.30%.
- v2 risk-control report `de6d3b60-df68-44af-9ab0-93de50d48952`: return 71.67%, Sharpe 0.56, max drawdown 28.04%.
- full-period 0.30% commission stress `9f774799-0f4e-44db-93cc-aff6e8e9a92f`: return 63.17%, Sharpe 0.50, max drawdown 29.52%.

These prove the LONA execution/readback/versioning lane, not live profitability.

## v2 robustness evidence

The v2 layer adds holdout separation, parameter perturbation, cross-asset survival and passive benchmark-relative scoring.

### Candidate results

- SPY in-sample 2020-2023: return 25.96%, Sharpe 0.36, max drawdown 28.04%, 8 closed trades.
- SPY holdout 2024-2026: return 27.67%, Sharpe 6.42, max drawdown 9.58%, only 4 closed trades.
- SPY perturbation 15/45: return 24.64%, Sharpe 1.55, max drawdown 10.69%, 7 closed trades.
- SPY perturbation 25/60: return 31.04%, Sharpe 2.90, max drawdown 10.47%, 4 closed trades.
- QQQ holdout: return 30.66%, Sharpe 1.47, max drawdown 12.79%, 5 closed trades.
- IWM holdout: return -0.01%, Sharpe -0.07, max drawdown 18.61%, 5 closed trades.

### Passive holdout benchmarks

- SPY buy-and-hold: return 63.51%, Sharpe 3.51, max drawdown 18.04%.
- QQQ buy-and-hold: return 74.97%, Sharpe 4.46, max drawdown 21.92%.
- IWM buy-and-hold: return 51.12%, Sharpe 3.13, max drawdown 26.38%.

### Current candidate decision

`REVISE_AND_RETEST`.

The candidate has lower drawdown than passive exposure on the SPY holdout and survives both nearby parameter perturbations, but it is not robustness-admitted because:

1. the SPY holdout has only four closed trades;
2. the candidate underperforms passive SPY by 35.84 percentage points;
3. it fails to generalize to IWM;
4. the dedicated holdout adverse-cost experiment is still pending.

The strategy remains preserved as a Failure-Win parent. Weak evidence is not deleted or rewritten as success.

## Hard-gated promotion contract

`robustness.py` now prevents a high Sharpe or positive return from masking weak evidence. Research admission requires, at minimum:

- at least 8 closed holdout trades;
- no material benchmark underperformance worse than 10 percentage points;
- at least 67% positive parameter-perturbation survival;
- at least 50% cross-asset survival;
- positive adverse-cost evidence;
- no hard gate failures;
- composite score >= 60 and holdout Sharpe >= 0.75.

The strongest state remains `ROBUSTNESS_RESEARCH_ADMITTED`; it does not authorize paper or live trading.

## Required experiment identity

Use `experiment_identity.py` to fingerprint all economically material inputs: source-code hash, data IDs, candle frequency, period, cash, commission, leverage, buy-on-close and strategy parameters. Two reports with different fingerprints must never be treated as equivalent.

## Promotion ladder

`DISPATCHED_NOT_VERIFIED` → `CANARY_EXECUTION_VERIFIED` → `ROBUSTNESS_RESEARCH_ADMITTED` → separate paper-trading gate → separate live-broker gate.

Live brokerage remains a separate future provider adapter requiring capital/risk limits, kill switch, order/fill reconciliation and explicit owner authorization.
