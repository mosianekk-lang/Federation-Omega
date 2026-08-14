# ChatBridge Ω4 — Provider Binding Gate

This document defines the next evolution from the provider-neutral Ω4 kernel to a provider-bound durable conversation runtime.

## OpenAI binding contract

The OpenAI Agents SDK supports persistent sessions and resumable runs. For OpenAI-hosted continuation, the runtime can instead use the Conversations API or a previous Responses API response identifier. These persistence strategies must not be mixed in the same run.

ChatBridge therefore maps one namespace generation to exactly one provider continuation mode:

| ChatBridge mode | Intended provider binding |
| --- | --- |
| `CLIENT_SESSION` | Agents SDK `Session` implementation such as SQLAlchemy/Redis/custom store |
| `OPENAI_CONVERSATION` | OpenAI Conversations API / `OpenAIConversationsSession` |
| `OPENAI_PREVIOUS_RESPONSE` | Responses API `previous_response_id` continuation |
| `NONE` | no provider continuation binding |

## Recommended production topology

```text
ChatGPT / app command surface
        ↓
ChatGov governance compiler
        ↓
ChatBridge namespace router
        ↓
PostgreSQL namespace + generation + governance ledger
        ↓
Agents SDK runtime
        ↓
ONE continuation strategy per turn
        ├─ SQLAlchemy/Redis/custom Session
        ├─ OpenAI Conversations API
        └─ previous_response_id
        ↓
OpenAI model/tool execution
        ↓
trace / result / approval state
        ↓
ChatBridge checkpoint + semantic readback
        ↓
Kim Dataverse / Drive archival replication
```

## Required provider-bound proof before promotion

Do not promote Ω4 from source candidate to provider-verified until all of the following pass on the exact admitted source version:

1. authorised OpenAI API credential is available through the approved credential path;
2. one live namespace is bound to one real provider continuation identity;
3. turn 1 is executed and its provider identity/state is read back;
4. a new process/worker restores the same namespace and continues the conversation without manually replaying the full old transcript;
5. an approval interruption is persisted and resumed without losing the Governance Capsule or approval gate;
6. a duplicate restore in the same destination session reuses the lease and does not replay an external effect;
7. a material checkpoint creates a new generation while the old generation remains restorable;
8. a clone creates an independent branch with its own provider continuation lineage;
9. release/tombstone prevents automatic resurrection;
10. traces/receipts bind the provider continuation identity to the exact ChatBridge generation and checkpoint fingerprint;
11. provider readback, not architecture alone, supports any claim of live durable continuity.

## Storage evolution

The local SQLite implementation is the deterministic reference core. Production should prefer a transactional multi-worker store such as PostgreSQL for namespaces, generations, governance capsules, events and restore leases. Redis may be added for low-latency lease/cache coordination, but Redis state must not become the sole source of durable lineage.

## ChatGPT boundary

Even after provider-bound Agents SDK/Conversations integration, ChatBridge must not claim a native invisible ChatGPT chat-open hook unless a real supported app/event surface proves it. A user may still need to open the destination chat/app surface and invoke `chatbridge restore "X"`.
