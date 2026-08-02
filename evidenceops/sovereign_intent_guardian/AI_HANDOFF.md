# AI handoff

Start by reading `README.md`, `FORMATION_SPEC.md`, `PROJECT_MEMORY.md` and `BUILD_CONTRACT.json` in full.

## Non-negotiable invariants

- Never add effect tools, connectors, network clients, cloud SDKs, subprocess execution or secret access.
- Never use owner voice or treat SIG as owner consent.
- Never turn `ALIGN` into execution, publication, deployment or release authority.
- Never clear a stop without the exact generation, a newer mission version and an exact configured resume-record hash.
- Never let an active scope stop exempt newer versions, or let a task below a persisted scope floor enter or claim.
- Never describe local allowlist configuration as authenticated issuer, signature or external Formation authority proof.
- Never allow a pre-stop or expired lease to heartbeat or complete.
- Never accept cadence from request/advisory input; use the delivered-output ledger.
- Never accept or execute a provider object, callback or callable adapter; only validate hash/reference receipt data.
- Never persist raw advisory failures or secret-like content in requests, registry IDs, mission or occurrence references, stop/resume subjects, dead letters or audit events.
- Never classify code, tests, SQLite rows, advisory agreement or a draft PR as deployed/autonomous proof.
- Never promote a learned repair without incident evidence, regression and healthy-case tests, independent review and a Formation permit.

## Verification commands

```bash
PYTHONPATH=. python -m unittest discover -s tests -v
python verify_guardian.py
python validate_build_contract.py BUILD_CONTRACT.json --require-proof
```

Before publication, revalidate current main, exact branch and PR absence, exact file scope, public-repository boundary, leak guard, OIFA, semantic readback and exact-head CI. Publish only a draft PR. Do not merge or deploy.
