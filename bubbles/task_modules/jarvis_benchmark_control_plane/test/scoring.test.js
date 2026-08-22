import assert from 'node:assert/strict';
import test from 'node:test';
import { projectPath, readJson } from '../src/config.js';
import { evaluateCycle } from '../src/engine.js';
import { assessRegistry } from '../src/freshness.js';
import { missionUtilityScore } from '../src/scoring.js';

const registry = readJson(projectPath('data', 'sources.json'));
const dimensions = readJson(projectPath('data', 'dimensions.json'));
const state = readJson(projectPath('examples', 'jarvis-state.sample.json'));
const now = new Date('2026-08-22T12:00:00.000Z');

test('Mission Utility Score implements the published deterministic formula', () => {
  assert.equal(missionUtilityScore({
    opportunity: 5,
    dependencyUnlock: 5,
    impact: 5,
    riskReduction: 5,
    authorityFit: 5,
    verifiability: 5,
    costExposure: 0,
    latency: 0,
  }), 100);
});

test('truth-state proof weighting prevents maturity assertions from becoming proof', () => {
  const cycle = evaluateCycle({ registry, dimensions, state, now });
  const row = cycle.evaluation.dimensions.find((item) => item.id === 'mission_strategy');
  assert.equal(row.assertedMaturity, 80);
  assert.equal(row.truthState, 'TESTED');
  assert.equal(row.effectiveScore, 44);
  assert.ok(cycle.evaluation.overallScore < 50);
  assert.equal(cycle.evaluation.readiness, 'INITIAL');
});

test('opportunity selection is deterministic and bounded to three', () => {
  const first = evaluateCycle({ registry, dimensions, state, now });
  const second = evaluateCycle({ registry, dimensions, state, now });
  assert.deepEqual(first.opportunities, second.opportunities);
  assert.equal(first.opportunities.length, 3);
  assert.equal(first.opportunities[0].dimensionId, 'knowledge_learning');
  assert.ok(first.opportunities.every((item) => item.effectful === false));
});

test('stale critical evidence fails closed to diagnostic-only conclusions', () => {
  const stale = registry.map((source) => ({ ...source, verifiedAt: '2025-01-01T00:00:00.000Z' }));
  const assessment = assessRegistry(stale, dimensions, now);
  const cycle = evaluateCycle({ registry: stale, dimensions, state, now });
  assert.equal(assessment.canConcludeCurrent, false);
  assert.equal(cycle.evaluation.conclusionState, 'DIAGNOSTIC_ONLY_STALE_EVIDENCE');
  assert.equal(cycle.evaluation.readiness, 'DIAGNOSTIC_ONLY');
  assert.ok(cycle.opportunities.every((item) => item.decision === 'DIAGNOSTIC_ONLY'));
});

test('missing state dimensions score as unproven rather than disappearing', () => {
  const reduced = { ...state, dimensions: state.dimensions.slice(0, 2) };
  const cycle = evaluateCycle({ registry, dimensions, state: reduced, now });
  assert.equal(cycle.evaluation.dimensions.length, dimensions.length);
  assert.equal(cycle.evaluation.dimensions.find((item) => item.id === 'reliability_resilience').effectiveScore, 0);
});
