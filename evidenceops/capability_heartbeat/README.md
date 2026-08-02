# EvidenceOps Heartbeat System

This package is the EvidenceOps heartbeat control plane for documented Kim DataVerse surfaces, participating chats, capability sources, response outboxes, adapter-remediation cases and connector-use Kimmie Seeds.

For every participating turn it:

1. hashes and checks the registered source evidence;
2. rejects missing, unproven, unsafe, costly or over-authority routes;
3. deduplicates semantically equivalent solutions;
4. selects one primary route;
5. admits up to three non-effectful cross-system assistants for verification or advice;
6. adopts an alternative only when its verified score exceeds the declared baseline without reducing safety;
7. preserves one effectful path and requires an external Formation permit before that path can be executed.
8. commits the turn, node state, response bundle and receipt atomically;
9. returns an acknowledgement or bounded assistance through the same authorised adapter;
10. opens and persistently reconciles a ranked workaround case for every unbound surface;
11. binds a Kimmie Seed PRE and POST receipt to connector calls routed through a participating adapter.

Run from the repository root:

```bash
python -m evidenceops.capability_heartbeat \
  --output scheduler/runtime/capability-heartbeat.json
```

The CLI is read-only except for its explicit report output. It does not execute a suggested route, expose private identifiers, grant authority, or inject messages into an inactive ChatGPT conversation. The current chat uses the generated intake during active turns; GitHub Actions supplies durable scheduled discovery artifacts for later readback.

The authenticated runtime exposes `/heartbeat/turn`, `/heartbeat/surfaces`, `/heartbeat/reconcile`, `/heartbeat/delivery`, `/heartbeat/connectors/seed`, `/heartbeat/connectors/cycle` and `/heartbeat/connectors/seeds`. The tool-only MCP adapter exposes matching ChatGPT tools.

Kimmie Seeds are policy envelopes, not credentials or executable implants. A PRE event must commit before a participating connector call and a POST receipt must bind its result hash afterward. Direct calls through unrelated connector paths cannot be intercepted; the affected surface remains `ADAPTER_REQUIRED` and its remediation case develops the supported proxy, webhook or polling route.
