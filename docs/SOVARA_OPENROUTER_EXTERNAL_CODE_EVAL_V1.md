# SOVARA OpenRouter External Code Evaluation v1

## Purpose

Provide SOVARA with a bounded, auditable path for sending an explicitly supplied code block to multiple external OpenRouter models for independent review and divergent engineering ideas.

This is an **external review** capability, not a code-execution capability. Model outputs are `PROPOSAL_ONLY` until SOVARA/SLOS independently validates them.

## Why this route

OpenRouter exposes a current model catalog and a common OpenAI-compatible chat interface. The evaluator resolves a provider-diverse panel from the live catalog instead of permanently pinning stale model slugs. The default selectors currently target DeepSeek V4 Flash, MiMo V2.5, GLM 5.2 and GPT-5.6 Luna families when available, with `openrouter/auto` as a fallback.

The evaluator uses a relatively exploratory temperature (`0.85`) and explicitly requests materially different redesign options. "Creative" means broader engineering exploration, not bypassing safety, privacy, law, provider policy, or authority controls.

## Security boundary

- Code is wrapped as `<UNTRUSTED_CODE>` and never executed.
- Instructions embedded in code/comments/strings are ignored.
- `OPENROUTER_API_KEY` is runtime-only.
- Requests default to `provider.data_collection = "deny"` and `provider.zdr = true`.
- Receipts hash source and outputs without persisting credential values.
- Live provider connectivity requires provider response/readback; source and CI success alone are insufficient.

## CLI

```bash
export OPENROUTER_API_KEY='...runtime secret...'
python ops/sovara_openrouter_code_eval_v1.py \
  --file path/to/code.py \
  --language python \
  --objective 'Find defects and propose materially different redesigns.' \
  --max-models 4 \
  --temperature 0.85 \
  --output review.json
```

Or pipe a code block:

```bash
cat path/to/code.py | python ops/sovara_openrouter_code_eval_v1.py --language python
```

## Live proof

`.github/workflows/sovara-openrouter-code-eval-canary.yml` runs source-only tests on pull requests. On an admitted `main` push (or manual dispatch), it runs a **synthetic, non-sensitive** external review canary only when the repository-scoped `OPENROUTER_API_KEY` secret is actually bound.

Live promotion requires at least two distinct resolved provider/model families to respond and a redacted receipt to be retained.

## Truth boundary

The capability is not `LIVE_OPENROUTER_CODE_EVALUATION` until the provider canary receipt is independently read back. A held canary preserves the source implementation while honestly leaving provider connectivity open.
