import { randomUUID } from 'node:crypto';
import { constantTimeEqual, sha256 } from './canonical.js';
import { commitPayload, evaluateCycle } from './engine.js';
import { ControlPlaneError, fail } from './errors.js';
import { assessRegistry, planRefresh } from './freshness.js';
import { appendLedger, verifyLedger } from './ledger.js';

function sendJson(response, status, payload, correlationId) {
  const body = JSON.stringify(payload);
  response.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(body),
    'cache-control': 'no-store',
    'x-content-type-options': 'nosniff',
    'x-frame-options': 'DENY',
    'referrer-policy': 'no-referrer',
    'content-security-policy': "default-src 'none'; frame-ancestors 'none'",
    'x-correlation-id': correlationId,
  });
  response.end(body);
}

async function readJsonBody(request, maximumBytes) {
  if (!/^application\/json(?:;|$)/i.test(request.headers['content-type'] || '')) {
    fail('INVALID_INPUT', 'content-type must be application/json', { status: 415 });
  }
  const declared = Number(request.headers['content-length']);
  if (Number.isFinite(declared) && declared > maximumBytes) {
    fail('INVALID_INPUT', 'request body is too large', { status: 413 });
  }
  const chunks = [];
  let total = 0;
  for await (const chunk of request) {
    total += chunk.length;
    if (total > maximumBytes) fail('INVALID_INPUT', 'request body is too large', { status: 413 });
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch {
    fail('INVALID_INPUT', 'request body must be valid JSON');
  }
}

function authorizeWrite(request, adminToken) {
  if (!adminToken) fail('WRITES_DISABLED', 'write API is disabled until an admin token is configured', { status: 503 });
  const header = request.headers.authorization || '';
  if (!header.startsWith('Bearer ') || !constantTimeEqual(header.slice(7), adminToken)) {
    fail('AUTHORIZATION_FAILURE', 'valid bearer token required', { status: 401 });
  }
}

export function createHttpApp({
  registry,
  dimensions,
  ledgerPath,
  previousEvaluation = null,
  adminToken = '',
  maximumBodyBytes = 1_000_000,
  clock = () => new Date(),
} = {}) {
  let currentRegistry = registry;
  let priorEvaluation = previousEvaluation;

  async function handler(request, response) {
    const suppliedId = request.headers['x-correlation-id'];
    const correlationId = typeof suppliedId === 'string' && /^[A-Za-z0-9._:-]{8,128}$/.test(suppliedId)
      ? suppliedId
      : randomUUID();
    try {
      const url = new URL(request.url, 'http://127.0.0.1');
      if (request.method === 'GET' && url.pathname === '/health') {
        return sendJson(response, 200, {
          status: 'ok',
          service: 'jarvis-benchmark-control-plane',
          schemaVersion: '1.0.0',
          writeApi: adminToken ? 'ENABLED' : 'DISABLED',
          continuousRuntime: 'CANDIDATE_NOT_SCHEDULED',
          ledger: verifyLedger(ledgerPath),
        }, correlationId);
      }
      if (request.method === 'GET' && url.pathname === '/v1/registry') {
        return sendJson(response, 200, {
          registry: currentRegistry,
          assessment: assessRegistry(currentRegistry, dimensions, clock()),
        }, correlationId);
      }
      if (request.method === 'GET' && url.pathname === '/v1/refresh/plan') {
        return sendJson(response, 200, planRefresh(currentRegistry, clock()), correlationId);
      }
      if (request.method === 'GET' && url.pathname === '/v1/ledger/verify') {
        return sendJson(response, 200, verifyLedger(ledgerPath), correlationId);
      }
      if (request.method === 'POST' && ['/v1/evaluate', '/v1/opportunities'].includes(url.pathname)) {
        const body = await readJsonBody(request, maximumBodyBytes);
        const cycle = evaluateCycle({
          registry: currentRegistry,
          dimensions,
          state: body.state || body,
          previousEvaluation: priorEvaluation,
          now: clock(),
        });
        return sendJson(response, 200,
          url.pathname.endsWith('opportunities')
            ? { conclusionState: cycle.evaluation.conclusionState, opportunities: cycle.opportunities }
            : cycle,
          correlationId);
      }
      if (request.method === 'POST' && url.pathname === '/v1/cycle/commit') {
        authorizeWrite(request, adminToken);
        const body = await readJsonBody(request, maximumBodyBytes);
        const observations = body.observations || [];
        const requestHash = sha256({ state: body.state, observations });
        const cycle = evaluateCycle({
          registry: currentRegistry,
          dimensions,
          state: body.state,
          observations,
          previousEvaluation: priorEvaluation,
          now: clock(),
        });
        const result = appendLedger(ledgerPath, commitPayload(cycle), {
          idempotencyKey: body.idempotencyKey,
          requestHash,
          now: clock(),
        });
        if (result.appended || result.duplicate) {
          currentRegistry = result.entry.payload.updatedRegistry;
          priorEvaluation = result.entry.payload.evaluation;
        }
        return sendJson(response, result.appended ? 201 : 200, {
          appended: result.appended,
          duplicate: result.duplicate,
          sequence: result.entry.sequence,
          ledgerHead: result.entry.hash,
          committed: result.entry.payload,
        }, correlationId);
      }
      return sendJson(response, 404, { error: { code: 'NOT_FOUND', message: 'route not found' } }, correlationId);
    } catch (error) {
      const known = error instanceof ControlPlaneError
        ? error
        : new ControlPlaneError('INTERNAL_ERROR', 'Unexpected control-plane failure', { status: 500 });
      return sendJson(response, known.status, {
        error: { code: known.code, message: known.message, ...(known.details ? { details: known.details } : {}) },
      }, correlationId);
    }
  }

  return {
    handler,
    snapshot: () => ({ registry: currentRegistry, previousEvaluation: priorEvaluation }),
  };
}
