import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { lastCommittedState } from './ledger.js';

export const PROJECT_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

export function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

export function projectPath(...parts) {
  return resolve(PROJECT_ROOT, ...parts);
}

export function loadRuntime({
  registryPath = projectPath('data', 'sources.json'),
  dimensionsPath = projectPath('data', 'dimensions.json'),
  statePath = projectPath('examples', 'jarvis-state.sample.json'),
  ledgerPath = projectPath('data', 'learning-ledger.jsonl'),
} = {}) {
  const baseRegistry = readJson(registryPath);
  const restored = lastCommittedState(ledgerPath, baseRegistry);
  return {
    registry: restored.registry,
    previousEvaluation: restored.evaluation,
    dimensions: readJson(dimensionsPath),
    state: readJson(statePath),
    ledgerPath,
    ledger: restored.ledger,
  };
}
