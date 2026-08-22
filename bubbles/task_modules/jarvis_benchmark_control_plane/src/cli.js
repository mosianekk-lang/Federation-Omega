#!/usr/bin/env node
import { resolve } from 'node:path';
import { sha256 } from './canonical.js';
import { loadRuntime, projectPath, readJson } from './config.js';
import { commitPayload, evaluateCycle } from './engine.js';
import { planRefresh } from './freshness.js';
import { appendLedger, verifyLedger } from './ledger.js';
import { validateDimensions, validateRegistry, validateState } from './validation.js';

function option(args, name, fallback = null) {
  const index = args.indexOf(name);
  return index === -1 ? fallback : args[index + 1];
}

function requiredOption(args, name) {
  const value = option(args, name);
  if (!value) throw Object.assign(new Error(`${name} is required`), { code: 'INVALID_INPUT' });
  return value;
}

function inputState(args, runtime) {
  const path = option(args, '--input');
  return path ? readJson(resolve(path)) : runtime.state;
}

function output(value) {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

function help() {
  return {
    commands: {
      validate: 'Validate registry, dimensions, state, ledger and a full dry-run cycle.',
      evaluate: 'Evaluate a state file: evaluate [--input path].',
      opportunities: 'Rank the next three opportunities: opportunities [--input path].',
      'refresh-plan': 'List due or stale authoritative sources.',
      'cycle-commit': 'Commit an observation/evaluation cycle: --input path --idempotency-key key [--observations path].',
      'ledger-verify': 'Verify the complete hash chain.',
    },
  };
}

async function main() {
  const [command = 'help', ...args] = process.argv.slice(2);
  const ledgerPath = resolve(option(args, '--ledger', projectPath('data', 'learning-ledger.jsonl')));
  const runtime = loadRuntime({ ledgerPath });
  if (command === 'help' || command === '--help' || command === '-h') return output(help());
  if (command === 'ledger-verify') return output(verifyLedger(ledgerPath));
  if (command === 'refresh-plan') return output(planRefresh(runtime.registry));
  const state = inputState(args, runtime);
  if (command === 'validate') {
    validateRegistry(runtime.registry);
    validateDimensions(runtime.dimensions);
    validateState(state, runtime.dimensions);
    const cycle = evaluateCycle({ ...runtime, state });
    return output({ valid: true, ledger: verifyLedger(ledgerPath), cycleId: cycle.cycleId, readiness: cycle.evaluation.readiness });
  }
  if (command === 'evaluate' || command === 'opportunities') {
    const cycle = evaluateCycle({ ...runtime, state });
    return output(command === 'evaluate' ? cycle : {
      conclusionState: cycle.evaluation.conclusionState,
      opportunities: cycle.opportunities,
    });
  }
  if (command === 'cycle-commit') {
    const observationsPath = option(args, '--observations');
    const observations = observationsPath ? readJson(resolve(observationsPath)) : [];
    const idempotencyKey = requiredOption(args, '--idempotency-key');
    const cycle = evaluateCycle({ ...runtime, state, observations });
    const result = appendLedger(ledgerPath, commitPayload(cycle), {
      idempotencyKey,
      requestHash: sha256({ state, observations }),
    });
    return output({
      appended: result.appended,
      duplicate: result.duplicate,
      sequence: result.entry.sequence,
      ledgerHead: result.entry.hash,
      cycle,
    });
  }
  throw Object.assign(new Error(`unknown command: ${command}`), { code: 'INVALID_INPUT' });
}

main().catch((error) => {
  process.stderr.write(`${JSON.stringify({ error: { code: error.code || 'INTERNAL_ERROR', message: error.message } })}\n`);
  process.exitCode = 1;
});
