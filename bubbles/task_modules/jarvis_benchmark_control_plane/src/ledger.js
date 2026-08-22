import { appendFileSync, closeSync, existsSync, mkdirSync, openSync, readFileSync, statSync, unlinkSync } from 'node:fs';
import { dirname } from 'node:path';
import { sha256 } from './canonical.js';
import { fail } from './errors.js';

const GENESIS = 'GENESIS';
const MAX_LEDGER_BYTES = 50_000_000;
const MAX_LINE_BYTES = 5_000_000;

export function readEntries(path) {
  if (!existsSync(path)) return [];
  if (statSync(path).size > MAX_LEDGER_BYTES) fail('LEDGER_LIMIT_EXCEEDED', 'ledger exceeds bounded size');
  const text = readFileSync(path, 'utf8').trim();
  if (!text) return [];
  return text.split('\n').map((line, index) => {
    if (Buffer.byteLength(line) > MAX_LINE_BYTES) fail('LEDGER_LIMIT_EXCEEDED', `ledger line ${index + 1} is oversized`);
    try {
      return JSON.parse(line);
    } catch {
      fail('LEDGER_CORRUPT', `ledger line ${index + 1} is not valid JSON`);
    }
  });
}

function expectedEntryHash(entry) {
  const { hash: ignored, ...unsigned } = entry;
  return sha256(unsigned);
}

export function verifyLedger(path) {
  let entries;
  try {
    entries = readEntries(path);
  } catch (error) {
    return { valid: false, count: 0, head: null, errors: [error.code || error.message] };
  }
  const errors = [];
  let previousHash = GENESIS;
  entries.forEach((entry, index) => {
    const sequence = index + 1;
    if (entry.sequence !== sequence) errors.push(`SEQUENCE_MISMATCH:${sequence}`);
    if (entry.previousHash !== previousHash) errors.push(`CHAIN_MISMATCH:${sequence}`);
    if (!Object.hasOwn(entry, 'payload')) {
      errors.push(`PAYLOAD_MISSING:${sequence}`);
    } else if (entry.payloadHash !== sha256(entry.payload)) {
      errors.push(`PAYLOAD_HASH_MISMATCH:${sequence}`);
    }
    if (entry.hash !== expectedEntryHash(entry)) errors.push(`ENTRY_HASH_MISMATCH:${sequence}`);
    previousHash = entry.hash;
  });
  return {
    valid: errors.length === 0,
    count: entries.length,
    head: entries.at(-1)?.hash || GENESIS,
    errors,
  };
}

export function appendLedger(path, payload, { idempotencyKey, requestHash = null, now = new Date() } = {}) {
  if (typeof idempotencyKey !== 'string' || !/^[A-Za-z0-9._:-]{8,160}$/.test(idempotencyKey)) {
    fail('INVALID_INPUT', 'idempotencyKey must be 8-160 safe characters');
  }
  if (requestHash !== null && !/^sha256:[0-9a-f]{64}$/.test(requestHash)) {
    fail('INVALID_INPUT', 'requestHash must be a SHA-256 digest');
  }
  mkdirSync(dirname(path), { recursive: true });
  const lockPath = `${path}.lock`;
  let lock;
  try {
    lock = openSync(lockPath, 'wx', 0o600);
  } catch {
    fail('LEDGER_BUSY', 'ledger is locked by another writer', { status: 409 });
  }
  try {
    const verification = verifyLedger(path);
    if (!verification.valid) fail('LEDGER_CORRUPT', 'ledger verification failed before append', { details: verification.errors });
    const entries = readEntries(path);
    const payloadHash = sha256(payload);
    const existing = entries.find((entry) => entry.idempotencyKey === idempotencyKey);
    if (existing) {
      const sameRequest = requestHash !== null && existing.requestHash === requestHash;
      const samePayload = requestHash === null && existing.payloadHash === payloadHash;
      if (!sameRequest && !samePayload) {
        fail('IDEMPOTENCY_CONFLICT', 'idempotency key was already used for a different payload', { status: 409 });
      }
      return { appended: false, duplicate: true, entry: existing, verification };
    }
    const entry = {
      sequence: entries.length + 1,
      timestamp: (now instanceof Date ? now : new Date(now)).toISOString(),
      idempotencyKey,
      ...(requestHash ? { requestHash } : {}),
      previousHash: entries.at(-1)?.hash || GENESIS,
      payloadHash,
      payload,
    };
    entry.hash = expectedEntryHash(entry);
    appendFileSync(path, `${JSON.stringify(entry)}\n`, { encoding: 'utf8', mode: 0o600, flush: true });
    const after = verifyLedger(path);
    if (!after.valid) fail('PARTIAL_WRITE', 'ledger failed verification after append', { details: after.errors });
    return { appended: true, duplicate: false, entry, verification: after };
  } finally {
    if (lock !== undefined) closeSync(lock);
    if (existsSync(lockPath)) unlinkSync(lockPath);
  }
}

export function lastCommittedState(path, fallbackRegistry) {
  const verification = verifyLedger(path);
  if (!verification.valid) fail('LEDGER_CORRUPT', 'cannot restore state from an invalid ledger');
  const lastCommit = readEntries(path).filter((entry) => entry.payload?.type === 'BENCHMARK_CYCLE_COMMIT').at(-1);
  return {
    registry: lastCommit?.payload?.updatedRegistry || fallbackRegistry,
    evaluation: lastCommit?.payload?.evaluation || null,
    ledger: verification,
  };
}
