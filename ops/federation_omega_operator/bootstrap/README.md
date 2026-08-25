# Federation Omega private-Ops WIF bootstrap
This package prepares a keyless trust path without storing a Google service-account key. It is intentionally not an active workflow in the quarantined public source repository. The supplied example must be materialized automatically inside a separately governed private Ops repository using that repository's immutable numeric IDs.

bootstrap_wif.py is dry-run by default and fails closed when no trusted Google machine identity exists. Apply mode creates or reuses the pool, provider and dedicated deployer account, and rejects drift in an existing provider. The private workflow must use immutable action commits, exact hashes, semantic readback, and rollback.

Test: python -m unittest -v test_bootstrap_wif.py
Dry run: python bootstrap_wif.py --config PRIVATE_WIF_CONFIG.json
Apply: python bootstrap_wif.py --config PRIVATE_WIF_CONFIG.json --apply --out bootstrap-receipt.json

The private configuration and exact Drive source pointer must not be committed to this public repository. Rollback: disable the provider first, prove token exchange rejection, then remove only bindings/resources recorded by the receipt. Never delete a pre-existing resource.
