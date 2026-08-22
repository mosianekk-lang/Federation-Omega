# Failure and recovery record

The first failure-first run passed 21 of 23 tests and exposed two defects.

1. An HTTP retry with the same idempotency key recalculated its delta against the newly committed baseline, producing a different payload and a false conflict. The repair binds the key to a stable request fingerprint, returns the original committed transaction on a genuine retry and rejects the same key with a changed request.
2. A deliberately malformed ledger line without a payload caused hashing to throw before a clean corruption verdict. The repair treats missing payload as explicit corruption, returns structured verification errors and blocks every later append.

The expanded regression suite then passed 24 of 24 tests. Both defects now have positive and negative canaries.

The `npm test` wrapper could not be invoked in this managed environment because its command launch requested an unavailable network approval. The exact underlying script, `node --test --test-reporter=spec`, ran directly and passed. No package download or third-party dependency was required.
