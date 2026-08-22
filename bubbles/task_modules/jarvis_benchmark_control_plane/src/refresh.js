import { sha256 } from './canonical.js';
import { fail } from './errors.js';
import { planRefresh } from './freshness.js';
import { validateObservation, validateRegistry } from './validation.js';

export function applyObservations(registry, observations) {
  validateRegistry(registry);
  if (!Array.isArray(observations)) fail('INVALID_INPUT', 'observations must be an array');
  const byId = new Map(registry.map((source) => [source.id, source]));
  const seen = new Set();
  const changes = [];
  for (const observation of observations) {
    const source = byId.get(observation?.sourceId);
    if (!source) fail('INVALID_INPUT', `unknown observation source: ${observation?.sourceId}`);
    if (seen.has(source.id)) fail('INVALID_INPUT', `duplicate observation source: ${source.id}`);
    seen.add(source.id);
    validateObservation(observation, source);
    const updated = {
      ...source,
      verifiedAt: observation.observedAt,
      version: observation.observedVersion,
      contentHash: observation.contentHash,
      ...(observation.sourceUpdatedAt ? { sourceUpdatedAt: observation.sourceUpdatedAt } : {}),
    };
    byId.set(source.id, updated);
    changes.push({
      sourceId: source.id,
      beforeHash: sha256(source),
      afterHash: sha256(updated),
      versionChanged: source.version !== updated.version,
      contentChanged: source.contentHash !== updated.contentHash,
    });
  }
  return {
    updatedRegistry: registry.map((source) => byId.get(source.id)),
    changes,
  };
}

async function boundedBody(response, maximumBytes) {
  const declared = Number(response.headers.get('content-length'));
  if (Number.isFinite(declared) && declared > maximumBytes) {
    fail('SOURCE_TOO_LARGE', `source exceeds ${maximumBytes} bytes`, { status: 502 });
  }
  if (!response.body?.getReader) {
    const buffer = Buffer.from(await response.arrayBuffer());
    if (buffer.length > maximumBytes) fail('SOURCE_TOO_LARGE', `source exceeds ${maximumBytes} bytes`, { status: 502 });
    return buffer;
  }
  const reader = response.body.getReader();
  const chunks = [];
  let total = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > maximumBytes) {
      await reader.cancel();
      fail('SOURCE_TOO_LARGE', `source exceeds ${maximumBytes} bytes`, { status: 502 });
    }
    chunks.push(Buffer.from(value));
  }
  return Buffer.concat(chunks);
}

export async function collectSource(source, {
  fetchImpl = globalThis.fetch,
  now = new Date(),
  timeoutMs = 10_000,
  maximumBytes = 2_000_000,
} = {}) {
  const canonical = new URL(source.canonicalUrl);
  if (canonical.protocol !== 'https:') fail('INVALID_INPUT', 'collector accepts HTTPS registry URLs only');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchImpl(canonical, {
      method: 'GET',
      redirect: 'manual',
      signal: controller.signal,
      headers: {
        accept: 'text/html,application/json,text/plain;q=0.8',
        'user-agent': 'JARVIS-Benchmark-Control-Plane/1.0',
      },
    });
    if (response.status >= 300 && response.status < 400) {
      fail('REDIRECT_REVIEW_REQUIRED', `registry source redirected: ${source.id}`, { status: 502 });
    }
    if (!response.ok) fail('EXTERNAL_API_FAILURE', `source returned HTTP ${response.status}: ${source.id}`, { status: 502 });
    if (response.url) {
      const final = new URL(response.url);
      if (final.origin !== canonical.origin || final.pathname !== canonical.pathname) {
        fail('SOURCE_IDENTITY_MISMATCH', `response URL changed for ${source.id}`, { status: 502 });
      }
    }
    const body = await boundedBody(response, maximumBytes);
    const lastModified = response.headers.get('last-modified');
    const sourceUpdatedAt = lastModified && Number.isFinite(Date.parse(lastModified))
      ? new Date(lastModified).toISOString()
      : source.sourceUpdatedAt;
    return {
      sourceId: source.id,
      status: 'VERIFIED',
      canonicalUrl: source.canonicalUrl,
      canonicalUrlMatch: true,
      publisherMatch: true,
      observedAt: (now instanceof Date ? now : new Date(now)).toISOString(),
      observedVersion: response.headers.get('etag') || lastModified || source.version,
      contentHash: sha256(body),
      ...(sourceUpdatedAt ? { sourceUpdatedAt } : {}),
    };
  } catch (error) {
    if (error?.name === 'AbortError') fail('TIMEOUT', `source collection timed out: ${source.id}`, { status: 504 });
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export async function collectDueSources(registry, options = {}) {
  const plan = planRefresh(registry, options.now, options.maximumSources || 5);
  const observations = [];
  const failures = [];
  for (const item of plan.selected) {
    const source = registry.find((candidate) => candidate.id === item.sourceId);
    try {
      observations.push(await collectSource(source, options));
    } catch (error) {
      failures.push({ sourceId: source.id, code: error.code || 'EXTERNAL_API_FAILURE', message: error.message });
    }
  }
  return { plan, observations, failures };
}
