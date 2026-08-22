import { sha256 } from './canonical.js';
import { assessRegistry, planRefresh } from './freshness.js';
import { applyObservations } from './refresh.js';
import { benchmarkDelta, evaluateBenchmark, selectOpportunities } from './scoring.js';
import { validateDimensions, validateRegistry, validateState } from './validation.js';

export function evaluateCycle({ registry, dimensions, state, now = new Date(), previousEvaluation = null, observations = [] }) {
  validateRegistry(registry);
  validateDimensions(dimensions);
  validateState(state, dimensions);
  const reconciliation = applyObservations(registry, observations);
  const registryAssessment = assessRegistry(reconciliation.updatedRegistry, dimensions, now);
  const evaluation = evaluateBenchmark(dimensions, state, registryAssessment);
  const opportunities = selectOpportunities(evaluation, dimensions);
  const delta = benchmarkDelta(previousEvaluation, evaluation);
  return {
    schemaVersion: '1.0.0',
    cycleId: sha256({ state, observations, evaluatedAt: registryAssessment.evaluatedAt }),
    evaluatedAt: registryAssessment.evaluatedAt,
    registryAssessment,
    refreshPlan: planRefresh(reconciliation.updatedRegistry, now),
    sourceChanges: reconciliation.changes,
    updatedRegistry: reconciliation.updatedRegistry,
    evaluation,
    opportunities,
    delta,
    effectfulActionTaken: false,
  };
}

export function commitPayload(cycle) {
  return {
    type: 'BENCHMARK_CYCLE_COMMIT',
    schemaVersion: cycle.schemaVersion,
    cycleId: cycle.cycleId,
    evaluatedAt: cycle.evaluatedAt,
    registryHash: sha256(cycle.updatedRegistry),
    updatedRegistry: cycle.updatedRegistry,
    registryAssessment: {
      canConcludeCurrent: cycle.registryAssessment.canConcludeCurrent,
      counts: cycle.registryAssessment.counts,
      criticalSourceIssues: cycle.registryAssessment.criticalSourceIssues,
      missingCriticalDimensionCoverage: cycle.registryAssessment.missingCriticalDimensionCoverage,
    },
    evaluation: cycle.evaluation,
    opportunities: cycle.opportunities,
    delta: cycle.delta,
    sourceChanges: cycle.sourceChanges,
  };
}
