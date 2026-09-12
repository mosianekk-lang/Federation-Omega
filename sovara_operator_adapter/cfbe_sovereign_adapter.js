/* CFBE-Ω sovereign portable adapter — JavaScript / Apps Script compatible.
 *
 * No provider SDK, browser API, Node-only API or secret access is required.
 * The same pure function can execute in Apps Script V8, Node, Cloud Run JS, or
 * another standards-compatible JavaScript runtime. Provider transports and
 * credential resolution remain outside this module.
 */

const CFBE_SOVEREIGN_ENVELOPE_CONTRACT = "CFBE_OMEGA_SOVEREIGN_ENVELOPE_V1";
const CFBE_AUTHORITY = {
  A0_READ: 0,
  A1_INTERNAL: 1,
  PROVIDER_ACTION: 2,
  CONSEQUENTIAL: 3,
};

function cfbeAuthority(value) {
  if (Number.isInteger(value)) return value;
  const key = String(value || "A0_READ").trim().toUpperCase();
  if (!Object.prototype.hasOwnProperty.call(CFBE_AUTHORITY, key)) {
    throw new Error("unsupported authority " + key);
  }
  return CFBE_AUTHORITY[key];
}

function cfbeIsPresent(adapter) {
  return [
    "CONNECTED",
    "CONNECTED_VERIFIED",
    "PRESENT_VERIFIED",
    "ACTIVE",
    "OPERATIONAL_SCOPED",
  ].includes(String(adapter.presence_state || ""));
}

function cfbeIsCurrent(adapter) {
  return ["CURRENT", "FRESH"].includes(String(adapter.freshness_state || ""));
}

function cfbeProviderLive(adapter) {
  return [
    "PROVIDER_LIVE",
    "PROVIDER_VERIFIED",
    "PROVIDER_VERIFIED_SCOPED",
    "CI_AND_SOURCE_LIVE",
    "OPERATIONAL_SCOPED",
  ].includes(String(adapter.provider_execution_state || ""));
}

function cfbeEligible(mission, adapter) {
  const excluded = new Set((mission.excluded_surface_classes || []).map(String));
  if (excluded.has(String(adapter.surface_class))) return false;
  if (!cfbeIsCurrent(adapter) || !cfbeIsPresent(adapter)) return false;
  if (!(adapter.capabilities || []).map(String).includes(String(mission.capability))) {
    return false;
  }
  const requiredAuthority = cfbeAuthority(mission.authority_required || "A0_READ");
  if (cfbeAuthority(adapter.authority_ceiling || "A0_READ") < requiredAuthority) {
    return false;
  }
  if (Boolean(mission.provider_execution_required) && !cfbeProviderLive(adapter)) {
    return false;
  }
  if (Boolean(mission.reversible_required) && !Boolean(adapter.reversible)) {
    return false;
  }
  if (mission.included_cost_only !== false && !["INCLUDED", "ZERO"].includes(String(adapter.cost_class || "UNKNOWN"))) {
    return false;
  }
  return true;
}

function cfbeRouteScore(mission, adapter) {
  let score = 0;
  if (cfbeProviderLive(adapter)) score += 40;
  if (Boolean(adapter.semantic_readback)) score += 25;
  if (["ZERO", "INCLUDED"].includes(String(adapter.cost_class))) score += 15;
  if (Boolean(adapter.reversible)) score += 10;
  score += Math.min(
    cfbeAuthority(adapter.authority_ceiling || "A0_READ"),
    cfbeAuthority(mission.authority_required || "A0_READ")
  ) * 5;
  return score;
}

function cfbeRankRoutes(mission, adapters) {
  return (adapters || [])
    .filter((adapter) => cfbeEligible(mission, adapter))
    .map((adapter) => ({
      adapter_id: String(adapter.adapter_id),
      surface_class: String(adapter.surface_class),
      rank_score: cfbeRouteScore(mission, adapter),
      proof_ref: String(adapter.proof_ref || ""),
      truth_boundary: String(adapter.truth_boundary || ""),
    }))
    .sort((left, right) => {
      if (left.rank_score !== right.rank_score) return right.rank_score - left.rank_score;
      return left.adapter_id.localeCompare(right.adapter_id);
    });
}

function cfbeExecuteEnvelope(payload) {
  if (!payload || payload.contract !== CFBE_SOVEREIGN_ENVELOPE_CONTRACT) {
    throw new Error("unsupported or missing sovereign envelope contract");
  }
  const mission = payload.mission || {};
  if (!mission.objective_id || !mission.capability) {
    throw new Error("objective_id and capability are required");
  }
  const operation = String(payload.operation || "RANK_ROUTES").toUpperCase();
  let routes = cfbeRankRoutes(mission, payload.adapters || []);
  const response = {
    contract: CFBE_SOVEREIGN_ENVELOPE_CONTRACT,
    version: "1.0.0-js",
    objective_id: String(mission.objective_id),
    operation: operation,
    ranked_routes: routes,
    selected_route: null,
    truth_boundary:
      "Envelope output is a deterministic route decision, not proof that a provider effect occurred. Provider execution requires action-specific semantic readback.",
  };

  if (operation === "RANK_ROUTES") {
    response.selected_route = routes.length ? routes[0] : null;
  } else if (operation === "FAILOVER") {
    const failed = new Set((payload.failed_adapter_ids || []).map(String));
    routes = routes.filter((route) => !failed.has(route.adapter_id));
    if (!routes.length) throw new Error("authorised route-space exhausted after failover exclusions");
    response.ranked_routes = routes;
    response.selected_route = routes[0];
    response.failed_adapter_ids = Array.from(failed).sort();
  } else {
    throw new Error("unsupported envelope operation " + operation);
  }
  return response;
}

// Apps Script V8 exposes the global function directly. Node-based CI may import it.
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    CFBE_SOVEREIGN_ENVELOPE_CONTRACT,
    cfbeAuthority,
    cfbeRankRoutes,
    cfbeExecuteEnvelope,
  };
}
