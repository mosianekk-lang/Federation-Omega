# Formation Specification — CIOS v0.3

Objective: integrate EvidenceOps market/trading intelligence without importing execution authority or creating an MNPI leakage path.

Routes evaluated:
1. Directly import a trading execution engine — rejected: coupling and authority inheritance risk.
2. Rebuild a second trading stack inside M&A — rejected: duplication and drift.
3. One-way PUBLIC evidence adapter — selected: strongest provenance, reuse and authority isolation.
4. Live provider execution — deferred: requires separate regulated/provider authority and runtime proof.

Highest-information reversible experiment: feed provenance-bearing PUBLIC observations through MarketTruthGate, create EvidenceOps claims/events, compute market/fundamental divergence, and simultaneously prove the bridge exposes no order/transfer method and rejects non-public observations.
