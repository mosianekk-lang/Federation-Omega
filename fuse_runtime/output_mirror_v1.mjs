export const DEFAULT_OUTPUT_MIRROR_QUESTION =
  'Did I give the best and most powerful solution available to me as ChatGPT / AI assistant for representing OpenAI and what the user actually asked for?';

export function assessOutputMirror(prompt, result, meta = {}, policy = {}) {
  const question = policy.question || DEFAULT_OUTPUT_MIRROR_QUESTION;
  if (policy.enabled !== true) {
    return { schema: 'FUSE_OUTPUT_MIRROR_V1', enabled: false, question, state: 'DISABLED', release_allowed: true, issues: [] };
  }
  const r = result && typeof result === 'object' ? result : {};
  const issues = [];
  const objective = String(r.objective || '').trim();
  if (!objective) issues.push('USER_INTENT_OBJECTIVE_MISSING');
  if (!r.completion_state) issues.push('COMPLETION_STATE_MISSING');
  const tasks = Array.isArray(r.tasks) ? r.tasks : [];
  if (!tasks.length && !r.next_action) issues.push('NO_EXECUTION_OR_NEXT_ACTION');

  const hardBoundary =
    (r.completion_state === 'HELD_WITH_EXACT_REASON' || r.completion_state === 'PARTIAL_VERIFIED_CONTINUING') &&
    Boolean(r.reason || r.fallback_reason) && Boolean(r.next_action);
  const degraded = r.route === 'LOCAL_FALLBACK' || r.completion_state === 'PLANNED_LOCAL_FALLBACK';
  if (degraded && !hardBoundary) issues.push('DEGRADED_ROUTE_WITHOUT_HARD_BOUNDARY');

  const powerRequest = /(best|ultimate|max(?:imum)?|strongest|powerful|complete|do all|finish|audit|build|harvest|repair|investigate|deploy)/i.test(String(prompt || ''));
  const challenged =
    Boolean(r.tournament) ||
    (Array.isArray(r.challengers) && r.challengers.length > 0) ||
    (Array.isArray(r.acceptance_tests) && r.acceptance_tests.length > 0) ||
    String(meta.depth || '').toUpperCase() === 'DEEP' ||
    r.reasoning_effort === 'xhigh';
  if (powerRequest && !challenged && !hardBoundary) issues.push('POWER_REQUEST_WITHOUT_DEEP_OR_CHALLENGE_PASS');

  const release = issues.length === 0;
  return {
    schema: 'FUSE_OUTPUT_MIRROR_V1',
    enabled: true,
    version: String(policy.version || '1.1.0'),
    question,
    state: release ? (hardBoundary ? 'PASS_BEST_AVAILABLE_WITH_HARD_BOUNDARY' : 'PASS_BEST_AVAILABLE_RESULT') : 'FAIL_RECOMPILE_OUTPUT',
    release_allowed: release,
    issues
  };
}

export function deterministicStrengthen(prompt, result, meta = {}, helpers = {}) {
  const current = result && typeof result === 'object' ? { ...result } : {};
  const mission = helpers.compileMissionGraph(prompt, { max_surfaces: meta.max_surfaces || 8 });
  const tournament = helpers.compileTournamentPacket(prompt, mission.portfolio);
  return {
    ...current,
    objective: current.objective || String(prompt || ''),
    tasks: Array.isArray(current.tasks) && current.tasks.length
      ? current.tasks
      : mission.steps.filter(x => x.id !== 'S0').map(x => x.id + ' ' + x.kind + ': ' + x.surfaces.join(', ')),
    artifacts: Array.isArray(current.artifacts) ? current.artifacts : ['FUSE_COMPILED_MISSION_GRAPH_V1', 'FUSE_TOURNAMENT_PACKET_V1'],
    next_action: current.next_action || 'Execute the highest-ranked qualified route and verify the frozen acceptance tests.',
    completion_state: current.completion_state || 'PLANNED_MIRROR_STRENGTHENED',
    expert_context: current.expert_context || helpers.compileExpertContext(prompt),
    surface_portfolio: current.surface_portfolio || mission.portfolio,
    mission_graph: current.mission_graph || mission,
    tournament,
    challengers: tournament.candidates.map(c => c.candidate_id + ':' + c.surface),
    acceptance_tests: tournament.frozen_acceptance,
    mirror_strengthening: 'DETERMINISTIC_CHALLENGE_TOURNAMENT'
  };
}

export function heldReceipt(prompt, assessment, cycles = 0) {
  return {
    schema: 'FUSE_SOVEREIGN_LOCAL_RESULT_V1',
    objective: String(prompt || ''),
    route: 'OUTPUT_MIRROR_HOLD',
    tasks: [],
    artifacts: [],
    next_action: 'Continue through the strongest qualified route before owner delivery',
    completion_state: 'HELD_WITH_EXACT_REASON',
    reason: 'OUTPUT_MIRROR_RECOMPILE_REQUIRED',
    output_release_allowed: false,
    output_mirror: { ...assessment, recompile_cycles: cycles }
  };
}
