import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { sha256 } from './canonical.js';
import { loadRuntime, projectPath } from './config.js';
import { commitPayload, evaluateCycle } from './engine.js';
import { appendLedger } from './ledger.js';
import { collectDueSources } from './refresh.js';

const once = process.argv.includes('--once');
const intervalHours = Number(process.env.JARVIS_REFRESH_INTERVAL_HOURS || 24);
const stopFile = resolve(process.env.JARVIS_STOP_FILE || projectPath('STOP'));
const maximumSources = Number(process.env.JARVIS_MAX_SOURCES_PER_CYCLE || 5);

if (!Number.isFinite(intervalHours) || intervalHours < 1 || intervalHours > 168) {
  throw new Error('JARVIS_REFRESH_INTERVAL_HOURS must be between 1 and 168');
}
if (!Number.isInteger(maximumSources) || maximumSources < 1 || maximumSources > 20) {
  throw new Error('JARVIS_MAX_SOURCES_PER_CYCLE must be between 1 and 20');
}

function log(payload) {
  process.stdout.write(`${JSON.stringify({ timestamp: new Date().toISOString(), ...payload })}\n`);
}

async function runOnce() {
  if (existsSync(stopFile)) {
    log({ level: 'warn', event: 'stop_switch_active', stopFile });
    return { stopped: true };
  }
  const runtime = loadRuntime();
  const collected = await collectDueSources(runtime.registry, { maximumSources });
  if (collected.plan.totalDue === 0) {
    log({ level: 'info', event: 'refresh_not_due', nextCheckAt: collected.plan.nextCheckAt });
    return { noOp: true };
  }
  const now = new Date();
  const cycle = evaluateCycle({
    ...runtime,
    observations: collected.observations,
    now,
  });
  const key = `daemon:${now.toISOString().slice(0, 13)}:${cycle.cycleId.slice(-16)}`;
  const payload = {
    ...commitPayload(cycle),
    collectionFailures: collected.failures,
  };
  const result = appendLedger(runtime.ledgerPath, payload, {
    idempotencyKey: key,
    requestHash: sha256({ state: runtime.state, observations: collected.observations }),
    now,
  });
  log({
    level: collected.failures.length ? 'warn' : 'info',
    event: 'refresh_cycle_committed',
    appended: result.appended,
    observations: collected.observations.length,
    failures: collected.failures,
    ledgerHead: result.entry.hash,
  });
  return { result, cycle, collected };
}

await runOnce();
if (!once) {
  const timer = setInterval(() => {
    runOnce().catch((error) => log({ level: 'error', event: 'refresh_cycle_failed', code: error.code, message: error.message }));
  }, intervalHours * 3_600_000);
  timer.unref();
  process.stdin.resume();
}
