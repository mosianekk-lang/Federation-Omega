export type AnthropicV4Maturity =
  | "REUSE_VERIFIED"
  | "SOURCE_IMPLEMENTED"
  | "RUNTIME_GATED"
  | "PROVIDER_GATED";

export interface AnthropicV4Gene {
  id: string;
  pattern: string;
  fusePrimitive: string;
  maturity: AnthropicV4Maturity;
  proofTarget: string;
}

/**
 * ANTH-101..128 extend the provider-neutral Anthropic CFBE genome with
 * long-horizon coding, checkpointing, subagent formation, containment,
 * dynamic tool use, success/failure learning and proof-gated recursive
 * improvement. These are FUSE source primitives, not claims about provider
 * internals or production deployment.
 */
export const ANTHROPIC_CFBE_V4_GENOME: readonly AnthropicV4Gene[] = [
  { id: "ANTH-101", pattern: "checkpoint tree before mutation", fusePrimitive: "EXEC.CHECKPOINT_TREE", maturity: "SOURCE_IMPLEMENTED", proofTarget: "every mutable sequence records a restorable predecessor before change" },
  { id: "ANTH-102", pattern: "lifecycle hooks around agent actions", fusePrimitive: "AGENT.HOOK_LIFECYCLE", maturity: "SOURCE_IMPLEMENTED", proofTarget: "preflight and postflight checks run deterministically around bounded actions" },
  { id: "ANTH-103", pattern: "specialist subagent formation", fusePrimitive: "AGENT.SPECIALIST_CELL", maturity: "SOURCE_IMPLEMENTED", proofTarget: "independent roles receive minimal scoped context and explicit deliverables" },
  { id: "ANTH-104", pattern: "leased background task state", fusePrimitive: "AGENT.BACKGROUND_LEASE", maturity: "RUNTIME_GATED", proofTarget: "long jobs expose lease, heartbeat, checkpoint and expiry semantics" },
  { id: "ANTH-105", pattern: "brain-hand decoupling", fusePrimitive: "EXEC.BRAIN_HAND_DECOUPLING", maturity: "SOURCE_IMPLEMENTED", proofTarget: "reasoning state can transfer between bounded execution hands without authority drift" },
  { id: "ANTH-106", pattern: "on-demand tool discovery", fusePrimitive: "TOOLS.DYNAMIC_DISCOVERY", maturity: "SOURCE_IMPLEMENTED", proofTarget: "only task-relevant tool schemas enter active context" },
  { id: "ANTH-107", pattern: "code-mediated MCP batching", fusePrimitive: "TOOLS.MCP_CODE_ROUTER", maturity: "SOURCE_IMPLEMENTED", proofTarget: "high-volume connector work can be compiled into bounded code paths with smaller context cost" },
  { id: "ANTH-108", pattern: "portable agent skill package", fusePrimitive: "SKILL.PORTABLE_PACKAGE", maturity: "SOURCE_IMPLEMENTED", proofTarget: "procedural expertise has explicit inputs, outputs, dependencies and acceptance tests" },
  { id: "ANTH-109", pattern: "quantified blast-radius budget", fusePrimitive: "SEC.BLAST_RADIUS_BUDGET", maturity: "SOURCE_IMPLEMENTED", proofTarget: "capability scales only inside an explicit consequence envelope" },
  { id: "ANTH-110", pattern: "successful-run pattern mining", fusePrimitive: "LEARN.SUCCESS_PATTERN_MINER", maturity: "SOURCE_IMPLEMENTED", proofTarget: "success generates a reusable invariant plus a harder challenger rather than terminating learning" },
  { id: "ANTH-111", pattern: "failure-to-innovation trigger", fusePrimitive: "LEARN.FAILURE_INNOVATION_TRIGGER", maturity: "SOURCE_IMPLEMENTED", proofTarget: "failure generates reproduction, root-cause, repair and regression work packages" },
  { id: "ANTH-112", pattern: "dual outcome learning trigger", fusePrimitive: "LEARN.OUTCOME_DUAL_TRIGGER", maturity: "SOURCE_IMPLEMENTED", proofTarget: "success, partial, blocked and failure outcomes all emit bounded improvement sequences" },
  { id: "ANTH-113", pattern: "counterfactual challenger generation", fusePrimitive: "CFBE.COUNTERFACTUAL_CHALLENGER", maturity: "SOURCE_IMPLEMENTED", proofTarget: "candidate improvements face cases designed to falsify the learned rule" },
  { id: "ANTH-114", pattern: "automatic regression inheritance", fusePrimitive: "TEST.REGRESSION_INHERITANCE", maturity: "SOURCE_IMPLEMENTED", proofTarget: "every repaired failure produces a persistent regression oracle" },
  { id: "ANTH-115", pattern: "agent-assisted tool self-optimization", fusePrimitive: "TOOLS.SELF_OPTIMIZATION_COURT", maturity: "SOURCE_IMPLEMENTED", proofTarget: "tool changes must improve measured task outcomes under a frozen eval set" },
  { id: "ANTH-116", pattern: "stale harness assumption reaping", fusePrimitive: "AGENT.HARNESS_ASSUMPTION_REAPER", maturity: "SOURCE_IMPLEMENTED", proofTarget: "obsolete scaffolding is removed only when a no-regression court proves it unnecessary" },
  { id: "ANTH-117", pattern: "model-lane challenger race", fusePrimitive: "MODEL.CHALLENGER_RACE", maturity: "PROVIDER_GATED", proofTarget: "model/provider lanes compete under normalized quality, latency, cost and safety conditions" },
  { id: "ANTH-118", pattern: "parallel code shard reconciliation", fusePrimitive: "CODE.PARALLEL_SHARD_RECONCILE", maturity: "RUNTIME_GATED", proofTarget: "parallel edits prove non-overlap or deterministic reconciliation before integration" },
  { id: "ANTH-119", pattern: "evidence delta ledger", fusePrimitive: "PROOF.DELTA_LEDGER", maturity: "SOURCE_IMPLEMENTED", proofTarget: "each cycle records claims, observations, changed evidence and unresolved gaps" },
  { id: "ANTH-120", pattern: "bounded experiment budget", fusePrimitive: "CFBE.EXPERIMENT_BUDGET", maturity: "SOURCE_IMPLEMENTED", proofTarget: "candidate fanout is capped by time, cost, risk and concurrency ceilings" },
  { id: "ANTH-121", pattern: "novelty and duplication filter", fusePrimitive: "CFBE.NOVELTY_FILTER", maturity: "SOURCE_IMPLEMENTED", proofTarget: "new candidates must differ materially from existing attempts or justify deliberate replication" },
  { id: "ANTH-122", pattern: "generalization court", fusePrimitive: "CFBE.GENERALIZATION_COURT", maturity: "SOURCE_IMPLEMENTED", proofTarget: "a local win must survive holdout and adversarial cases before reuse" },
  { id: "ANTH-123", pattern: "rollback synthesis", fusePrimitive: "EXEC.ROLLBACK_SYNTHESIS", maturity: "SOURCE_IMPLEMENTED", proofTarget: "every promotable mutation carries an executable rollback recipe and readback target" },
  { id: "ANTH-124", pattern: "compatible cross-surface learning diffusion", fusePrimitive: "LEARN.COMPATIBILITY_DIFFUSION", maturity: "RUNTIME_GATED", proofTarget: "proven learning transfers only after receiver compatibility and local-effect proof" },
  { id: "ANTH-125", pattern: "provenance-safe capability reuse", fusePrimitive: "LEARN.PROVENANCE_REUSE_GATE", maturity: "SOURCE_IMPLEMENTED", proofTarget: "reused capabilities retain source lineage, license/authority constraints and proof state" },
  { id: "ANTH-126", pattern: "owner burden minimization with risk floor", fusePrimitive: "UX.OWNER_BURDEN_OPTIMIZER", maturity: "SOURCE_IMPLEMENTED", proofTarget: "automation reduces redundant approvals without weakening consequential-action gates" },
  { id: "ANTH-127", pattern: "model-agnostic hardware-standard bridge", fusePrimitive: "DEVICE.HARDWARE_STANDARD_BRIDGE", maturity: "PROVIDER_GATED", proofTarget: "device control remains typed, bounded and interoperable across supported standard protocols" },
  { id: "ANTH-128", pattern: "recursive improvement flywheel", fusePrimitive: "LEARN.RECURSIVE_IMPROVEMENT_FLYWHEEL", maturity: "SOURCE_IMPLEMENTED", proofTarget: "every observed outcome produces a measurable candidate, court, disposition and retained learning artifact" },
] as const;

export type OutcomeKind = "SUCCESS" | "PARTIAL" | "FAILURE" | "BLOCKED";

export interface OutcomeObservation {
  outcomeId: string;
  kind: OutcomeKind;
  objective: string;
  expectedState: string;
  observedState: string;
  evidenceRefs: readonly string[];
  failureClass?: string;
  successfulTechnique?: string;
  latencyMs?: number;
  ownerPrompts?: number;
}

export interface InnovationSeed {
  seedId: string;
  outcomeId: string;
  sourceKind: OutcomeKind;
  thesis: string;
  requiredWork: readonly string[];
  falsificationTargets: readonly string[];
  evidenceRefs: readonly string[];
}

function normalizedText(value: string | undefined): string {
  return value?.trim() ?? "";
}

export function deriveOutcomeInnovationSeed(observation: OutcomeObservation): InnovationSeed {
  if (!normalizedText(observation.outcomeId)) throw new Error("OUTCOME_ID_REQUIRED");
  if (!normalizedText(observation.objective)) throw new Error("OUTCOME_OBJECTIVE_REQUIRED");
  if (!normalizedText(observation.observedState)) throw new Error("OBSERVED_STATE_REQUIRED");
  if (observation.evidenceRefs.length === 0) throw new Error("OUTCOME_EVIDENCE_REQUIRED");

  const base = `${observation.outcomeId}:${observation.kind}`;
  if (observation.kind === "SUCCESS") {
    const technique = normalizedText(observation.successfulTechnique) || "observed successful route";
    return {
      seedId: `${base}:SUCCESS-MINE`,
      outcomeId: observation.outcomeId,
      sourceKind: observation.kind,
      thesis: `Extract the invariant behind ${technique}, then seek a simpler, faster or more general implementation without quality or safety regression.`,
      requiredWork: [
        "extract-success-invariant",
        "generate-harder-holdout",
        "generate-simplification-candidate",
        "benchmark-incumbent-vs-challenger",
        "capture-reusable-skill-if-proven",
      ],
      falsificationTargets: [
        "success-was-input-specific",
        "success-depended-on-hidden-manual-intervention",
        "simplification-regresses-quality-or-safety",
      ],
      evidenceRefs: [...observation.evidenceRefs],
    };
  }

  if (observation.kind === "FAILURE") {
    const failureClass = normalizedText(observation.failureClass) || "UNCLASSIFIED_FAILURE";
    return {
      seedId: `${base}:FAILURE-FORGE`,
      outcomeId: observation.outcomeId,
      sourceKind: observation.kind,
      thesis: `Reproduce ${failureClass}, isolate the root cause, generate independent repair hypotheses, and preserve the winning repair as a regression oracle.`,
      requiredWork: [
        "reproduce-failure",
        "isolate-root-cause",
        "generate-repair-hypotheses",
        "run-targeted-court",
        "run-no-regression-court",
        "persist-regression-oracle-if-proven",
      ],
      falsificationTargets: [
        "failure-not-reproducible",
        "patch-treats-symptom-only",
        "repair-breaks-unrelated-contract",
      ],
      evidenceRefs: [...observation.evidenceRefs],
    };
  }

  if (observation.kind === "PARTIAL") {
    return {
      seedId: `${base}:GAP-CLOSURE`,
      outcomeId: observation.outcomeId,
      sourceKind: observation.kind,
      thesis: "Separate the proven portion from the unresolved delta and build the smallest experiment that can close or falsify the remaining gap.",
      requiredWork: [
        "partition-proven-vs-unproven",
        "rank-unresolved-gaps",
        "build-minimum-gap-closing-experiment",
        "run-targeted-court",
      ],
      falsificationTargets: ["claimed-completion-exceeds-observation", "gap-requires-new-authority", "gap-has-no-testable-oracle"],
      evidenceRefs: [...observation.evidenceRefs],
    };
  }

  return {
    seedId: `${base}:BLOCKER-ROUTE`,
    outcomeId: observation.outcomeId,
    sourceKind: observation.kind,
    thesis: "Classify the blocker, search for a safe alternate route, and convert the missing capability into a bounded build or qualification work package.",
    requiredWork: [
      "classify-blocker",
      "search-reusable-capabilities",
      "generate-alternate-route",
      "build-missing-capability-if-safe",
      "prove-route-before-promotion",
    ],
    falsificationTargets: ["alternate-route-violates-authority", "capability-gap-is-external-only", "route-cannot-produce-independent-readback"],
    evidenceRefs: [...observation.evidenceRefs],
  };
}

export interface ToolDescriptor {
  name: string;
  description: string;
  tags: readonly string[];
  schemaCharacters: number;
  expectedCalls: number;
}

export function selectOnDemandTools(
  intent: string,
  tools: readonly ToolDescriptor[],
  maxTools = 8,
): readonly ToolDescriptor[] {
  const terms = new Set(intent.toLowerCase().split(/[^a-z0-9]+/).filter((term) => term.length >= 3));
  return [...tools]
    .map((tool) => {
      const haystack = `${tool.name} ${tool.description} ${tool.tags.join(" ")}`.toLowerCase();
      const relevance = [...terms].filter((term) => haystack.includes(term)).length;
      const contextPenalty = Math.max(0, tool.schemaCharacters) / 20000;
      const reuseBonus = Math.log2(Math.max(1, tool.expectedCalls) + 1) / 4;
      return { tool, score: relevance + reuseBonus - contextPenalty };
    })
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score || a.tool.name.localeCompare(b.tool.name))
    .slice(0, Math.max(1, maxTools))
    .map((item) => item.tool);
}

export interface AgentRoleSpec {
  role: string;
  objective: string;
  contextRefs: readonly string[];
  writableScopes: readonly string[];
  independentFailureDomain: string;
}

export interface AgentCellPlan {
  cellId: string;
  roles: readonly AgentRoleSpec[];
  maxParallel: number;
  requiresReconciliation: boolean;
}

export function formSpecialistAgentCell(input: {
  cellId: string;
  roles: readonly AgentRoleSpec[];
  maxParallel?: number;
}): AgentCellPlan {
  if (!input.cellId.trim()) throw new Error("AGENT_CELL_ID_REQUIRED");
  const uniqueRoles = new Map<string, AgentRoleSpec>();
  for (const role of input.roles) {
    if (!role.role.trim() || !role.objective.trim()) throw new Error("AGENT_ROLE_INVALID");
    if (!uniqueRoles.has(role.role)) uniqueRoles.set(role.role, role);
  }
  const roles = [...uniqueRoles.values()];
  const scopeWriters = new Map<string, number>();
  for (const role of roles) {
    for (const scope of role.writableScopes) {
      scopeWriters.set(scope, (scopeWriters.get(scope) ?? 0) + 1);
    }
  }
  const requiresReconciliation = [...scopeWriters.values()].some((count) => count > 1);
  return {
    cellId: input.cellId,
    roles,
    maxParallel: Math.min(Math.max(1, input.maxParallel ?? roles.length), Math.max(1, roles.length)),
    requiresReconciliation,
  };
}

export interface BlastRadiusInput {
  authorityLevel: 0 | 1 | 2 | 3;
  reversibility: number;
  affectedResources: number;
  externalEffect: boolean;
  independentReadback: boolean;
}

export interface BlastRadiusDecision {
  budget: number;
  allowed: boolean;
  reason: string;
}

export function computeBlastRadiusBudget(input: BlastRadiusInput): BlastRadiusDecision {
  const reversibility = Math.min(1, Math.max(0, input.reversibility));
  const authorityPenalty = input.authorityLevel * 0.18;
  const resourcePenalty = Math.min(0.35, Math.max(0, input.affectedResources - 1) * 0.04);
  const externalPenalty = input.externalEffect ? 0.35 : 0;
  const readbackBonus = input.independentReadback ? 0.15 : 0;
  const budget = Math.max(0, Math.min(1, reversibility + readbackBonus - authorityPenalty - resourcePenalty - externalPenalty));
  if (input.externalEffect && input.authorityLevel >= 2) return { budget, allowed: false, reason: "external-high-authority-requires-owner-gate" };
  if (!input.independentReadback) return { budget, allowed: false, reason: "independent-readback-required" };
  if (budget < 0.45) return { budget, allowed: false, reason: "blast-radius-budget-too-low" };
  return { budget, allowed: true, reason: "within-bounded-blast-radius" };
}

export interface InnovationCandidate {
  candidateId: string;
  novelty: number;
  expectedQualityGain: number;
  expectedLatencyGain: number;
  expectedOwnerBurdenGain: number;
  expectedResilienceGain: number;
  risk: number;
  cost: number;
  reversible: boolean;
  evidenceRefs: readonly string[];
}

export function scoreInnovationCandidate(candidate: InnovationCandidate): number {
  const bounded = (value: number) => Math.min(1, Math.max(0, value));
  const positive =
    0.24 * bounded(candidate.expectedQualityGain)
    + 0.16 * bounded(candidate.expectedLatencyGain)
    + 0.16 * bounded(candidate.expectedOwnerBurdenGain)
    + 0.18 * bounded(candidate.expectedResilienceGain)
    + 0.16 * bounded(candidate.novelty)
    + 0.10 * (candidate.reversible ? 1 : 0);
  const penalty = 0.16 * bounded(candidate.risk) + 0.08 * bounded(candidate.cost);
  return Math.max(-1, Math.min(1, positive - penalty));
}

export function rankInnovationCandidates(candidates: readonly InnovationCandidate[]): readonly InnovationCandidate[] {
  return [...candidates]
    .filter((candidate) => candidate.candidateId.trim().length > 0 && candidate.evidenceRefs.length > 0)
    .sort((a, b) => scoreInnovationCandidate(b) - scoreInnovationCandidate(a) || a.candidateId.localeCompare(b.candidateId));
}

export interface GeneralizationCourtInput {
  baselineQuality: number;
  candidateQuality: number;
  baselineLatencyMs: number;
  candidateLatencyMs: number;
  safetyRegression: boolean;
  holdoutPassRate: number;
  adversarialPassRate: number;
  rollbackProven: boolean;
  independentReadback: boolean;
}

export interface GeneralizationCourtVerdict {
  promote: boolean;
  reasons: readonly string[];
  latencyRatio: number;
}

export function runGeneralizationCourt(input: GeneralizationCourtInput): GeneralizationCourtVerdict {
  const reasons: string[] = [];
  const latencyRatio = input.candidateLatencyMs > 0 ? input.baselineLatencyMs / input.candidateLatencyMs : 0;
  if (input.candidateQuality + 0.01 < input.baselineQuality) reasons.push("quality-regression");
  if (input.safetyRegression) reasons.push("safety-regression");
  if (input.holdoutPassRate < 0.90) reasons.push("holdout-below-floor");
  if (input.adversarialPassRate < 0.85) reasons.push("adversarial-below-floor");
  if (!input.rollbackProven) reasons.push("rollback-unproven");
  if (!input.independentReadback) reasons.push("readback-unproven");
  return { promote: reasons.length === 0, reasons, latencyRatio };
}

export interface RegressionCase {
  id: string;
  trigger: string;
  expectedInvariant: string;
  evidenceRefs: readonly string[];
  blocking: boolean;
}

export function compileRegressionCase(observation: OutcomeObservation, expectedInvariant: string): RegressionCase {
  if (!expectedInvariant.trim()) throw new Error("REGRESSION_INVARIANT_REQUIRED");
  return {
    id: `REG:${observation.outcomeId}`,
    trigger: observation.kind === "SUCCESS" ? "prove-success-invariant-remains-true" : "prove-observed-failure-does-not-recur",
    expectedInvariant,
    evidenceRefs: [...observation.evidenceRefs],
    blocking: true,
  };
}

export interface HarnessAssumption {
  id: string;
  description: string;
  stillRequired: boolean;
  removalNoRegressionProven: boolean;
}

export function harnessSimplificationCandidates(assumptions: readonly HarnessAssumption[]): readonly HarnessAssumption[] {
  return assumptions
    .filter((assumption) => !assumption.stillRequired && assumption.removalNoRegressionProven)
    .sort((a, b) => a.id.localeCompare(b.id));
}

export interface DiffusionDecision {
  allowed: boolean;
  reason: string;
  receiver: string;
}

export function compatibleDiffusionDecision(input: {
  receiver: string;
  sourceProofRefs: readonly string[];
  receiverCompatibilityProven: boolean;
  localEffectReadbackProven: boolean;
  changesAuthority: boolean;
}): DiffusionDecision {
  if (!input.receiver.trim()) return { allowed: false, reason: "receiver-required", receiver: input.receiver };
  if (input.sourceProofRefs.length === 0) return { allowed: false, reason: "source-proof-required", receiver: input.receiver };
  if (!input.receiverCompatibilityProven) return { allowed: false, reason: "receiver-compatibility-unproven", receiver: input.receiver };
  if (!input.localEffectReadbackProven) return { allowed: false, reason: "receiver-local-effect-unproven", receiver: input.receiver };
  if (input.changesAuthority) return { allowed: false, reason: "authority-change-requires-owner-gate", receiver: input.receiver };
  return { allowed: true, reason: "compatible-proof-preserving-diffusion", receiver: input.receiver };
}

export function anthropicV4Disposition(input: {
  observation: OutcomeObservation;
  candidateCount: number;
  courtPassed: boolean;
  proofRefs: readonly string[];
}): "INNOVATE" | "HOLD" | "PROMOTE_INTERNAL" {
  if (input.proofRefs.length === 0) return "HOLD";
  if (input.candidateCount <= 0) return "INNOVATE";
  if (!input.courtPassed) return "INNOVATE";
  return "PROMOTE_INTERNAL";
}
