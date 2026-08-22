import { fail } from './errors.js';

export const TRUTH_WEIGHTS = Object.freeze({
  DESIGNED: 0.15,
  IMPLEMENTED: 0.35,
  TESTED: 0.55,
  REGISTERED: 0.65,
  AUTHORIZED: 0.72,
  READY: 0.82,
  DEPLOYED: 0.92,
  PROVEN: 1,
});

const MUS_KEYS = ['opportunity', 'dependencyUnlock', 'impact', 'riskReduction', 'authorityFit', 'verifiability', 'costExposure', 'latency'];

function boundedFive(value, key) {
  if (!Number.isFinite(value) || value < 0 || value > 5) {
    fail('INVALID_INPUT', `${key} must be between 0 and 5`);
  }
  return value;
}

export function missionUtilityScore(input) {
  for (const key of MUS_KEYS) boundedFive(input[key], key);
  return Number((
    5 * input.opportunity
    + 4 * input.dependencyUnlock
    + 3 * input.impact
    + 3 * input.riskReduction
    + 3 * input.authorityFit
    + 2 * input.verifiability
    - 2 * input.costExposure
    - 2 * input.latency
  ).toFixed(2));
}

function readiness(overallScore, rows, registryCurrent) {
  if (!registryCurrent) return 'DIAGNOSTIC_ONLY';
  const critical = rows.filter((row) => row.critical);
  if (overallScore >= 95 && critical.every((row) => row.truthState === 'PROVEN')) return 'FRONTIER_PROVEN';
  if (overallScore >= 85 && critical.every((row) => ['DEPLOYED', 'PROVEN'].includes(row.truthState))) return 'PRODUCTION_PROVEN';
  if (overallScore >= 70 && critical.every((row) => row.effectiveScore >= 60)) return 'OPERATIONAL_READY';
  if (overallScore >= 50) return 'FOUNDATIONAL';
  return 'INITIAL';
}

export function evaluateBenchmark(dimensions, state, registryAssessment) {
  const stateById = new Map(state.dimensions.map((entry) => [entry.id, entry]));
  let weightedActual = 0;
  let weightedTarget = 0;
  const rows = dimensions.map((dimension) => {
    const entry = stateById.get(dimension.id) || {
      id: dimension.id,
      maturity: 0,
      truthState: 'DESIGNED',
      evidenceRefs: [],
    };
    const proofWeight = TRUTH_WEIGHTS[entry.truthState];
    const effectiveScore = Number((entry.maturity * proofWeight).toFixed(2));
    const gap = Number(Math.max(0, dimension.targetScore - effectiveScore).toFixed(2));
    weightedActual += effectiveScore * dimension.weight;
    weightedTarget += dimension.targetScore * dimension.weight;
    return {
      id: dimension.id,
      name: dimension.name,
      critical: dimension.critical,
      weight: dimension.weight,
      targetScore: dimension.targetScore,
      assertedMaturity: entry.maturity,
      truthState: entry.truthState,
      proofWeight,
      effectiveScore,
      gap,
      evidenceRefs: entry.evidenceRefs,
    };
  });
  const overallScore = Number((weightedActual / dimensions.reduce((sum, item) => sum + item.weight, 0)).toFixed(2));
  const targetScore = Number((weightedTarget / dimensions.reduce((sum, item) => sum + item.weight, 0)).toFixed(2));
  return {
    systemId: state.systemId,
    evaluatedAt: registryAssessment.evaluatedAt,
    conclusionState: registryAssessment.canConcludeCurrent ? 'CURRENT_PUBLIC_EVIDENCE' : 'DIAGNOSTIC_ONLY_STALE_EVIDENCE',
    readiness: readiness(overallScore, rows, registryAssessment.canConcludeCurrent),
    overallScore,
    targetScore,
    totalGap: Number((targetScore - overallScore).toFixed(2)),
    privateInternalParityClaimed: false,
    dimensions: rows,
  };
}

export function selectOpportunities(evaluation, dimensions, maximum = 3) {
  const configuration = new Map(dimensions.map((dimension) => [dimension.id, dimension]));
  return evaluation.dimensions
    .map((row) => {
      const dimension = configuration.get(row.id);
      const opportunity = Math.min(5, Number((row.gap / 20).toFixed(2)));
      const factors = { opportunity, ...dimension.opportunityFactors };
      return {
        id: `CLOSE_${row.id.toUpperCase()}_GAP`,
        dimensionId: row.id,
        title: dimension.opportunityTitle,
        gap: row.gap,
        missionUtilityScore: missionUtilityScore(factors),
        factors,
        authorityClass: dimension.authorityClass,
        proofNeed: dimension.proofNeed,
        effectful: false,
        decision: evaluation.conclusionState === 'CURRENT_PUBLIC_EVIDENCE'
          ? 'RECOMMENDED_CURRENT_EVIDENCE'
          : 'DIAGNOSTIC_ONLY',
      };
    })
    .filter((item) => item.missionUtilityScore > 0)
    .sort((a, b) => b.missionUtilityScore - a.missionUtilityScore || b.gap - a.gap || a.id.localeCompare(b.id))
    .slice(0, maximum);
}

export function benchmarkDelta(previous, current) {
  if (!previous) return { state: 'BASELINE_CREATED', overallDelta: null, dimensions: [] };
  const prior = new Map(previous.dimensions.map((row) => [row.id, row]));
  return {
    state: 'COMPARABLE',
    overallDelta: Number((current.overallScore - previous.overallScore).toFixed(2)),
    dimensions: current.dimensions.map((row) => ({
      id: row.id,
      scoreDelta: Number((row.effectiveScore - (prior.get(row.id)?.effectiveScore || 0)).toFixed(2)),
      gapDelta: Number((row.gap - (prior.get(row.id)?.gap || 0)).toFixed(2)),
    })),
  };
}
