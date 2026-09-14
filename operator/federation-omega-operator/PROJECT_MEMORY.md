# Project Memory

- Live service: federation-omega-operator, sov-hybrid-suite, africa-south1.
- Live version: fo-operator-v1-image-cloudbuild; five observed actions.
- The July FO-AIS installer is a three-action historical ancestor.
- PFRD and the two control-plane archives are different systems.
- GitHub holds clients/receipts, not the current live source.

Candidate delta: bounded WIF inventory; safe Run/Build/health/WIF projections;
timing-safe auth; request IDs; bounded body; redacted logs; timeout mapping;
HTTP smoke tests; container and continuity artifacts; fail-closed deploy adapter.

Proof: 13/13 tests, four syntax checks, leak guard. No live call, GitHub write,
merge, build, deploy, IAM, or traffic change is claimed.

Next: publish draft with exact-head hashes; run CI; reconcile live build/source;
implement adapter; build no-traffic canary; prove rollback before promotion.
