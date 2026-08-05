import assert from 'node:assert/strict';
import http from 'node:http';
import test from 'node:test';
import {createApp} from '../src/app.mjs';
import {loadConfig} from '../src/config.mjs';

const silent = () => {};

function fakeProvider({delay = 0, reject = null, text = 'model text'} = {}) {
  return {
    name: 'fake',
    validateSource(source) { if (source.uri && !source.uri.startsWith('gs://')) throw new Error('bad source'); },
    async generate({body}) {
      if (delay) await new Promise((resolve) => setTimeout(resolve, delay));
      if (reject) throw reject;
      const transcript = body.generationConfig?.responseMimeType === 'application/json'
        ? JSON.stringify({verbatimTranscript: 'Hello', utterances: [], detectedLanguages: ['en'], unknownSegments: [], qualityWarnings: [], summary: 'Greeting'})
        : text;
      return {text: transcript, payload: {candidates: [{content: {parts: [{text: transcript}]}, finishReason: 'STOP'}], usageMetadata: {totalTokenCount: 7}}};
    }
  };
}

async function withServer(options, task) {
  const config = loadConfig({port: 0, providerMode: 'vertex', project: 'test-project', maxRequestBytes: 10_000, maxInlineAudioBytes: 1_000, ...options.config});
  const server = http.createServer(createApp({config, provider: options.provider || fakeProvider(), logger: silent, now: options.now}));
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  try { await task(base); } finally { await new Promise((resolve) => server.close(resolve)); }
}

test('health and readiness are non-secret and available', async () => withServer({}, async (base) => {
  const health = await fetch(`${base}/health`);
  assert.equal(health.status, 200);
  assert.equal((await health.json()).status, 'ok');
  const ready = await fetch(`${base}/ready`);
  assert.equal(ready.status, 200);
  assert.equal((await ready.json()).provider, 'vertex');
}));

test('generate returns normalized metadata and output hash', async () => withServer({}, async (base) => {
  const response = await fetch(`${base}/v1/generate`, {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({prompt: 'hello'})});
  const body = await response.json();
  assert.equal(response.status, 200);
  assert.equal(body.data.text, 'model text');
  assert.match(body.data.outputSha256, /^[a-f0-9]{64}$/);
}));

test('transcription records input and output integrity without claiming verification', async () => withServer({}, async (base) => {
  const response = await fetch(`${base}/v1/transcribe`, {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({caseId: 'CASE-EXAMPLE-001', audio: {mimeType: 'audio/wav', dataBase64: Buffer.from('audio').toString('base64')}})});
  const body = await response.json();
  assert.equal(response.status, 200);
  assert.equal(body.data.transcript.verbatimTranscript, 'Hello');
  assert.equal(body.data.evidence.evidentiaryStatus, 'MODEL_GENERATED_REQUIRES_HUMAN_VERIFICATION');
  assert.match(body.data.evidence.contentSha256, /^[a-f0-9]{64}$/);
  assert.match(body.data.evidence.outputSha256, /^[a-f0-9]{64}$/);
}));

test('shared-token mode rejects missing authorization', async () => withServer({config: {sharedToken: 'correct-secret'}}, async (base) => {
  const response = await fetch(`${base}/v1/generate`, {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({prompt: 'hello'})});
  assert.equal(response.status, 401);
  assert.equal((await response.json()).error.code, 'UNAUTHORIZED');
}));

test('shared-token mode accepts exact bearer token', async () => withServer({config: {sharedToken: 'correct-secret'}}, async (base) => {
  const response = await fetch(`${base}/v1/generate`, {method: 'POST', headers: {'content-type': 'application/json', authorization: 'Bearer correct-secret'}, body: JSON.stringify({prompt: 'hello'})});
  assert.equal(response.status, 200);
}));

test('invalid JSON and oversized requests fail closed', async () => withServer({config: {maxRequestBytes: 1_024}}, async (base) => {
  const invalid = await fetch(`${base}/v1/generate`, {method: 'POST', body: '{'});
  assert.equal(invalid.status, 400);
  const oversized = await fetch(`${base}/v1/generate`, {method: 'POST', body: JSON.stringify({prompt: 'x'.repeat(2_000)})});
  assert.equal(oversized.status, 413);
}));

test('model allowlist and inline-audio limit are enforced', async () => withServer({config: {maxInlineAudioBytes: 4}}, async (base) => {
  const model = await fetch(`${base}/v1/generate`, {method: 'POST', body: JSON.stringify({prompt: 'x', model: 'not-allowed'})});
  assert.equal(model.status, 400);
  const audio = await fetch(`${base}/v1/transcribe`, {method: 'POST', body: JSON.stringify({audio: {mimeType: 'audio/wav', dataBase64: Buffer.from('12345').toString('base64')}})});
  assert.equal(audio.status, 413);
}));

test('idempotency replays identical requests and rejects body conflicts', async () => withServer({}, async (base) => {
  const headers = {'content-type': 'application/json', 'idempotency-key': 'case-key-123'};
  const first = await fetch(`${base}/v1/generate`, {method: 'POST', headers, body: JSON.stringify({prompt: 'same'})});
  assert.equal(first.status, 200);
  const replay = await fetch(`${base}/v1/generate`, {method: 'POST', headers, body: JSON.stringify({prompt: 'same'})});
  assert.equal((await replay.json()).idempotentReplay, true);
  const conflict = await fetch(`${base}/v1/generate`, {method: 'POST', headers, body: JSON.stringify({prompt: 'different'})});
  assert.equal(conflict.status, 409);
}));

test('daily budget and concurrency limits are enforced', async () => withServer({config: {dailyRequestLimit: 1, maxConcurrency: 1}, provider: fakeProvider({delay: 40})}, async (base) => {
  const firstPromise = fetch(`${base}/v1/generate`, {method: 'POST', body: JSON.stringify({prompt: 'one'})});
  await new Promise((resolve) => setTimeout(resolve, 5));
  const concurrent = await fetch(`${base}/v1/generate`, {method: 'POST', body: JSON.stringify({prompt: 'two'})});
  assert.equal(concurrent.status, 429);
  assert.equal((await firstPromise).status, 200);
  const quota = await fetch(`${base}/v1/generate`, {method: 'POST', body: JSON.stringify({prompt: 'three'})});
  assert.equal(quota.status, 429);
}));

test('capability and metrics endpoints expose bounded operational state', async () => withServer({}, async (base) => {
  const capabilities = await (await fetch(`${base}/v1/capabilities`)).json();
  assert.ok(capabilities.count >= 40);
  const metrics = await (await fetch(`${base}/metrics`)).json();
  assert.equal(metrics.quotaLimit, 250);
}));
