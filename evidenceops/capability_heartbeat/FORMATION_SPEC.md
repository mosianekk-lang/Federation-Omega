# Formation specification

## Mission

- Mission: `EVIDENCEOPS-CAPABILITY-HEARTBEAT-VERIFIED-V4-INTEGRATION`
- Mission version: `4`
- Local integration action: `F18-HEARTBEAT-ONE-AUTHORITY-INTEGRATION`
- Authority: `A1` for one bounded reversible local source integration only
- Runtime authority ceiling: `A0`, recommendation-only
- Cost: zero new recurring cost
- Manual owner tasks: none
- External effects: prohibited

The single-use local permit was consumed in the trusted Formation runtime and is not persisted in repository artifacts. It creates no GitHub, cloud, connector, IAM, secret, deployment, API, MCP or live-attachment authority.

## Decision path

`explicit caller -> metadata-only observation -> VerifiedV4Authority -> A0 recommendation -> registered signer -> complete signed lineage -> fresh destination registration -> destination-signed receipt -> atomic local metadata record`

The path terminates at recommendation and local receipt. Catalogue, scheduler, runtime and MCP scaffolding cannot become a second authority.

## Fail-closed conditions

Unknown or raw fields; wrong namespaces; credentials; duplicate JSON keys; path escapes; missing authority; unregistered or stale nodes; signer/key/version/rotation mismatch; wrong owner, matter, classification or generation; A1-A5 runtime authority; effectful candidate; incomplete, mutated, forged, future, stale, expired or looping lineage; more than three hops; stale destination registration; receipt mismatch; replay conflict; stopped generation; fixture ingress; unhosted or session-only ingress; ledger rollback; respawn drift; and any live-awareness flag terminate without recommendation or ingress.

## States

- Designed: yes
- Implemented locally: yes
- Tested: only as recorded by current reproducible commands
- Registered live: no
- Authorized live: no
- Ready live: no
- Deployed: no
- Proven live: no

Canonical maturity: `DURABLE_FOUNDATION_IMPLEMENTED_NOT_ATTACHED`.
