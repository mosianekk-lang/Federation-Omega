# ChatBridge Ω4.3 — Provider-Live Canary Harness

This harness is the next proof gate after the admitted Ω4.2 continuity/control source.

## Objective

Prove that one ChatBridge namespace can bind to one real OpenAI server-managed conversation and survive real process boundaries without manually replaying the prior transcript.

The harness also proves a persisted approval interruption can be resumed once, duplicate resume is fenced, and a cloned ChatBridge namespace obtains independent provider lineage.

## Secret boundary

The harness never accepts an API key as a CLI argument and never prints the key.

`OPENAI_API_KEY` must already exist in the executing process through an approved secret-injection path. Do not paste the key into chat, source, issue bodies, workflow YAML, logs, or command-line arguments.

## Provider dependencies

Use a trusted Python environment with the current OpenAI Agents SDK installed (`openai-agents`). The harness uses the admitted `OpenAIConversationsSession` provider adapter and exactly one server-managed continuation strategy.

The default canary model is `gpt-5.4-mini`. Override with `CHATBRIDGE_OPENAI_MODEL` or `--model` when a different currently available model is required.

## One-command proof

From repository root, with the approved secret already injected:

```bash
python -m bubbles.chatbridge_omega4.live_canary \
  --db .chatbridge/live_canary.sqlite3 \
  --namespace omega4-provider-canary \
  prove --branch-namespace omega4-provider-canary-branch
```

`prove` launches separate child processes for the continuation phases. The sequence is:

1. create/bind a real OpenAI Conversation and write provider readback;
2. start a new Python process and recover a synthetic marker using the same Conversation ID;
3. start another process and trigger a harmless `needs_approval=True` tool interruption;
4. persist serialized `RunState` and terminate that phase;
5. start another process, approve, and resume the saved state;
6. attempt the same resume again and require the fencing layer to reject it;
7. clone the ChatBridge namespace and bind the branch to an independent OpenAI Conversation;
8. emit a redacted proof receipt containing IDs/hashes/semantic states but no API key or raw agent output.

## Promotion boundary

A successful deterministic/source test does not equal a provider-live proof. Promote to `PROVIDER_LIVE_VERIFIED` only from the output of an actual run in an authorised provider environment and after the receipt/provider identity has been independently read back and archived under issue #455 / canonical controls.

This harness does not create a native ChatGPT chat-open hook and does not observe arbitrary ChatGPT/dashboard UI clicks.
