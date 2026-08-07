# EvidenceOps eCertify ZA

Production architecture for South African self-service document assurance.

The platform separates five concerns: citizen identity proofing, document integrity/source assurance, commissioner/certifier legal events, recipient acceptance rules, and public verification.

## Identity boundary
Identity proofing is provider-bound. EvidenceOps consumes authenticated signed verification receipts from an approved identity provider and does not implement or store raw biometric matching models, face images or reusable biometric templates in this repository. Provider-specific integrations implement `IdentityProviderAdapter` and must carry provider-native production evidence before promotion.

## Legal boundary
No identity result can by itself create a `CERTIFIED COPY` or `COMMISSIONED AFFIDAVIT` label. Those statuses require their separate authority/event gates. Affidavit commissioning uses physical presence as the default legal production route unless a current, specifically verified lawful exception applies.

## Runtime boundary
- `http_app.py` is the private identity/legal-routing API.
- `public_http_app.py` is the privacy-minimal public verification API.
- production private startup fails closed without provider trust configuration and a distributed replay guard.
- SQLite replay/public registry implementations are reference/local only.
- PostgreSQL-compatible replay is provided through an injected DB-API connection factory; credentials and exact private connection bindings remain outside public source.
- `deployment/deploy_cloud_run_canary.sh` targets only isolated `evidenceops-ecertify-za-*` services, uses zero traffic and authenticated access, and refuses the reserved Architron service name.

## Current maturity
v0.3 is merged on Federation-Omega `main`. v0.4 adds production boundary interfaces and deployment preflight. Public production availability is not claimed until identity-provider, POPIA/legal, commissioner, recipient, cloud, penetration-test and end-to-end readback gates are all proved.
