import { createHash, timingSafeEqual } from 'node:crypto';

function normalize(value) {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (Array.isArray(value)) return value.map(normalize);
  if (typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value).sort().map((key) => [key, normalize(value[key])]),
    );
  }
  throw new TypeError(`Unsupported canonical value: ${typeof value}`);
}

export function stableStringify(value) {
  return JSON.stringify(normalize(value));
}

export function sha256(value) {
  const bytes = Buffer.isBuffer(value)
    ? value
    : Buffer.from(typeof value === 'string' ? value : stableStringify(value));
  return `sha256:${createHash('sha256').update(bytes).digest('hex')}`;
}

export function constantTimeEqual(left, right) {
  const a = Buffer.from(String(left));
  const b = Buffer.from(String(right));
  return a.length === b.length && timingSafeEqual(a, b);
}
