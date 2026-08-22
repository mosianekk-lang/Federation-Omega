import assert from 'node:assert/strict';
import test from 'node:test';
import { projectPath, readJson } from '../src/config.js';
import { applyObservations, collectSource } from '../src/refresh.js';

const registry = readJson(projectPath('data', 'sources.json'));
const source = registry[0];
const observation = {
  sourceId: source.id,
  status: 'VERIFIED',
  canonicalUrl: source.canonicalUrl,
  canonicalUrlMatch: true,
  publisherMatch: true,
  observedAt: '2026-08-23T00:00:00.000Z',
  observedVersion: 'etag-v2',
  contentHash: `sha256:${'a'.repeat(64)}`,
};

test('verified observations update freshness evidence without changing source identity', () => {
  const result = applyObservations(registry, [observation]);
  assert.equal(result.changes.length, 1);
  assert.equal(result.updatedRegistry[0].canonicalUrl, source.canonicalUrl);
  assert.equal(result.updatedRegistry[0].version, 'etag-v2');
  assert.equal(result.updatedRegistry[0].verifiedAt, observation.observedAt);
});

test('source URL substitution is rejected', () => {
  assert.throws(
    () => applyObservations(registry, [{ ...observation, canonicalUrl: 'https://attacker.invalid/' }]),
    (error) => error.code === 'SOURCE_IDENTITY_MISMATCH',
  );
});

test('duplicate observations for one source are rejected', () => {
  assert.throws(
    () => applyObservations(registry, [observation, observation]),
    (error) => error.code === 'INVALID_INPUT',
  );
});

test('collector hashes bounded content and uses registry-fixed identity', async () => {
  const fetchImpl = async () => new Response('authoritative content', {
    status: 200,
    headers: { etag: 'v3', 'last-modified': 'Sat, 22 Aug 2026 00:00:00 GMT' },
  });
  const result = await collectSource(source, { fetchImpl, now: new Date('2026-08-22T12:00:00.000Z') });
  assert.equal(result.sourceId, source.id);
  assert.equal(result.observedVersion, 'v3');
  assert.match(result.contentHash, /^sha256:[0-9a-f]{64}$/);
  assert.equal(result.canonicalUrlMatch, true);
});

test('collector rejects oversized sources before ingestion', async () => {
  const fetchImpl = async () => new Response('0123456789', { status: 200, headers: { 'content-length': '10' } });
  await assert.rejects(
    collectSource(source, { fetchImpl, maximumBytes: 5 }),
    (error) => error.code === 'SOURCE_TOO_LARGE',
  );
});

test('collector rejects redirects for explicit registry review', async () => {
  const fetchImpl = async () => new Response('', { status: 302, headers: { location: 'https://example.com/' } });
  await assert.rejects(
    collectSource(source, { fetchImpl }),
    (error) => error.code === 'REDIRECT_REVIEW_REQUIRED',
  );
});
