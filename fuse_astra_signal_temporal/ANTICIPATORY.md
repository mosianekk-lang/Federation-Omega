# Anticipatory Intelligence Addendum v0.2

This tranche extends signal/time semantics into bounded anticipatory intelligence. It is not a prediction oracle and does not authorize consequential action by itself.

## New semantic targets

- `TIME.TREND` — deterministic trend direction, slope and fit quality.
- `TIME.FORECAST` — forecast envelope with uncertainty widening as horizon grows.
- `TIME.LEAD_LAG` — estimate whether one observed series tends to lead another; correlation is not causation.
- `TIME.REGIME` — classify baseline, shifting, elevated, depressed or volatile operating regimes.
- `SIGNAL.EARLY_WARNING` — combine fused confidence, salience, persistence and validated lead/lag evidence into a warning probability and optional lead time.
- `TIME.ACTION_WINDOW` — map fresh evidence, risk, reversibility, authority and lead time into WAIT/WATCH/INVESTIGATE/PREPARE/ACT/HOLD.
- `SIGNAL.OPPORTUNITY_PHASE` — classify owner-authorized market/research signals as too-early, emerging, actionable, crowded, declining or expired.

## Guardrails

1. Forecast confidence must decay with horizon and poor fit.
2. Lead/lag relationships remain hypotheses until causal evidence or intervention validates them.
3. Stale evidence cannot trigger direct action through this layer.
4. High-risk action without authority returns HOLD.
5. ACT is only reachable for sufficiently strong, fresh, reversible, authorized conditions; external effect authority remains CK.POLICY/SOVARA-owned.
6. Opportunity classification does not place trades, spend money or publish externally.
7. Algorithms are replaceable reference implementations behind semantic contracts; CFBE/evals may promote stronger models only after matched evidence.
