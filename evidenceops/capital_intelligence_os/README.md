# EvidenceOps Capital Intelligence OS — v0.2 Durable Core

v0.2 advances the Genesis source nucleus into a replayable, tenant-scoped reference runtime without expanding financial authority.

Implemented: ProofGraph, A1 AuthorityGuard, transactional Durable AUTOPILOT, request-bound idempotency, tenant isolation, Restricted List, Deal Passport, consented/cohort-gated OutcomeNet, GRAVITY, financing stress, the 60-stage M&A lifecycle, maturity controls and ten new decision/learning algorithms.

OutcomeNet requires explicit opt-in, at least five unique tenants (or a higher participant threshold), and equal tenant aggregate weighting. This is privacy/risk reduction, **not** a formal differential-privacy claim.

Deal Passport carries claim fingerprints, evidence status, freshness, missing/conflicting facts and an integrity digest. It is **not** represented as a legal or PKI signature.

Authority remains `A1_INTERNAL`. Live orders, withdrawals, transfers, autonomous financial effects, evidence deletion, audit erasure and disabling information barriers remain denied. Consequential external actions remain human-gated. Private/clean-team/potentially-MNPI/restricted/privileged/unknown M&A information cannot flow into public-market/trading pathways.

SQLite is a reference persistence adapter proving atomicity, restart/replay, request-bound idempotency, tenant scoping and integrity checks. A commercial provider database must preserve those semantics and additionally prove encryption, HA, backup/restore, migrations, disaster recovery and tenant isolation.

Verification:
```bash
PYTHONPATH=. python -m unittest discover -s evidenceops/capital_intelligence_os/tests -v
PYTHONPATH=. python -m evidenceops.capital_intelligence_os.verify_release
python -m compileall -q evidenceops/capital_intelligence_os
```
Local v0.2 acceptance: 70 tests plus release verifier and compile check.
