import {canonicalJson, constantTimeTokenMatch, createLogger, HttpError, jsonResponse, normalizedBearer, readBody, requestId, sha256} from './core.mjs';
import {generate, transcribe} from './evidence.mjs';
import {IMPLEMENTED_CAPABILITIES} from './capabilities.mjs';
import {configReadiness} from './config.mjs';

export function createApp({config, provider, logger = createLogger(), now = () => new Date()}) {
  let active = 0;
  let requestCount = 0;
  let failureCount = 0;
  let quotaDate = now().toISOString().slice(0, 10);
  let quotaUsed = 0;
  const idempotency = new Map();

  const cleanIdempotency = () => {
    const current = now().getTime();
    for (const [key, item] of idempotency.entries()) if (item.expiresAt <= current) idempotency.delete(key);
  };

  const checkAuth = (request) => {
    if (!config.sharedToken) return;
    if (!constantTimeTokenMatch(normalizedBearer(request.headers.authorization), config.sharedToken)) {
      throw new HttpError(401, 'UNAUTHORIZED', 'A valid bearer token is required');
    }
  };

  const consumeQuota = () => {
    const currentDate = now().toISOString().slice(0, 10);
    if (currentDate !== quotaDate) { quotaDate = currentDate; quotaUsed = 0; }
    if (quotaUsed >= config.dailyRequestLimit) throw new HttpError(429, 'DAILY_LIMIT_REACHED', 'The connector daily request budget has been reached');
    quotaUsed += 1;
  };

  return async function handler(request, response) {
    const id = requestId(request.headers['x-request-id']);
    const started = Date.now();
    let route = 'unknown';
    try {
      const url = new URL(request.url, 'http://connector.local');
      route = `${request.method} ${url.pathname}`;
      if (request.method === 'GET' && url.pathname === '/health') {
        return jsonResponse(response, 200, {status: 'ok', service: 'kim-dataverse-gemini-connector'}, id);
      }
      if (request.method === 'GET' && url.pathname === '/ready') {
        const readiness = configReadiness(config);
        return jsonResponse(response, readiness.ready ? 200 : 503, {...readiness, service: 'kim-dataverse-gemini-connector'}, id);
      }
      checkAuth(request);
      if (request.method === 'GET' && url.pathname === '/v1/capabilities') {
        return jsonResponse(response, 200, {implemented: IMPLEMENTED_CAPABILITIES, count: IMPLEMENTED_CAPABILITIES.length}, id);
      }
      if (request.method === 'GET' && url.pathname === '/metrics') {
        return jsonResponse(response, 200, {active, requests: requestCount, failures: failureCount, quotaDate, quotaUsed, quotaLimit: config.dailyRequestLimit, idempotencyEntries: idempotency.size}, id);
      }
      if (request.method !== 'POST' || !['/v1/generate', '/v1/transcribe'].includes(url.pathname)) {
        throw new HttpError(404, 'NOT_FOUND', 'Route not found');
      }
      if (active >= config.maxConcurrency) throw new HttpError(429, 'CONCURRENCY_LIMIT', 'Connector concurrency limit reached');
      const body = await readBody(request, config.maxRequestBytes);
      const idemKey = request.headers['idempotency-key'] || body.idempotencyKey;
      const bodyHash = sha256(canonicalJson(body));
      cleanIdempotency();
      if (idemKey) {
        if (!/^[A-Za-z0-9._:-]{8,200}$/.test(idemKey)) throw new HttpError(400, 'INVALID_IDEMPOTENCY_KEY', 'Idempotency key must contain 8 to 200 safe characters');
        const existing = idempotency.get(idemKey);
        if (existing && existing.bodyHash !== bodyHash) throw new HttpError(409, 'IDEMPOTENCY_CONFLICT', 'Idempotency key was already used with a different request');
        if (existing) return jsonResponse(response, 200, {...existing.payload, idempotentReplay: true}, id);
      }
      consumeQuota();
      active += 1;
      requestCount += 1;
      const controller = new AbortController();
      request.once('aborted', () => controller.abort());
      let payload;
      try {
        payload = url.pathname === '/v1/transcribe'
          ? await transcribe({input: body, provider, config, signal: controller.signal, now})
          : await generate({input: body, provider, config, signal: controller.signal});
      } finally {
        active -= 1;
      }
      const envelope = {requestId: id, idempotentReplay: false, data: payload};
      if (idemKey) idempotency.set(idemKey, {bodyHash, payload: envelope, expiresAt: now().getTime() + config.idempotencyTtlMs});
      logger('info', 'request.completed', {requestId: id, route, status: 200, durationMs: Date.now() - started, provider: provider.name});
      return jsonResponse(response, 200, envelope, id);
    } catch (error) {
      failureCount += 1;
      const known = error instanceof HttpError;
      const status = known ? error.status : 500;
      const code = known ? error.code : 'INTERNAL_ERROR';
      logger(status >= 500 ? 'error' : 'info', 'request.failed', {requestId: id, route, status, code, durationMs: Date.now() - started, details: known ? error.details : undefined});
      return jsonResponse(response, status, {requestId: id, error: {code, message: known ? error.message : 'Internal connector error', details: known ? error.details : undefined}}, id);
    }
  };
}
