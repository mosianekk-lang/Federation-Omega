import assert from 'node:assert/strict';
import test from 'node:test';
import {DeveloperProvider, VertexProvider} from '../src/providers.mjs';

const response = (payload, status = 200) => new Response(JSON.stringify(payload), {status, headers: {'content-type': 'application/json'}});

test('Developer provider uses x-goog-api-key without exposing it in the URL', async () => {
  let observed;
  const provider = new DeveloperProvider({apiKey: 'secret', timeoutMs: 1_000, fetchImpl: async (url, options) => {
    observed = {url, options};
    return response({candidates: [{content: {parts: [{text: 'ok'}]}}]});
  }});
  const result = await provider.generate({model: 'gemini-2.5-flash', body: {contents: []}});
  assert.equal(result.text, 'ok');
  assert.equal(observed.options.headers['x-goog-api-key'], 'secret');
  assert.equal(observed.url.includes('secret'), false);
});

test('Vertex provider obtains an access token from the metadata server and uses regional endpoint', async () => {
  const calls = [];
  const provider = new VertexProvider({project: 'project', location: 'africa-south1', timeoutMs: 1_000, fetchImpl: async (url, options) => {
    calls.push({url, options});
    if (url.startsWith('http://metadata.google.internal')) return response({access_token: 'access', expires_in: 300});
    return response({candidates: [{content: {parts: [{text: 'ok'}]}}]});
  }});
  await provider.generate({model: 'gemini-2.5-flash', body: {contents: []}});
  assert.equal(calls.length, 2);
  assert.match(calls[1].url, /^https:\/\/africa-south1-aiplatform\.googleapis\.com\/v1\/projects\/project/);
  assert.equal(calls[1].options.headers.authorization, 'Bearer access');
});

test('provider errors are normalized without echoing credentials', async () => {
  const provider = new DeveloperProvider({apiKey: 'secret', timeoutMs: 1_000, fetchImpl: async () => response({error: {status: 'PERMISSION_DENIED', message: 'denied'}}, 403)});
  await assert.rejects(() => provider.generate({model: 'gemini-2.5-flash', body: {contents: []}}), (error) => error.code === 'GEMINI_PROVIDER_ERROR' && !JSON.stringify(error).includes('secret'));
});
