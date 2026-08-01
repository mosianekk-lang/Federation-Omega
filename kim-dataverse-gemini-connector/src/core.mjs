import {createHash, randomUUID, timingSafeEqual} from 'node:crypto';

export class HttpError extends Error {
  constructor(status, code, message, details = undefined) {
    super(message);
    this.name = 'HttpError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export const sha256 = (value) => createHash('sha256').update(value).digest('hex');
export const requestId = (headerValue) => (/^[A-Za-z0-9._:-]{8,128}$/.test(headerValue || '') ? headerValue : randomUUID());

export function constantTimeTokenMatch(actual, expected) {
  const left = Buffer.from(actual || '');
  const right = Buffer.from(expected || '');
  if (left.length !== right.length || left.length === 0) return false;
  return timingSafeEqual(left, right);
}

export function redact(value) {
  if (Array.isArray(value)) return value.map(redact);
  if (!value || typeof value !== 'object') return value;
  const output = {};
  for (const [key, child] of Object.entries(value)) {
    output[key] = /key|secret|token|authorization|credential|audio|database64/i.test(key) ? '[REDACTED]' : redact(child);
  }
  return output;
}

export function safeJsonParse(value, code = 'INVALID_JSON') {
  try { return JSON.parse(value); }
  catch { throw new HttpError(400, code, 'Request body must contain valid JSON'); }
}

export function jsonResponse(response, status, payload, id) {
  const encoded = Buffer.from(JSON.stringify(payload));
  response.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': encoded.length,
    'cache-control': 'no-store',
    'x-content-type-options': 'nosniff',
    'x-request-id': id
  });
  response.end(encoded);
}

export function normalizedBearer(header) {
  const match = /^Bearer\s+(.+)$/i.exec(header || '');
  return match ? match[1] : '';
}

export function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`;
  return JSON.stringify(value);
}

export async function readBody(request, maximumBytes) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > maximumBytes) throw new HttpError(413, 'REQUEST_TOO_LARGE', `Request exceeds ${maximumBytes} bytes`);
    chunks.push(chunk);
  }
  if (size === 0) throw new HttpError(400, 'EMPTY_BODY', 'A JSON request body is required');
  return safeJsonParse(Buffer.concat(chunks).toString('utf8'));
}

export function createLogger(output = console) {
  return (level, event, fields = {}) => output[level === 'error' ? 'error' : 'log'](JSON.stringify({
    timestamp: new Date().toISOString(), level, event, ...redact(fields)
  }));
}
