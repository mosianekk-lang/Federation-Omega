# Threat Model

## Protected assets
- device and identity risk metadata
- case decisions and evidence lineage
- model/policy configuration
- signing keys and integration secrets
- release and rollback evidence

## Threats
- forged or replayed telemetry
- malicious/poisoned indicators
- compromised sensor or integration
- model drift/adversarial evasion
- accidental privacy leakage
- unauthorized high-impact response
- secret leakage/supply-chain compromise
- false assurance from unverified deployment claims

## Controls
- authenticated ingestion boundary in production
- provenance HMAC and evidence hashes
- multi-source corroboration and calibrated confidence
- content-field minimization
- human gate for containment/high-impact actions
- offline candidate evaluation and no auto-promotion
- least privilege/IAM/WIF
- versioned evidence retention and immutable build digests
- canary/rollback/provider-native readback
