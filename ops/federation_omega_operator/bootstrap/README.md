# Federation Omega GitHub WIF bootstrap
This package restores the missing keyless trust path without storing a Google service-account key. It binds only immutable repository ID 1292795464, immutable owner ID 261966700, main, and workflow_dispatch.

bootstrap_wif.py is dry-run by default and fails closed when no trusted Google machine identity exists. Apply mode creates or reuses the pool, provider and dedicated deployer account. The workflow uses immutable action commits, deploys the existing operator, proves the live CFRE action, invokes the hash-bound Drive bundle and retains receipts.

Test: python -m unittest -v test_bootstrap_wif.py
Dry run: python bootstrap_wif.py
Apply: python bootstrap_wif.py --apply --out bootstrap-receipt.json

Rollback: disable the provider first, prove token exchange rejection, then remove only bindings/resources recorded by the receipt. Never delete a pre-existing resource.
