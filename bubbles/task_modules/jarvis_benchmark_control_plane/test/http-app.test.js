import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { projectPath, readJson } from '../src/config.js';
import { createHttpApp } from '../src/http-app.js';

const registry = readJson(projectPath('data', 'sources.json'));
const dimensions = readJson(projectPath('data', 'dimensions.json'));
const state = readJson(projectPath('examples', 'jarvis-state.sample.json'));

async function service(t, adminToken = '') {
  const directory = mkdtempSync(join(tmpdir(), 'jbcp-http-'));
  const ledgerPath = join(directory, 'ledger.jsonl');
  const app = createHttpApp({
    registry,
    dimensions,
    ledgerPath,
    adminToken,
    clock: () => new Date('2026-08-22T12:00:00.000Z'),
  });
  const server = createServer(app.handler);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  t.after(async () => {
    await new Promise((resolve) => server.close(resolve));
    rmSync(directory, { recursive: true, force: true });
  });
  const address = server.address();
  return { base: `http://127.0.0.1:${address.port}`, app };
}

test('health reports ledger state and disabled writes by default', async (t) => {
  const { base } = await service(t);
  const response = await fetch(`${base}/health`);
  const body = await response.json();
  assert.equal(response.status, 200);
  assert.equal(body.writeApi, 'DISABLED');
  assert.equal(body.continuousRuntime, 'CANDIDATE_NOT_SCHEDULED');
  assert.equal(body.ledger.valid, true);
});

test('evaluation endpoint returns bounded current-evidence result', async (t) => {
  const { base } = await service(t);
  const response = await fetch(`${base}/v1/evaluate`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ state }),
  });
  const body = await response.json();
  assert.equal(response.status, 200);
  assert.equal(body.opportunities.length, 3);
  assert.equal(body.evaluation.privateInternalParityClaimed, false);
});

test('cycle commit fails closed when write token is not configured', async (t) => {
  const { base } = await service(t);
  const response = await fetch(`${base}/v1/cycle/commit`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ state, idempotencyKey: 'http:test:0001' }),
  });
  const body = await response.json();
  assert.equal(response.status, 503);
  assert.equal(body.error.code, 'WRITES_DISABLED');
});

test('authorized commit is idempotent and updates the in-memory snapshot', async (t) => {
  const token = 'test-token-with-at-least-24-characters';
  const { base, app } = await service(t, token);
  const request = () => fetch(`${base}/v1/cycle/commit`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: `Bearer ${token}` },
    body: JSON.stringify({ state, observations: [], idempotencyKey: 'http:test:0002' }),
  });
  const first = await request();
  const second = await request();
  assert.equal(first.status, 201);
  assert.equal(second.status, 200);
  assert.equal((await second.json()).duplicate, true);
  assert.ok(app.snapshot().previousEvaluation);
});

test('wrong bearer token is rejected without parsing the requested mutation', async (t) => {
  const { base } = await service(t, 'correct-test-token-at-least-24-characters');
  const response = await fetch(`${base}/v1/cycle/commit`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: 'Bearer incorrect' },
    body: '{}',
  });
  assert.equal(response.status, 401);
  assert.equal((await response.json()).error.code, 'AUTHORIZATION_FAILURE');
});

test('same idempotency key with a changed request is rejected', async (t) => {
  const token = 'test-token-with-at-least-24-characters';
  const { base } = await service(t, token);
  const commit = (requestState) => fetch(`${base}/v1/cycle/commit`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: `Bearer ${token}` },
    body: JSON.stringify({ state: requestState, observations: [], idempotencyKey: 'http:test:0003' }),
  });
  assert.equal((await commit(state)).status, 201);
  const changed = { ...state, asOf: '2026-08-22T12:00:00.000Z' };
  const conflict = await commit(changed);
  assert.equal(conflict.status, 409);
  assert.equal((await conflict.json()).error.code, 'IDEMPOTENCY_CONFLICT');
});
