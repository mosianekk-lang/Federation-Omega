import assert from 'node:assert/strict';
import { appendFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { appendLedger, lastCommittedState, verifyLedger } from '../src/ledger.js';

function workspace(t) {
  const directory = mkdtempSync(join(tmpdir(), 'jbcp-ledger-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  return join(directory, 'ledger.jsonl');
}

test('ledger appends and verifies a hash-chained entry', (t) => {
  const path = workspace(t);
  const result = appendLedger(path, { type: 'TEST', value: 1 }, {
    idempotencyKey: 'test:entry:0001',
    now: new Date('2026-08-22T00:00:00.000Z'),
  });
  assert.equal(result.appended, true);
  assert.deepEqual(verifyLedger(path).errors, []);
  assert.equal(verifyLedger(path).count, 1);
});

test('same idempotency key and payload returns the original entry', (t) => {
  const path = workspace(t);
  const payload = { type: 'TEST', value: 1 };
  const first = appendLedger(path, payload, { idempotencyKey: 'test:entry:0002' });
  const second = appendLedger(path, payload, { idempotencyKey: 'test:entry:0002' });
  assert.equal(first.appended, true);
  assert.equal(second.duplicate, true);
  assert.equal(second.entry.hash, first.entry.hash);
});

test('idempotency conflict fails closed', (t) => {
  const path = workspace(t);
  appendLedger(path, { value: 1 }, { idempotencyKey: 'test:entry:0003' });
  assert.throws(
    () => appendLedger(path, { value: 2 }, { idempotencyKey: 'test:entry:0003' }),
    (error) => error.code === 'IDEMPOTENCY_CONFLICT',
  );
});

test('ledger tampering is detected and blocks later writes', (t) => {
  const path = workspace(t);
  appendLedger(path, { value: 1 }, { idempotencyKey: 'test:entry:0004' });
  appendFileSync(path, '{}\n');
  assert.equal(verifyLedger(path).valid, false);
  assert.throws(
    () => appendLedger(path, { value: 2 }, { idempotencyKey: 'test:entry:0005' }),
    (error) => error.code === 'LEDGER_CORRUPT',
  );
});

test('latest committed registry is restored from the ledger', (t) => {
  const path = workspace(t);
  const updatedRegistry = [{ id: 'restored' }];
  appendLedger(path, { type: 'BENCHMARK_CYCLE_COMMIT', updatedRegistry, evaluation: { overallScore: 5 } }, {
    idempotencyKey: 'test:entry:0006',
  });
  const restored = lastCommittedState(path, [{ id: 'base' }]);
  assert.deepEqual(restored.registry, updatedRegistry);
  assert.equal(restored.evaluation.overallScore, 5);
});
