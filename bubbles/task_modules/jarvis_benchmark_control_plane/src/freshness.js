import { validateRegistry } from './validation.js';

const DAY_MS = 86_400_000;

export function sourceFreshness(source, now = new Date()) {
  const nowMs = now instanceof Date ? now.getTime() : Date.parse(now);
  const verifiedMs = Date.parse(source.verifiedAt);
  if (!Number.isFinite(nowMs) || !Number.isFinite(verifiedMs)) {
    return { status: 'UNKNOWN', ageDays: null, remainingDays: null };
  }
  const ageDays = Math.max(0, (nowMs - verifiedMs) / DAY_MS);
  const remainingDays = source.freshnessSlaDays - ageDays;
  const dueSoonWindow = Math.max(1, source.freshnessSlaDays * 0.2);
  const status = remainingDays < 0 ? 'STALE' : remainingDays <= dueSoonWindow ? 'DUE_SOON' : 'CURRENT';
  return {
    status,
    ageDays: Number(ageDays.toFixed(2)),
    remainingDays: Number(remainingDays.toFixed(2)),
    nextCheckAt: new Date(verifiedMs + source.freshnessSlaDays * DAY_MS).toISOString(),
  };
}

export function assessRegistry(registry, dimensions, now = new Date()) {
  validateRegistry(registry);
  const sources = registry.map((source) => ({ ...source, freshness: sourceFreshness(source, now) }));
  const counts = { CURRENT: 0, DUE_SOON: 0, STALE: 0, UNKNOWN: 0 };
  for (const source of sources) counts[source.freshness.status] += 1;
  const criticalSourceIssues = sources
    .filter((source) => source.critical && ['STALE', 'UNKNOWN'].includes(source.freshness.status))
    .map((source) => source.id);
  const missingCriticalDimensionCoverage = dimensions
    .filter((dimension) => dimension.critical)
    .filter((dimension) => !sources.some((source) =>
      source.scoreEligible !== false
      && ['CURRENT', 'DUE_SOON'].includes(source.freshness.status)
      && source.dimensions.includes(dimension.id)))
    .map((dimension) => dimension.id);
  return {
    evaluatedAt: (now instanceof Date ? now : new Date(now)).toISOString(),
    canConcludeCurrent: criticalSourceIssues.length === 0 && missingCriticalDimensionCoverage.length === 0,
    counts,
    criticalSourceIssues,
    missingCriticalDimensionCoverage,
    sources,
  };
}

export function planRefresh(registry, now = new Date(), maximumSources = 5) {
  validateRegistry(registry);
  const ranked = registry
    .map((source) => ({ sourceId: source.id, critical: source.critical, ...sourceFreshness(source, now) }))
    .filter((item) => item.status !== 'CURRENT')
    .sort((a, b) => {
      const statusRank = { STALE: 0, UNKNOWN: 1, DUE_SOON: 2 };
      return statusRank[a.status] - statusRank[b.status]
        || Number(b.critical) - Number(a.critical)
        || (a.remainingDays ?? -Infinity) - (b.remainingDays ?? -Infinity)
        || a.sourceId.localeCompare(b.sourceId);
    });
  const nextCheckAt = registry
    .map((source) => sourceFreshness(source, now).nextCheckAt)
    .filter(Boolean)
    .sort()[0] || null;
  return {
    generatedAt: (now instanceof Date ? now : new Date(now)).toISOString(),
    nextCheckAt,
    totalDue: ranked.length,
    selected: ranked.slice(0, maximumSources),
    deferred: Math.max(0, ranked.length - maximumSources),
  };
}
