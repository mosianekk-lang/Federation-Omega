export type HarvestMaturity =
  | "REUSE_VERIFIED"
  | "SOURCE_IMPLEMENTED"
  | "RUNTIME_GATED"
  | "PROVIDER_GATED";

export type PriorityBand = "P0" | "P1" | "P2" | "P3";
export type EffectClass = "READ" | "BOUNDED_WRITE" | "EXTERNAL_WRITE" | "PRIVILEGED";

export interface AnthropicHarvestFeature {
  id: string;
  pattern: string;
  fusePrimitive: string;
  owner: "FUSE_MOBILE" | "FEDERATION" | "AEGIS" | "CFBE" | "REALITY_LAB";
  priority: PriorityBand;
  maturity: HarvestMaturity;
  acceptance: string;
}

export interface ToolDescriptor {
  name: string;
  namespace: string;
  description: string;
  effect: EffectClass;
  deferredSchema?: string;
  inputExamples?: readonly string[];
  tags?: readonly string[];
}

export interface ToolDiscoveryResult {
  tool: ToolDescriptor;
  score: number;
  reasons: readonly string[];
}

export interface SkillDescriptor {
  name: string;
  description: string;
  bodyRef: string;
  resourceRefs?: readonly string[];
  tags?: readonly string[];
}

export interface SkillSelection {
  skill: SkillDescriptor;
  score: number;
  loadRefs: readonly string[];
}

export interface SessionEvent {
  id: string;
  kind: "PLAN" | "USER" | "MODEL" | "TOOL" | "CHECKPOINT" | "SUMMARY" | "OUTCOME";
  text: string;
  createdAt: string;
  pinned?: boolean;
}

export interface ContextScreenResult {
  safe: boolean;
  signals: readonly string[];
  sanitized: string;
}

export interface ActionRiskDecision {
  effect: EffectClass;
  autoAllow: boolean;
  requiresOwnerApproval: boolean;
  deny: boolean;
  reasons: readonly string[];
}

export interface ResearchShard {
  id: string;
  objective: string;
  tokenBudget: number;
  toolBudget: number;
}

export interface Checkpoint {
  missionId: string;
  eventCursor: string;
  artifactRefs: readonly string[];
  digest: string;
  createdAt: string;
}

export interface OutcomeEvaluation {
  passed: boolean;
  claimedState: string;
  observedState: string;
  reason: string;
}

export interface DeviceCapability {
  deviceId: string;
  kind: string;
  commands: readonly string[];
  safetyNotes: readonly string[];
  maxConcurrentActions: number;
  requiresOwnerPresence: boolean;
}

export const ANTHROPIC_CFBE_GENOME: readonly AnthropicHarvestFeature[] = [
  { id: "ANTH-001", pattern: "orchestrator-worker research fanout", fusePrimitive: "bounded parallel research shards", owner: "CFBE", priority: "P0", maturity: "SOURCE_IMPLEMENTED", acceptance: "independent shards with explicit token/tool budgets" },
  { id: "ANTH-002", pattern: "separate subagent context windows", fusePrimitive: "context-isolated worker lanes", owner: "FEDERATION", priority: "P0", maturity: "SOURCE_IMPLEMENTED", acceptance: "workers receive only task-scoped context" },
  { id: "ANTH-003", pattern: "citation verification stage", fusePrimitive: "evidence-linked synthesis pass", owner: "CFBE", priority: "P0", maturity: "RUNTIME_GATED", acceptance: "material claims map to source evidence" },
  { id: "ANTH-004", pattern: "research budget economics", fusePrimitive: "value-aware fanout governor", owner: "CFBE", priority: "P1", maturity: "SOURCE_IMPLEMENTED", acceptance: "fanout is bounded by task value and budget" },
  { id: "ANTH-005", pattern: "lead-agent plan persistence", fusePrimitive: "pinned plan event", owner: "FEDERATION", priority: "P0", maturity: "SOURCE_IMPLEMENTED", acceptance: "plan survives context compaction" },
  { id: "ANTH-006", pattern: "durable external session log", fusePrimitive: "append-only mission event cursor", owner: "FEDERATION", priority: "P0", maturity: "RUNTIME_GATED", acceptance: "resume from durable cursor after process loss" },
  { id: "ANTH-007", pattern: "selective event retrieval", fusePrimitive: "context slice compiler", owner: "FEDERATION", priority: "P0", maturity: "SOURCE_IMPLEMENTED", acceptance: "retrieve pinned plus recent high-signal events" },
  { id: "ANTH-008", pattern: "structured artifact handoff", fusePrimitive: "typed handoff envelope", owner: "FEDERATION", priority: "P0", maturity: "REUSE_VERIFIED", acceptance: "handoffs carry task, evidence, limits and output refs" },
  { id: "ANTH-009", pattern: "planner-generator-evaluator loop", fusePrimitive: "three-role build court", owner: "CFBE", priority: "P0", maturity: "REUSE_VERIFIED", acceptance: "evaluator can reject and request bounded repair" },
  { id: "ANTH-010", pattern: "automatic context compaction", fusePrimitive: "loss-minimizing context compiler", owner: "FEDERATION", priority: "P0", maturity: "SOURCE_IMPLEMENTED", acceptance: "pinned plans and recent critical events remain" },
  { id: "ANTH-011", pattern: "dynamic tool discovery", fusePrimitive: "query-ranked tool search", owner: "FUSE_MOBILE", priority: "P0", maturity: "SOURCE_IMPLEMENTED", acceptance: "small relevant tool set returned on demand" },
  { id: "ANTH-012", pattern: "deferred tool schemas", fusePrimitive: "lazy schema loading", owner: "FUSE_MOBILE", priority: "P0", maturity: "SOURCE_IMPLEMENTED", acceptance: "heavy schemas stay outside context until selected" },
  { id: "ANTH-013", pattern: "programmatic tool calling", fusePrimitive: "code-orchestrated tool composition", owner: "FEDERATION", priority: "P1", maturity: "RUNTIME_GATED", acceptance: "large intermediate results are filtered before model context" },
  { id: "ANTH-014", pattern: "MCP code execution", fusePrimitive: "MCP-as-code façade", owner: "FEDERATION", priority: "P1", maturity: "RUNTIME_GATED", acceptance: "tool definitions are loaded selectively" },
  { id: "ANTH-015", pattern: "agent-friendly tool namespaces", fusePrimitive: "service.resource.verb naming", owner: "FEDERATION", priority: "P1", maturity: "SOURCE_IMPLEMENTED", acceptance: "namespaces are non-overlapping and evaluable" },
  { id: "ANTH-016", pattern: "high-signal tool responses", fusePrimitive: "result envelope compactor", owner: "FEDERATION", priority: "P0", maturity: "SOURCE_IMPLEMENTED", acceptance: "tool results contain only decision-relevant context" },
  { id: "ANTH-017", pattern: "tool self-optimization with evals", fusePrimitive: "paired tool ergonomics court", owner: "CFBE", priority: "P1", maturity: "RUNTIME_GATED", acceptance: "tool changes require measured task improvement" },
  { id: "ANTH-018", pattern: "progressive Agent Skills disclosure", fusePrimitive: "metadata-first skill selection", owner: "FUSE_MOBILE", priority: "P0", maturity: "SOURCE_IMPLEMENTED", acceptance: "skill bodies/resources load only when selected" },
  { id: "ANTH-019", pattern: "skills with executable helpers", fusePrimitive: "skill script references", owner: "FEDERATION", priority: "P1", maturity: "RUNTIME_GATED", acceptance: "scripts execute only inside bounded runtime" },
  { id: "ANTH-020", pattern: "skill lifecycle improvement", fusePrimitive: "eval-gated skill evolution", owner: "CFBE", priority: "P1", maturity: "RUNTIME_GATED", acceptance: "self-edits remain challengers until eval promotion" },
  { id: "ANTH-021", pattern: "prompt-injection probe on tool outputs", fusePrimitive: "untrusted-context scanner", owner: "AEGIS", priority: "P0", maturity: "REUSE_VERIFIED", acceptance: "suspect instructions are labelled before model ingestion" },
  { id: "ANTH-022", pattern: "action transcript classifier", fusePrimitive: "pre-effect action risk gate", owner: "AEGIS", priority: "P0", maturity: "SOURCE_IMPLEMENTED", acceptance: "dangerous external effects require approval or denial" },
  { id: "ANTH-023", pattern: "fast-path then deep review", fusePrimitive: "two-stage effect screening", owner: "AEGIS", priority: "P0", maturity: "SOURCE_IMPLEMENTED", acceptance: "obviously safe reads avoid expensive review" },
  { id: "ANTH-024", pattern: "filesystem sandbox boundary", fusePrimitive: "path-scoped execution permit", owner: "AEGIS", priority: "P0", maturity: "REUSE_VERIFIED", acceptance: "agent cannot escape declared workspace" },
  { id: "ANTH-025", pattern: "network sandbox boundary", fusePrimitive: "egress allowlist permit", owner: "AEGIS", priority: "P0", maturity: "REUSE_VERIFIED", acceptance: "network access is explicit and destination-scoped" },
  { id: "ANTH-026", pattern: "subagent delegation and return gates", fusePrimitive: "handoff risk screen", owner: "AEGIS", priority: "P1", maturity: "SOURCE_IMPLEMENTED", acceptance: "delegations cannot widen effect authority" },
  { id: "ANTH-027", pattern: "blast-radius containment", fusePrimitive: "capability ceiling compiler", owner: "AEGIS", priority: "P0", maturity: "SOURCE_IMPLEMENTED", acceptance: "mission receives minimum capabilities required" },
  { id: "ANTH-028", pattern: "decouple reasoning brain from execution hands", fusePrimitive: "brain-hand runtime boundary", owner: "FEDERATION", priority: "P0", maturity: "RUNTIME_GATED", acceptance: "execution worker enforces policy independent of model" },
  { id: "ANTH-029", pattern: "model tier specialization", fusePrimitive: "risk-value-latency model lane", owner: "FEDERATION", priority: "P0", maturity: "SOURCE_IMPLEMENTED", acceptance: "cheap lane for low-risk volume and frontier lane for high-value work" },
  { id: "ANTH-030", pattern: "outcome-state evaluation", fusePrimitive: "claim-versus-environment verifier", owner: "CFBE", priority: "P0", maturity: "SOURCE_IMPLEMENTED", acceptance: "success is based on observed state, not agent prose" },
  { id: "ANTH-031", pattern: "infrastructure-noise-aware evals", fusePrimitive: "paired environment normalization", owner: "CFBE", priority: "P1", maturity: "RUNTIME_GATED", acceptance: "benchmark deltas exceed measured environment noise" },
  { id: "ANTH-032", pattern: "long-running checkpoints", fusePrimitive: "mission checkpoint digest", owner: "FEDERATION", priority: "P0", maturity: "SOURCE_IMPLEMENTED", acceptance: "resume state has cursor, artifacts and deterministic digest" },
  { id: "ANTH-033", pattern: "parallel shared-codebase agent teams", fusePrimitive: "bounded work partition and merge court", owner: "REALITY_LAB", priority: "P1", maturity: "RUNTIME_GATED", acceptance: "parallel workers have disjoint ownership and merge verification" },
  { id: "ANTH-034", pattern: "hardware capability descriptors", fusePrimitive: "device capability manifest", owner: "FUSE_MOBILE", priority: "P1", maturity: "SOURCE_IMPLEMENTED", acceptance: "discoverable commands, limits and safety notes" },
  { id: "ANTH-035", pattern: "safe physical-device commands", fusePrimitive: "device effect gate", owner: "AEGIS", priority: "P0", maturity: "SOURCE_IMPLEMENTED", acceptance: "physical writes default to owner-presence or explicit permit" },
  { id: "ANTH-036", pattern: "cross-device standardized control", fusePrimitive: "MCP-compatible device bridge", owner: "FEDERATION", priority: "P2", maturity: "PROVIDER_GATED", acceptance: "real device command/readback pair passes" },
  { id: "ANTH-037", pattern: "persistent-memory poisoning defense", fusePrimitive: "memory provenance and quarantine", owner: "AEGIS", priority: "P0", maturity: "RUNTIME_GATED", acceptance: "persistent entries retain origin/trust and can be excluded" },
  { id: "ANTH-038", pattern: "live inspection of untrusted tool returns", fusePrimitive: "pre-context inspection proxy", owner: "AEGIS", priority: "P0", maturity: "RUNTIME_GATED", acceptance: "network/tool responses are scanned before context entry" },
  { id: "ANTH-039", pattern: "model currentness and deprecation tracking", fusePrimitive: "provider model lifecycle watch", owner: "CFBE", priority: "P1", maturity: "RUNTIME_GATED", acceptance: "routing rejects retired models and warns before deadlines" },
  { id: "ANTH-040", pattern: "threat-intelligence feedback", fusePrimitive: "incident-to-eval compiler", owner: "AEGIS", priority: "P1", maturity: "RUNTIME_GATED", acceptance: "real incidents create regression cases before closure" },
  { id: "ANTH-041", pattern: "enterprise frontier safeguard profiles", fusePrimitive: "mission-specific risk profile", owner: "AEGIS", priority: "P1", maturity: "SOURCE_IMPLEMENTED", acceptance: "risk ceilings can vary by mission without weakening global invariants" },
  { id: "ANTH-042", pattern: "cost-aware parallel intelligence scaling", fusePrimitive: "fanout ROI governor", owner: "CFBE", priority: "P1", maturity: "SOURCE_IMPLEMENTED", acceptance: "extra workers require expected value above marginal cost" },
] as const;

const tokenise = (value: string): readonly string[] =>
  value
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((token) => token.length >= 2);

const scoreOverlap = (queryTokens: readonly string[], text: string): number => {
  if (queryTokens.length === 0) return 0;
  const haystack = new Set(tokenise(text));
  let hits = 0;
  for (const token of queryTokens) if (haystack.has(token)) hits += 1;
  return hits / queryTokens.length;
};

export function discoverDeferredTools(
  query: string,
  tools: readonly ToolDescriptor[],
  limit = 8,
): readonly ToolDiscoveryResult[] {
  const queryTokens = tokenise(query);
  return tools
    .map((tool): ToolDiscoveryResult => {
      const searchable = `${tool.namespace} ${tool.name} ${tool.description} ${(tool.tags ?? []).join(" ")}`;
      const lexical = scoreOverlap(queryTokens, searchable);
      const exactNamespace = query.toLowerCase().includes(tool.namespace.toLowerCase()) ? 0.25 : 0;
      const safeReadBias = tool.effect === "READ" ? 0.05 : 0;
      const score = lexical + exactNamespace + safeReadBias;
      const reasons: string[] = [];
      if (lexical > 0) reasons.push("semantic-token-overlap");
      if (exactNamespace > 0) reasons.push("namespace-match");
      if (safeReadBias > 0) reasons.push("least-effect-bias");
      return { tool, score, reasons };
    })
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score || a.tool.name.localeCompare(b.tool.name))
    .slice(0, Math.max(1, limit));
}

export function selectProgressiveSkills(
  task: string,
  skills: readonly SkillDescriptor[],
  limit = 4,
): readonly SkillSelection[] {
  const taskTokens = tokenise(task);
  return skills
    .map((skill): SkillSelection => {
      const score = scoreOverlap(taskTokens, `${skill.name} ${skill.description} ${(skill.tags ?? []).join(" ")}`);
      const loadRefs = score > 0 ? [skill.bodyRef] : [];
      return { skill, score, loadRefs };
    })
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score || a.skill.name.localeCompare(b.skill.name))
    .slice(0, Math.max(1, limit));
}

const INJECTION_RULES: readonly [string, RegExp][] = [
  ["instruction-override", /\b(ignore|disregard|override)\b.{0,48}\b(system|developer|previous|policy|instruction)\b/i],
  ["secret-request", /\b(reveal|print|expose|upload|send)\b.{0,48}\b(secret|token|credential|password|api[-_ ]?key)\b/i],
  ["authority-escalation", /\b(disable|bypass|skip)\b.{0,48}\b(approval|guardrail|permission|policy|sandbox)\b/i],
];

export function screenUntrustedContext(text: string): ContextScreenResult {
  const signals = INJECTION_RULES.filter(([, rule]) => rule.test(text)).map(([signal]) => signal);
  const safe = signals.length === 0;
  const sanitized = safe ? text : `[UNTRUSTED_CONTEXT:${signals.join(",")}]\n${text}`;
  return { safe, signals, sanitized };
}

export function classifyActionRisk(effect: EffectClass, description: string): ActionRiskDecision {
  const lower = description.toLowerCase();
  const destructiveSignal = /\b(delete|drop|destroy|revoke|publish|send|charge|purchase|transfer|deploy|release)\b/.test(lower);
  const secretSignal = /\b(secret|credential|password|token|api[-_ ]?key)\b/.test(lower);
  const reasons: string[] = [];

  if (effect === "READ" && !secretSignal) {
    return { effect, autoAllow: true, requiresOwnerApproval: false, deny: false, reasons: ["read-only-fast-path"] };
  }

  if (effect === "BOUNDED_WRITE" && !destructiveSignal && !secretSignal) {
    return { effect, autoAllow: true, requiresOwnerApproval: false, deny: false, reasons: ["bounded-write-within-declared-scope"] };
  }

  if (destructiveSignal) reasons.push("destructive-or-public-effect");
  if (secretSignal) reasons.push("sensitive-material-involved");
  if (effect === "EXTERNAL_WRITE") reasons.push("external-side-effect");
  if (effect === "PRIVILEGED") reasons.push("privileged-operation");

  const deny = effect === "PRIVILEGED" && secretSignal;
  return {
    effect,
    autoAllow: false,
    requiresOwnerApproval: !deny,
    deny,
    reasons: reasons.length > 0 ? reasons : ["manual-review-required"],
  };
}

export function compactSessionEvents(
  events: readonly SessionEvent[],
  maxCharacters = 12000,
): readonly SessionEvent[] {
  const pinned = events.filter((event) => event.pinned || event.kind === "PLAN");
  const selected = new Map<string, SessionEvent>();
  let used = 0;

  for (const event of pinned) {
    if (used + event.text.length > maxCharacters) break;
    selected.set(event.id, event);
    used += event.text.length;
  }

  for (const event of [...events].reverse()) {
    if (selected.has(event.id)) continue;
    if (used + event.text.length > maxCharacters) continue;
    selected.set(event.id, event);
    used += event.text.length;
  }

  return events.filter((event) => selected.has(event.id));
}

export function buildResearchFanout(
  objective: string,
  facets: readonly string[],
  totalTokenBudget = 24000,
  maxWorkers = 6,
): readonly ResearchShard[] {
  const unique = [...new Set(facets.map((facet) => facet.trim()).filter(Boolean))].slice(0, Math.max(1, maxWorkers));
  if (unique.length === 0) return [];
  const perWorker = Math.max(1000, Math.floor(totalTokenBudget / unique.length));
  const toolBudget = Math.max(2, Math.min(12, Math.floor(perWorker / 2000)));
  return unique.map((facet, index) => ({
    id: `research-${String(index + 1).padStart(2, "0")}`,
    objective: `${objective} :: ${facet}`,
    tokenBudget: perWorker,
    toolBudget,
  }));
}

export function chooseModelLane(input: {
  value: number;
  risk: number;
  latencySensitivity: number;
}): "FAST" | "BALANCED" | "FRONTIER" {
  const value = Math.max(0, Math.min(1, input.value));
  const risk = Math.max(0, Math.min(1, input.risk));
  const latency = Math.max(0, Math.min(1, input.latencySensitivity));
  const frontierScore = value * 0.5 + risk * 0.4 - latency * 0.1;
  if (frontierScore >= 0.65) return "FRONTIER";
  if (frontierScore >= 0.35) return "BALANCED";
  return "FAST";
}

const fnv1a = (value: string): string => {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
};

export function createMissionCheckpoint(
  missionId: string,
  events: readonly SessionEvent[],
  artifactRefs: readonly string[],
  createdAt = new Date().toISOString(),
): Checkpoint {
  const lastEvent = events.length > 0 ? events[events.length - 1] : undefined;
  const eventCursor = lastEvent?.id ?? "START";
  const digestMaterial = [missionId, eventCursor, ...artifactRefs.slice().sort()].join("|");
  return { missionId, eventCursor, artifactRefs: [...artifactRefs], digest: fnv1a(digestMaterial), createdAt };
}

export function evaluateObservedOutcome(claimedState: string, observedState: string): OutcomeEvaluation {
  const normalize = (value: string) => value.trim().replace(/\s+/g, " ").toLowerCase();
  const passed = normalize(claimedState) === normalize(observedState);
  return {
    passed,
    claimedState,
    observedState,
    reason: passed ? "claim-matches-observed-state" : "claim-observation-mismatch",
  };
}

export function compileDeviceCapability(input: {
  deviceId: string;
  kind: string;
  commands: readonly string[];
  safetyNotes?: readonly string[];
  maxConcurrentActions?: number;
  requiresOwnerPresence?: boolean;
}): DeviceCapability {
  const commands = [...new Set(input.commands.map((command) => command.trim()).filter(Boolean))].sort();
  return {
    deviceId: input.deviceId,
    kind: input.kind,
    commands,
    safetyNotes: [...(input.safetyNotes ?? [])],
    maxConcurrentActions: Math.max(1, input.maxConcurrentActions ?? 1),
    requiresOwnerPresence: input.requiresOwnerPresence ?? true,
  };
}

export function capBlastRadius(
  requested: readonly string[],
  allowed: readonly string[],
): readonly string[] {
  const allowedSet = new Set(allowed);
  return [...new Set(requested.filter((capability) => allowedSet.has(capability)))].sort();
}

export function gateSubagentHandoff(input: {
  parentCapabilities: readonly string[];
  requestedCapabilities: readonly string[];
  task: string;
}): { allowedCapabilities: readonly string[]; blockedCapabilities: readonly string[]; task: string } {
  const allowedCapabilities = capBlastRadius(input.requestedCapabilities, input.parentCapabilities);
  const allowedSet = new Set(allowedCapabilities);
  const blockedCapabilities = [...new Set(input.requestedCapabilities.filter((capability) => !allowedSet.has(capability)))].sort();
  return { allowedCapabilities, blockedCapabilities, task: input.task };
}

export function harvestDisposition(): Readonly<Record<HarvestMaturity, number>> {
  return ANTHROPIC_CFBE_GENOME.reduce<Record<HarvestMaturity, number>>(
    (counts, feature) => {
      counts[feature.maturity] += 1;
      return counts;
    },
    { REUSE_VERIFIED: 0, SOURCE_IMPLEMENTED: 0, RUNTIME_GATED: 0, PROVIDER_GATED: 0 },
  );
}
