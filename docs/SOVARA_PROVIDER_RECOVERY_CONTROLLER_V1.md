# SOVARA Provider Recovery Controller v1

## Purpose

This controller turns provider failures into proof-bound recovery routes instead of repeated unchanged retries. It is deliberately provider-neutral and has no credential, IAM, billing, deployment or inference client.

It consumes redacted evidence from the three active Formation Omega provider trackers:

- Google/WIF/admin recovery — issue #52;
- direct OpenAI provider proof — issue #179;
- OpenRouter alternate-route binding — issue #592.

## Current Formation

The route tournament selects **REUSE_OPTIMISE** first:

1. repair the existing canonical Google WIF through a genuinely authenticated Google administration surface;
2. verify project `257649435135` and exact Cloud Run readback;
3. recover the operator token by secret reference and prove authenticated operator actions;
4. run the Gemini exact-nonce semantic canary;
5. use the recovered private secret plane to bind OpenRouter as an independent fallback;
6. keep direct OpenAI proof separate and resume it after usable project credit exists.

This ordering is not cosmetic. Google authority unlocks Secret Manager, operator administration and the private SOVARA gateway, so it removes more downstream constraints than creating another provider path first.

## Circuit-breaker rules

- **Google:** `invalid_target` opens the unchanged-WIF circuit. Do not repeat the same token exchange until provider/admin state changes.
- **OpenAI:** `credit_balance_exhausted` opens the paid-inference circuit. Model visibility remains valid; do not burn cycles retrying Responses until credit/project state changes.
- **OpenRouter:** a live public GPT-5.6 catalog does not prove runtime authority. Do not attempt inference until the execution key is securely bound and metadata readback succeeds.

Independent verified surfaces continue operating while those circuits are open.

## Usage

```bash
python3 ops/sovara_provider_recovery_controller.py \
  --google redacted-google-receipt.json \
  --openai redacted-openai-receipt.json \
  --openrouter redacted-openrouter-receipt.json \
  --out sovara-provider-recovery.json
```

The output includes per-lane state, stable failure fingerprints, circuit state, next action, auto-continue conditions and a Formation-style route tournament.

## Security and truth boundary

The controller rejects common secret-like material and must receive only redacted receipts. It performs no provider call, no paid inference, no IAM mutation and no external effect. Its route plan is not provider proof. Provider promotion still requires provider-native identity, execution and semantic readback.

## Relation to existing SOVARA / Alpha→Omega work

This is a small current-main integration of proven concepts already present in the estate: durable recovery, deterministic fingerprints, failure-first routing, independent-lane continuation, Formation route families and Alpha→Omega materially-different-route behavior. It does **not** claim that draft PR #558 or draft PR #562 are merged or deployed, and it does not duplicate their full runtimes.
