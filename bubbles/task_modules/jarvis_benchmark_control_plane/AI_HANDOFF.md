# AI handoff

Start with `README.md`, `BUILD_CONTRACT.json`, `PROJECT_MEMORY.md` and `governance/foresight_plan.json`.

Run `npm test`, `npm run validate`, the MODISA validator and `node src/cli.js ledger-verify` before changing truth-state claims. Preserve all source IDs and canonical URLs unless a current official page proves a migration. Add new sources with an explicit evidence grade, verification timestamp, freshness SLA and dimension mapping. Do not make private-team parity claims.

For a production continuation, the next authorized tasks are: provision a private runtime; place the admin token in managed secrets; bind platform identity; schedule the daemon; enable TLS and network policy; add backup/restore and alerts; produce signed provenance; deploy; read back health/ledger state; run an independent freshness and recovery canary. Only then may `deployed` or `proven` change.

Do not add a GitHub Actions workflow without reconciling it with the Federation Airlock and central-task-module doctrine.
