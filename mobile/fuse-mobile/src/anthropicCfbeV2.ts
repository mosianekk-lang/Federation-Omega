export type AnthropicV2Maturity =
  | "REUSE_VERIFIED"
  | "SOURCE_IMPLEMENTED"
  | "RUNTIME_GATED"
  | "PROVIDER_GATED";

export interface AnthropicV2Gene {
  id: string;
  pattern: string;
  fusePrimitive: string;
  maturity: AnthropicV2Maturity;
  proofTarget: string;
}

export const ANTHROPIC_CFBE_V2_GENOME: readonly AnthropicV2Gene[] = [
  { id: "ANTH-043", pattern: "advisor-executor separation", fusePrimitive: "REASON.ADVISOR_DELEGATION", maturity: "SOURCE_IMPLEMENTED", proofTarget: "advisor use is bounded by marginal value and cost" },
  { id: "ANTH-044", pattern: "adaptive reasoning effort", fusePrimitive: "REASON.EFFORT_CONTROL", maturity: "SOURCE_IMPLEMENTED", proofTarget: "effort rises only with difficulty, uncertainty or failure cost" },
  { id: "ANTH-045", pattern: "tool execution locus separation", fusePrimitive: "TOOL.EXECUTION_LOCUS", maturity: "SOURCE_IMPLEMENTED", proofTarget: "client, hosted and self-hosted execution are explicit choices" },
  { id: "ANTH-046", pattern: "browser-vs-computer tool routing", fusePrimitive: "EXEC.BROWSER_COMPUTER_ROUTER", maturity: "SOURCE_IMPLEMENTED", proofTarget: "page-aware tasks avoid full-desktop authority" },
  { id: "ANTH-047", pattern: "context-pressure composition", fusePrimitive: "CONTEXT.PRESSURE_CONTROLLER", maturity: "SOURCE_IMPLEMENTED", proofTarget: "context controls match the actual source of pressure" },
  { id: "ANTH-048", pattern: "memory trust zones", fusePrimitive: "CONTEXT.MEMORY_TRUST_ZONES", maturity: "SOURCE_IMPLEMENTED", proofTarget: "untrusted sessions cannot write shared durable memory" },
  { id: "ANTH-049", pattern: "immutable memory versions", fusePrimitive: "MEMORY.VERSIONED_PROVENANCE", maturity: "SOURCE_IMPLEMENTED", proofTarget: "every durable memory write has immutable provenance" },
  { id: "ANTH-050", pattern: "versioned reusable agent definitions", fusePrimitive: "AGENT.RESOURCE_VERSIONING", maturity: "SOURCE_IMPLEMENTED", proofTarget: "optimistic concurrency blocks silent agent-definition overwrite" },
  { id: "ANTH-051", pattern: "bounded outcome revision loops", fusePrimitive: "AGENT.OUTCOME_EVALUATION", maturity: "SOURCE_IMPLEMENTED", proofTarget: "evaluator can revise, satisfy, fail or hit a hard iteration ceiling" },
  { id: "ANTH-052", pattern: "self-hosted sensitive execution", fusePrimitive: "EXEC.SELF_HOSTED_SANDBOX", maturity: "SOURCE_IMPLEMENTED", proofTarget: "sensitive/internal-network work defaults to owner-controlled execution" },
  { id: "ANTH-053", pattern: "brain-hand decoupling", fusePrimitive: "EXEC.BRAIN_HAND_INTERFACE", maturity: "RUNTIME_GATED", proofTarget: "stateless reasoning can reconnect to replaceable execution hands" },
  { id: "ANTH-054", pattern: "lazy hand provisioning", fusePrimitive: "EXEC.LAZY_HAND_PROVISIONING", maturity: "RUNTIME_GATED", proofTarget: "sessions pay startup cost only for execution environments they use" },
  { id: "ANTH-055", pattern: "many-hands routing", fusePrimitive: "EXEC.MULTI_HAND_ROUTER", maturity: "RUNTIME_GATED", proofTarget: "one reasoning session routes safely across multiple execution environments" },
  { id: "ANTH-056", pattern: "auto-mode two-stage action screening", fusePrimitive: "SEC.TWO_STAGE_ACTION_GATE", maturity: "SOURCE_IMPLEMENTED", proofTarget: "cheap filter clears obvious safe actions; flagged actions receive deeper review" },
  { id: "ANTH-057", pattern: "reasoning-blind approval classifier", fusePrimitive: "SEC.INTENT_ACTION_VIEW", maturity: "SOURCE_IMPLEMENTED", proofTarget: "approval decision uses user intent and requested action, not persuasive model prose" },
  { id: "ANTH-058", pattern: "recursive subagent safety pipeline", fusePrimitive: "SEC.RECURSIVE_HANDOFF_GATE", maturity: "SOURCE_IMPLEMENTED", proofTarget: "delegation cannot widen parent authority and returned context is re-screened" },
  { id: "ANTH-059", pattern: "containment-first autonomy", fusePrimitive: "SEC.CONTAINMENT_BEFORE_BEHAVIOR", maturity: "REUSE_VERIFIED", proofTarget: "hard environment bounds remain authoritative when probabilistic safeguards miss" },
  { id: "ANTH-060", pattern: "credential non-presence in sandbox", fusePrimitive: "SEC.SECRET_NON_PRESENCE", maturity: "RUNTIME_GATED", proofTarget: "sandbox cannot exfiltrate credentials that never enter it" },
  { id: "ANTH-061", pattern: "egress provenance enforcement", fusePrimitive: "SEC.EGRESS_PROVENANCE_PROXY", maturity: "RUNTIME_GATED", proofTarget: "permitted destinations reject foreign or attacker-supplied credentials" },
  { id: "ANTH-062", pattern: "tool-return live inspection", fusePrimitive: "SEC.PRE_CONTEXT_INSPECTION", maturity: "RUNTIME_GATED", proofTarget: "untrusted network/tool returns are inspected before model context ingestion" },
  { id: "ANTH-063", pattern: "research suitability gate", fusePrimitive: "CFBE.MULTI_AGENT_FITNESS", maturity: "SOURCE_IMPLEMENTED", proofTarget: "parallel research runs only when task value and parallelizability justify cost" },
  { id: "ANTH-064", pattern: "research rubric evaluation", fusePrimitive: "CFBE.RESEARCH_RUBRIC", maturity: "SOURCE_IMPLEMENTED", proofTarget: "accuracy, citation, completeness, source quality and tool efficiency are scored separately" },
  { id: "ANTH-065", pattern: "separate citation verification", fusePrimitive: "CFBE.CITATION_AUDITOR", maturity: "SOURCE_IMPLEMENTED", proofTarget: "material claims are independently mapped to supporting sources" },
  { id: "ANTH-066", pattern: "tool-result token budgeting", fusePrimitive: "TOOL.RESULT_BUDGET", maturity: "SOURCE_IMPLEMENTED", proofTarget: "large tool results are summarized or externalized before context entry" },
  { id: "ANTH-067", pattern: "harness staleness challenge", fusePrimitive: "AGENT.HARNESS_SIMPLIFIER", maturity: "SOURCE_IMPLEMENTED", proofTarget: "every harness component must continue to earn its complexity" },
  { id: "ANTH-068", pattern: "infrastructure-noise calibration", fusePrimitive: "CFBE.INFRA_NOISE_COURT", maturity: "SOURCE_IMPLEMENTED", proofTarget: "benchmark deltas are compared with repeated-run environment variance" },
  { id: "ANTH-069", pattern: "parallel shared-code ownership", fusePrimitive: "REALITYLAB.SHARD_OWNERSHIP", maturity: "SOURCE_IMPLEMENTED", proofTarget: "parallel workers receive disjoint ownership before merge court" },
  { id: "ANTH-070", pattern: "device read/write primitive standard", fusePrimitive: "DEVICE.MHS_COMMAND_MODEL", maturity: "SOURCE_IMPLEMENTED", proofTarget: "device actions use discoverable read/write commands with explicit safety metadata" },
  { id: "ANTH-071", pattern: "hardware fault recovery policy", fusePrimitive: "DEVICE.RECOVERY_POLICY", maturity: "SOURCE_IMPLEMENTED", proofTarget: "fault recovery is bounded, observable and stops on unsafe state" },
  { id: "ANTH-072", pattern: "incident-to-eval feedback", fusePrimitive: "SEC.INCIDENT_REGRESSION_COMPILER", maturity: "SOURCE_IMPLEMENTED", proofTarget: "real failures become permanent regression cases before closure" },
] as const;

export type EffortLevel = "LOW" | "MEDIUM" | "HIGH" | "XHIGH" | "MAX";
export type ExecutionLocus = "CLIENT" | "HOSTED" | "SELF_HOSTED";
export type ToolsetKind = "TYPED" | "BROWSER" | "COMPUTER";

const clamp01 = (value: number): number => Math.max(0, Math.min(1, value));

export function chooseAdvisorDelegation(input: {
  complexity: number;
  uncertainty: number;
  failureCost: number;
  executorQuality: number;
  costPressure?: number;
}): { useAdvisor: boolean; maxUses: number; score: number } {
  const score =
    0.35 * clamp01(input.complexity) +
    0.3 * clamp01(input.uncertainty) +
    0.25 * clamp01(input.failureCost) +
    0.1 * (1 - clamp01(input.executorQuality)) -
    0.2 * clamp01(input.costPressure ?? 0);
  if (score >= 0.72) return { useAdvisor: true, maxUses: 2, score };
  if (score >= 0.55) return { useAdvisor: true, maxUses: 1, score };
  return { useAdvisor: false, maxUses: 0, score };
}

export function chooseAdaptiveEffort(input: {
  difficulty: number;
  uncertainty: number;
  failureCost: number;
  longHorizon: boolean;
  costPressure?: number;
}): EffortLevel {
  let score =
    0.42 * clamp01(input.difficulty) +
    0.28 * clamp01(input.uncertainty) +
    0.3 * clamp01(input.failureCost) -
    0.22 * clamp01(input.costPressure ?? 0);
  if (input.longHorizon) score += 0.12;
  if (score >= 0.88) return "MAX";
  if (score >= 0.72) return "XHIGH";
  if (score >= 0.5) return "HIGH";
  if (score >= 0.28) return "MEDIUM";
  return "LOW";
}

export function chooseExecutionLocus(input: {
  sensitiveData: boolean;
  internalNetworkRequired: boolean;
  localDeviceRequired: boolean;
}): ExecutionLocus {
  if (input.localDeviceRequired) return "CLIENT";
  if (input.sensitiveData || input.internalNetworkRequired) return "SELF_HOSTED";
  return "HOSTED";
}

export function chooseToolset(input: {
  pageAware: boolean;
  fullDesktopRequired: boolean;
}): ToolsetKind {
  if (input.fullDesktopRequired) return "COMPUTER";
  if (input.pageAware) return "BROWSER";
  return "TYPED";
}

export interface ContextPressureInput {
  toolCount: number;
  toolResultTokens: number;
  conversationTokens: number;
  stableToolset: boolean;
  repetitiveFanout: boolean;
  memoryAvailable: boolean;
}

export function planContextPressure(input: ContextPressureInput): readonly string[] {
  const actions: string[] = [];
  if (input.stableToolset && input.toolCount > 0) actions.push("PROMPT_CACHE");
  if (input.toolCount >= 20) actions.push("TOOL_SEARCH");
  if (input.repetitiveFanout) actions.push("PROGRAMMATIC_TOOL_CALLING");
  if (input.toolResultTokens >= 20000) actions.push("CLEAR_STALE_TOOL_RESULTS");
  if (input.conversationTokens >= 100000) {
    if (input.memoryAvailable) actions.push("MEMORY_OFFLOAD_BEFORE_COMPACTION");
    actions.push("CONTEXT_COMPACTION");
  }
  return [...new Set(actions)];
}

export type MemoryAccess = "NONE" | "READ_ONLY" | "READ_WRITE";

export function planMemoryAccess(input: {
  sharedReference: boolean;
  untrustedInputPresent: boolean;
  writeNeeded: boolean;
}): { access: MemoryAccess; reason: string } {
  if (input.sharedReference) return { access: "READ_ONLY", reason: "shared-reference-immutable" };
  if (input.untrustedInputPresent) return { access: "READ_ONLY", reason: "persistent-memory-poisoning-risk" };
  if (input.writeNeeded) return { access: "READ_WRITE", reason: "trusted-durable-learning-required" };
  return { access: "READ_ONLY", reason: "no-write-requirement" };
}

export interface MemoryRecord {
  path: string;
  version: number;
  content: string;
  createdBy: string;
  sourceRefs: readonly string[];
  trust: "TRUSTED" | "UNTRUSTED" | "QUARANTINED";
}

export class VersionedMemoryStore {
  private readonly items = new Map<string, readonly MemoryRecord[]>();

  write(input: Omit<MemoryRecord, "version">): MemoryRecord {
    if (!input.path || input.path.startsWith("../") || input.path.includes("/../")) {
      throw new Error("invalid-memory-path");
    }
    if (input.trust !== "TRUSTED") throw new Error("memory-write-requires-trusted-input");
    const prior = this.items.get(input.path) ?? [];
    const record: MemoryRecord = { ...input, version: prior.length + 1 };
    this.items.set(input.path, [...prior, record]);
    return record;
  }

  latest(path: string): MemoryRecord | undefined {
    const history = this.items.get(path) ?? [];
    return history.length > 0 ? history[history.length - 1] : undefined;
  }

  history(path: string): readonly MemoryRecord[] {
    return this.items.get(path) ?? [];
  }
}

export interface AgentDefinition {
  agentId: string;
  version: number;
  model: string;
  toolsDigest: string;
  skillsDigest: string;
  policyDigest: string;
}

export class AgentDefinitionStore {
  private readonly definitions = new Map<string, AgentDefinition>();

  create(input: Omit<AgentDefinition, "version">): AgentDefinition {
    if (this.definitions.has(input.agentId)) throw new Error("agent-definition-exists");
    const created: AgentDefinition = { ...input, version: 1 };
    this.definitions.set(input.agentId, created);
    return created;
  }

  update(
    agentId: string,
    expectedVersion: number,
    patch: Partial<Omit<AgentDefinition, "agentId" | "version">>,
  ): AgentDefinition {
    const current = this.definitions.get(agentId);
    if (!current) throw new Error("agent-definition-missing");
    if (current.version !== expectedVersion) throw new Error("agent-definition-version-conflict");
    const next: AgentDefinition = { ...current, ...patch, version: current.version + 1 };
    this.definitions.set(agentId, next);
    return next;
  }
}

export type OutcomeState =
  | "PENDING"
  | "RUNNING"
  | "NEEDS_REVISION"
  | "SATISFIED"
  | "MAX_ITERATIONS_REACHED"
  | "FAILED";

export function evaluateOutcomeIteration(input: {
  currentIteration: number;
  maxIterations: number;
  satisfied: boolean;
  recoverable: boolean;
}): { state: OutcomeState; nextIteration: number } {
  if (input.maxIterations < 1) throw new Error("max-iterations-must-be-positive");
  if (input.satisfied) return { state: "SATISFIED", nextIteration: input.currentIteration };
  if (!input.recoverable) return { state: "FAILED", nextIteration: input.currentIteration };
  const nextIteration = input.currentIteration + 1;
  if (nextIteration >= input.maxIterations) return { state: "MAX_ITERATIONS_REACHED", nextIteration };
  return { state: "NEEDS_REVISION", nextIteration };
}

export interface SandboxProfile {
  mode: "EPHEMERAL_HOSTED" | "LOCAL_SANDBOX" | "SELF_HOSTED_ISOLATED";
  filesystem: "READ_ONLY" | "BOUNDED_RW" | "EPHEMERAL_RW";
  network: "NONE" | "ALLOWLIST" | "PROXY_ENFORCED";
  secrets: "ABSENT" | "BROKERED_SHORT_LIVED";
}

export function chooseContainmentProfile(input: {
  sensitiveData: boolean;
  internalNetworkRequired: boolean;
  localFilesRequired: boolean;
  writeRequired: boolean;
}): SandboxProfile {
  if (input.sensitiveData || input.internalNetworkRequired) {
    return {
      mode: "SELF_HOSTED_ISOLATED",
      filesystem: input.writeRequired ? "BOUNDED_RW" : "READ_ONLY",
      network: "PROXY_ENFORCED",
      secrets: "BROKERED_SHORT_LIVED",
    };
  }
  if (input.localFilesRequired) {
    return {
      mode: "LOCAL_SANDBOX",
      filesystem: input.writeRequired ? "BOUNDED_RW" : "READ_ONLY",
      network: "ALLOWLIST",
      secrets: "ABSENT",
    };
  }
  return {
    mode: "EPHEMERAL_HOSTED",
    filesystem: input.writeRequired ? "EPHEMERAL_RW" : "READ_ONLY",
    network: "ALLOWLIST",
    secrets: "ABSENT",
  };
}

const HIGH_RISK_ACTION = /\b(delete|drop|destroy|force[- ]?push|publish|send|transfer|charge|purchase|deploy|release|production|prod\b|revoke|rotate secret|export credential)\b/i;
const LOW_RISK_ACTION = /^(read|list|show|inspect|search|find|get|status|diff|test|lint|typecheck)\b/i;

export function twoStageActionGate(input: {
  userIntent: string;
  action: string;
  withinSandbox: boolean;
}): { decision: "ALLOW" | "DEEP_REVIEW" | "BLOCK"; reason: string } {
  if (!input.withinSandbox) return { decision: "BLOCK", reason: "outside-containment-boundary" };
  if (HIGH_RISK_ACTION.test(input.action)) return { decision: "DEEP_REVIEW", reason: "high-risk-action-signal" };
  if (LOW_RISK_ACTION.test(input.action)) return { decision: "ALLOW", reason: "safe-fast-path" };
  const intentTokens = new Set(input.userIntent.toLowerCase().split(/\W+/).filter(Boolean));
  const actionTokens = input.action.toLowerCase().split(/\W+/).filter(Boolean);
  const aligned = actionTokens.some((token) => intentTokens.has(token));
  return aligned
    ? { decision: "ALLOW", reason: "intent-aligned-bounded-action" }
    : { decision: "DEEP_REVIEW", reason: "intent-action-uncertainty" };
}

export function researchSuitability(input: {
  taskValue: number;
  parallelizability: number;
  contextBreadth: number;
  dependencyCoupling: number;
  costPressure: number;
}): { useMultiAgent: boolean; score: number } {
  const score =
    0.3 * clamp01(input.taskValue) +
    0.3 * clamp01(input.parallelizability) +
    0.25 * clamp01(input.contextBreadth) -
    0.25 * clamp01(input.dependencyCoupling) -
    0.15 * clamp01(input.costPressure);
  return { useMultiAgent: score >= 0.45, score };
}

export interface ResearchRubricScores {
  factualAccuracy: number;
  citationAccuracy: number;
  completeness: number;
  sourceQuality: number;
  toolEfficiency: number;
}

export function scoreResearchRubric(scores: ResearchRubricScores): number {
  return (
    0.3 * clamp01(scores.factualAccuracy) +
    0.25 * clamp01(scores.citationAccuracy) +
    0.2 * clamp01(scores.completeness) +
    0.15 * clamp01(scores.sourceQuality) +
    0.1 * clamp01(scores.toolEfficiency)
  );
}

export function planCitationAudit(input: {
  materialClaims: readonly string[];
  sourceRefs: readonly string[];
}): readonly { claim: string; requiredSourceCount: number; availableSourceRefs: readonly string[] }[] {
  const availableSourceRefs = [...new Set(input.sourceRefs)].filter(Boolean);
  return input.materialClaims.map((claim) => ({
    claim,
    requiredSourceCount: 1,
    availableSourceRefs,
  }));
}

export function budgetToolResult(input: {
  rawCharacters: number;
  contextCharactersRemaining: number;
  materiality: number;
}): "INLINE" | "SUMMARIZE" | "EXTERNALIZE" {
  const remaining = Math.max(1, input.contextCharactersRemaining);
  const ratio = Math.max(0, input.rawCharacters) / remaining;
  if (ratio <= 0.12) return "INLINE";
  if (ratio <= 0.45 && clamp01(input.materiality) >= 0.65) return "SUMMARIZE";
  return "EXTERNALIZE";
}

export function harnessSimplificationCandidates(
  components: readonly { name: string; measuredBenefit: number; maintenanceCost: number }[],
): readonly string[] {
  return components
    .filter((component) => clamp01(component.measuredBenefit) < clamp01(component.maintenanceCost))
    .map((component) => component.name)
    .sort();
}

export function benchmarkNoiseDecision(input: {
  challengerDelta: number;
  repeatedRunStandardDeviation: number;
  minimumPracticalDelta: number;
}): { promotable: boolean; reason: string } {
  const noiseFloor = Math.max(0, input.repeatedRunStandardDeviation) * 2;
  const required = Math.max(noiseFloor, Math.max(0, input.minimumPracticalDelta));
  return input.challengerDelta >= required
    ? { promotable: true, reason: "delta-clears-noise-and-practicality-floor" }
    : { promotable: false, reason: "delta-not-distinguishable-from-noise-or-too-small" };
}

export interface CodeShard {
  id: string;
  ownedPaths: readonly string[];
  acceptanceTests: readonly string[];
}

export function validateParallelCodeShards(shards: readonly CodeShard[]): { valid: boolean; conflicts: readonly string[] } {
  const ownerByPath = new Map<string, string>();
  const conflicts = new Set<string>();
  for (const shard of shards) {
    for (const path of shard.ownedPaths) {
      const owner = ownerByPath.get(path);
      if (owner && owner !== shard.id) conflicts.add(path);
      ownerByPath.set(path, shard.id);
    }
  }
  return { valid: conflicts.size === 0, conflicts: [...conflicts].sort() };
}

export type DeviceCommandKind = "READ" | "WRITE";

export interface DeviceCommand {
  name: string;
  kind: DeviceCommandKind;
  safetyNotes: readonly string[];
  requiresOwnerPresence: boolean;
  maxAttempts: number;
}

export function compileDeviceCommand(input: {
  name: string;
  kind: DeviceCommandKind;
  safetyNotes?: readonly string[];
  reversible?: boolean;
}): DeviceCommand {
  const write = input.kind === "WRITE";
  return {
    name: input.name.trim(),
    kind: input.kind,
    safetyNotes: [...(input.safetyNotes ?? [])],
    requiresOwnerPresence: write,
    maxAttempts: write && !input.reversible ? 1 : 3,
  };
}

export function deviceRecoveryDecision(input: {
  faultCount: number;
  safetyStateKnown: boolean;
  lastCommandReversible: boolean;
}): "RETRY" | "READ_STATE" | "STOP_AND_ESCALATE" {
  if (!input.safetyStateKnown) return "READ_STATE";
  if (!input.lastCommandReversible) return "STOP_AND_ESCALATE";
  if (input.faultCount >= 2) return "STOP_AND_ESCALATE";
  return "RETRY";
}

export interface RegressionCase {
  id: string;
  incidentRef: string;
  invariant: string;
  replayRequired: boolean;
  promotionBlocking: boolean;
}

export function incidentToRegressionCase(input: {
  incidentRef: string;
  invariant: string;
}): RegressionCase {
  const normalized = `${input.incidentRef}|${input.invariant}`.toLowerCase();
  let hash = 2166136261;
  for (let index = 0; index < normalized.length; index += 1) {
    hash ^= normalized.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return {
    id: `REG-${(hash >>> 0).toString(16).padStart(8, "0")}`,
    incidentRef: input.incidentRef,
    invariant: input.invariant,
    replayRequired: true,
    promotionBlocking: true,
  };
}

export function anthropicV2Disposition(): Readonly<Record<AnthropicV2Maturity, number>> {
  return ANTHROPIC_CFBE_V2_GENOME.reduce<Record<AnthropicV2Maturity, number>>(
    (counts, gene) => {
      counts[gene.maturity] += 1;
      return counts;
    },
    { REUSE_VERIFIED: 0, SOURCE_IMPLEMENTED: 0, RUNTIME_GATED: 0, PROVIDER_GATED: 0 },
  );
}
