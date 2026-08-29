"use strict";

const INPUT_ROUTE_MODES = new Set(["ACTIVE", "PASSIVE"]);
const DERIVED_ROUTE_HEALTH = new Set(["HEALTHY", "DEGRADED", "OPEN"]);

function assertInputRouteMode(mode) {
  if (!INPUT_ROUTE_MODES.has(mode)) throw new TypeError("route mode must be ACTIVE or PASSIVE");
  return mode;
}

function deriveRouteHealth(metrics = {}, limits = {}) {
  const errorCount = Number(metrics.errorCount || 0);
  const saturation = Number(metrics.saturation || 0);
  const latencyMs = Number(metrics.latencyMs || 0);
  const openErrorCount = Number(limits.openErrorCount === undefined ? 3 : limits.openErrorCount);
  const maximumSaturation = Number(limits.maximumSaturation === undefined ? 0.9 : limits.maximumSaturation);
  const maximumLatencyMs = Number(limits.maximumLatencyMs === undefined ? 2000 : limits.maximumLatencyMs);
  if (![errorCount, saturation, latencyMs].every(Number.isFinite) || errorCount < 0 || saturation < 0 || latencyMs < 0) {
    throw new TypeError("route metrics must be finite non-negative numbers");
  }
  if (errorCount >= openErrorCount) return "OPEN";
  if (errorCount > 0 || saturation >= maximumSaturation || latencyMs > maximumLatencyMs) return "DEGRADED";
  return "HEALTHY";
}

function selectPrimary(routes, limits) {
  if (!Array.isArray(routes) || routes.length === 0) return {state: "NO_ROUTE"};
  const evaluated = routes.map((route, index) => ({
    key: String(route.key || `route-${index}`),
    mode: assertInputRouteMode(route.mode),
    health: deriveRouteHealth(route.metrics, limits),
    index
  }));
  const rank = {HEALTHY: 0, DEGRADED: 1, OPEN: 2};
  evaluated.sort((a, b) => {
    const healthDifference = rank[a.health] - rank[b.health];
    if (healthDifference) return healthDifference;
    const modeDifference = Number(b.mode === "ACTIVE") - Number(a.mode === "ACTIVE");
    return modeDifference || a.index - b.index;
  });
  const selected = evaluated[0];
  if (selected.health === "OPEN") return {state: "NO_HEALTHY_ROUTE", selectedHealth: "OPEN"};
  return {state: "ROUTE_SELECTED", key: selected.key, selectedMode: selected.mode, selectedHealth: selected.health};
}

module.exports = {INPUT_ROUTE_MODES, DERIVED_ROUTE_HEALTH, assertInputRouteMode, deriveRouteHealth, selectPrimary};
