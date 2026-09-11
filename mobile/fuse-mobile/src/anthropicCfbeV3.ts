export type AnthropicV3Maturity =
  | "REUSE_VERIFIED"
  | "SOURCE_IMPLEMENTED"
  | "RUNTIME_GATED"
  | "PROVIDER_GATED";

export interface AnthropicV3Gene {
  id: string;
  pattern: string;
  fusePrimitive: string;
  maturity: AnthropicV3Maturity;
  proofTarget: string;
}

export const ANTHROPIC_CFBE_V3_GENOME: readonly AnthropicV3Gene[] = [
  { id: "ANTH-073", pattern: "discoverable hardware capability manifest", fusePrimitive: "DEVICE.CAPABILITY_MANIFEST", maturity: "SOURCE_IMPLEMENTED", proofTarget: "unknown devices expose commands, limits, telemetry and safety metadata before use" },
  { id: "ANTH-074", pattern: "natural-language hardware safety metadata", fusePrimitive: "DEVICE.SAFETY_KNOWLEDGE_TAGS", maturity: "SOURCE_IMPLEMENTED", proofTarget: "tacit operating constraints become machine-readable agent context" },
  { id: "ANTH-075", pattern: "model-agnostic physical AI interface", fusePrimitive: "DEVICE.MODEL_AGNOSTIC_BRIDGE", maturity: "SOURCE_IMPLEMENTED", proofTarget: "device contract depends on commands and proofs rather than one model vendor" },
  { id: "ANTH-076", pattern: "MCP CLI API hardware convergence", fusePrimitive: "DEVICE.MULTI_PROTOCOL_ADAPTER", maturity: "SOURCE_IMPLEMENTED", proofTarget: "the same bounded command can be addressed through typed tools, CLI or code" },
  { id: "ANTH-077", pattern: "parallel hardware orchestration", fusePrimitive: "DEVICE.PARALLEL_ORCHESTRATOR", maturity: "RUNTIME_GATED", proofTarget: "independent devices run concurrently without violating shared safety limits" },
  { id: "ANTH-078", pattern: "closed-loop observe adjust", fusePrimitive: "DEVICE.OBSERVE_ADJUST_LOOP", maturity: "SOURCE_IMPLEMENTED", proofTarget: "writes are followed by readback before the next parameter change" },
  { id: "ANTH-079", pattern: "compile learned device routine into deterministic code", fusePrimitive: "DEVICE.DETERMINISTIC_ROUTINE_COMPILER", maturity: "SOURCE_IMPLEMENTED", proofTarget: "stable repeated procedures no longer require model reasoning at every step" },
  { id: "ANTH-080", pattern: "driver-enforced safety limits", fusePrimitive: "DEVICE.DRIVER_SAFETY_ENVELOPE", maturity: "RUNTIME_GATED", proofTarget: "unsafe command parameters fail below the model layer" },
  { id: "ANTH-081", pattern: "days-long asynchronous mission contract", fusePrimitive: "AGENT.ASYNC_MISSION_STATE", maturity: "SOURCE_IMPLEMENTED", proofTarget: "mission can pause, resume and recover without losing objective or evidence cursor" },
  { id: "ANTH-082", pattern: "failure recovery before escalation", fusePrimitive: "AGENT.BOUNDED_RECOVERY", maturity: "SOURCE_IMPLEMENTED", proofTarget: "recoverable faults retry under hard ceilings; unknown/unsafe faults escalate" },
  { id: "ANTH-083", pattern: "owner progress heartbeat", fusePrimitive: "AGENT.PROGRESS_HEARTBEAT", maturity: "SOURCE_IMPLEMENTED", proofTarget: "long missions surface meaningful progress without requiring owner polling" },
  { id: "ANTH-084", pattern: "self-authored acceptance tests", fusePrimitive: "AGENT.SELF_TEST_PLAN", maturity: "SOURCE_IMPLEMENTED", proofTarget: "generator creates executable checks before claiming completion" },
  { id: "ANTH-085", pattern: "vision-assisted output verification", fusePrimitive: "AGENT.VISION_OUTCOME_CHECK", maturity: "PROVIDER_GATED", proofTarget: "visual output is compared with the intended design or target state" },
  { id: "ANTH-086", pattern: "root-cause repair preference", fusePrimitive: "REASON.ROOT_CAUSE_GATE", maturity: "SOURCE_IMPLEMENTED", proofTarget: "symptom-only patches require explicit justification" },
  { id: "ANTH-087", pattern: "cache-aware long-agent economics", fusePrimitive: "CONTEXT.CACHE_ECONOMICS", maturity: "SOURCE_IMPLEMENTED", proofTarget: "stable repeated context is cached only when expected savings exceed overhead" },
  { id: "ANTH-088", pattern: "pending-event session hydration", fusePrimitive: "AGENT.EVENT_HYDRATION", maturity: "SOURCE_IMPLEMENTED", proofTarget: "stateless brains reconstruct only pending and high-signal mission events" },
  { id: "ANTH-089", pattern: "stateless reasoning pool", fusePrimitive: "EXEC.STATELESS_BRAIN_POOL", maturity: "RUNTIME_GATED", proofTarget: "reasoning workers scale independently of execution environments" },
  { id: "ANTH-090", pattern: "execution-hand health and replacement", fusePrimitive: "EXEC.HAND_HEALTH_ROUTER", maturity: "SOURCE_IMPLEMENTED", proofTarget: "failed execution hands can be replaced without losing mission state" },
  { id: "ANTH-091", pattern: "execution-hand transfer between brains", fusePrimitive: "EXEC.HAND_TRANSFER", maturity: "RUNTIME_GATED", proofTarget: "a qualified successor brain resumes the same hand under unchanged authority" },
  { id: "ANTH-092", pattern: "approval-fatigue telemetry", fusePrimitive: "SEC.APPROVAL_FATIGUE_METER", maturity: "SOURCE_IMPLEMENTED", proofTarget: "approval rate and prompt volume drive safer automation rather than blind prompt reduction" },
  { id: "ANTH-093", pattern: "oversight-capability-aware containment", fusePrimitive: "SEC.OPERATOR_AWARE_CONTAINMENT", maturity: "SOURCE_IMPLEMENTED", proofTarget: "containment strength increases when users cannot meaningfully review low-level actions" },
  { id: "ANTH-094", pattern: "mature security primitive preference", fusePrimitive: "SEC.BATTLE_TESTED_PRIMITIVE_BIAS", maturity: "SOURCE_IMPLEMENTED", proofTarget: "custom security components require justification over hardened standard isolation" },
  { id: "ANTH-095", pattern: "credential provenance proxy", fusePrimitive: "SEC.CREDENTIAL_PROVENANCE_GATE", maturity: "RUNTIME_GATED", proofTarget: "allowed egress accepts only brokered credentials bound to the active environment" },
  { id: "ANTH-096", pattern: "typed inspection for every external return", fusePrimitive: "SEC.RETURN_SOURCE_INSPECTION", maturity: "SOURCE_IMPLEMENTED", proofTarget: "web, file, shell and connector outputs all cross the same pre-context trust gate" },
  { id: "ANTH-097", pattern: "reproducible agent-eval resource matrix", fusePrimitive: "CFBE.EVAL_ENV_MATRIX", maturity: "SOURCE_IMPLEMENTED", proofTarget: "CPU, RAM, timeout, concurrency, egress and run time are recorded with each result" },
  { id: "ANTH-098", pattern: "small real-work eval bootstrap", fusePrimitive: "CFBE.REAL_TASK_SEED_SET", maturity: "SOURCE_IMPLEMENTED", proofTarget: "evaluation begins with a compact representative task set instead of waiting for a huge benchmark" },
  { id: "ANTH-099", pattern: "model-independent outcome judge ensemble", fusePrimitive: "CFBE.MULTI_GRADER_OUTCOME_COURT", maturity: "SOURCE_IMPLEMENTED", proofTarget: "deterministic, groundedness and rubric graders are combined by task type" },
  { id: "ANTH-100", pattern: "continuous provider qualification", fusePrimitive: "CFBE.PROVIDER_LIFECYCLE_COURT", maturity: "SOURCE_IMPLEMENTED", proofTarget: "provider/model upgrades must beat incumbent on normalized quality, cost, latency and safety" },
] as const;

export interface DeviceCapabilityManifest {
  deviceId: string;
  kind: string;
  commands: readonly {
    name: string;
    kind: "READ" | "WRITE";
    unit?: string;
    min?: number;
    max?: number;
    safetyNotes: readonly string[];
  }[];
  protocols: readonly ("MCP" | "CLI" | "API")[];
  metadata: Readonly<Record<string, string>>;
}

export function compileDeviceManifest(input: DeviceCapabilityManifest): DeviceCapabilityManifest {
  const commands = [...input.commands]
    .map((command) => ({ ...command, safetyNotes: [...command.safetyNotes] }))
    .sort((a, b) => a.name.localeCompare(b.name));
  const protocols = [...new Set(input.protocols)].sort() as DeviceCapabilityManifest["protocols"];
  return { ...input, commands, protocols, metadata: { ...input.metadata } };
}

export function validateDeviceWrite(input: {
  manifest: DeviceCapabilityManifest;
  commandName: string;
  value?: number;
}): { allowed: boolean; reason: string } {
  const command = input.manifest.commands.find((item) => item.name === input.commandName);
  if (!command) return { allowed: false, reason: "unknown-device-command" };
  if (command.kind !== "WRITE") return { allowed: false, reason: "command-is-not-write" };
  if (typeof input.value === "number" && typeof command.min === "number" && input.value < command.min) {
    return { allowed: false, reason: "below-driver-safety-minimum" };
  }
  if (typeof input.value === "number" && typeof command.max === "number" && input.value > command.max) {
    return { allowed: false, reason: "above-driver-safety-maximum" };
  }
  return { allowed: true, reason: "within-declared-device-envelope" };
}

export interface DeviceStep {
  id: string;
  deviceId: string;
  command: string;
  kind: "READ" | "WRITE";
  dependsOn?: readonly string[];
}

export function planObserveAdjustLoop(steps: readonly DeviceStep[]): readonly DeviceStep[] {
  const output: DeviceStep[] = [];
  for (const step of steps) {
    output.push(step);
    if (step.kind === "WRITE") {
      output.push({
        id: `${step.id}:readback`,
        deviceId: step.deviceId,
        command: `readback:${step.command}`,
        kind: "READ",
        dependsOn: [step.id],
      });
    }
  }
  return output;
}

export function validateParallelDevicePlan(steps: readonly DeviceStep[]): {
  parallelizable: boolean;
  conflictingDevices: readonly string[];
} {
  const writesByDevice = new Map<string, number>();
  for (const step of steps) {
    if (step.kind !== "WRITE") continue;
    writesByDevice.set(step.deviceId, (writesByDevice.get(step.deviceId) ?? 0) + 1);
  }
  const conflictingDevices = [...writesByDevice.entries()]
    .filter(([, count]) => count > 1)
    .map(([deviceId]) => deviceId)
    .sort();
  return { parallelizable: conflictingDevices.length === 0, conflictingDevices };
}

export function shouldCompileDeterministicRoutine(input: {
  successfulRepetitions: number;
  parameterVariance: number;
  safetyEnvelopeStable: boolean;
}): boolean {
  return input.successfulRepetitions >= 3 && input.parameterVariance <= 0.1 && input.safetyEnvelopeStable;
}

export type AsyncMissionStatus =
  | "PENDING"
  | "RUNNING"
  | "WAITING"
  | "RECOVERING"
  | "BLOCKED"
  | "SUCCEEDED"
  | "FAILED";

export interface AsyncMissionState {
  missionId: string;
  objective: string;
  status: AsyncMissionStatus;
  evidenceCursor: string;
  checkpointRef?: string;
  attempt: number;
  maxRecoveryAttempts: number;
  updatedAt: string;
}

export function createAsyncMission(input: {
  missionId: string;
  objective: string;
  maxRecoveryAttempts?: number;
  now?: string;
}): AsyncMissionState {
  return {
    missionId: input.missionId,
    objective: input.objective,
    status: "PENDING",
    evidenceCursor: "START",
    attempt: 0,
    maxRecoveryAttempts: Math.max(0, input.maxRecoveryAttempts ?? 2),
    updatedAt: input.now ?? new Date().toISOString(),
  };
}

export function recoverAsyncMission(
  mission: AsyncMissionState,
  input: { recoverable: boolean; safetyStateKnown: boolean; now?: string },
): AsyncMissionState {
  const now = input.now ?? new Date().toISOString();
  if (!input.safetyStateKnown) return { ...mission, status: "BLOCKED", updatedAt: now };
  if (!input.recoverable) return { ...mission, status: "FAILED", updatedAt: now };
  const attempt = mission.attempt + 1;
  if (attempt > mission.maxRecoveryAttempts) return { ...mission, status: "FAILED", attempt, updatedAt: now };
  return { ...mission, status: "RECOVERING", attempt, updatedAt: now };
}

export interface ProgressHeartbeat {
  missionId: string;
  status: AsyncMissionStatus;
  completedUnits: number;
  totalUnits?: number;
  blocker?: string;
  evidenceCursor: string;
  at: string;
}

export function createProgressHeartbeat(input: Omit<ProgressHeartbeat, "at"> & { at?: string }): ProgressHeartbeat {
  return { ...input, completedUnits: Math.max(0, input.completedUnits), at: input.at ?? new Date().toISOString() };
}

export interface AcceptanceCheck {
  id: string;
  description: string;
  oracle: "UNIT" | "INTEGRATION" | "VISUAL" | "PROVIDER_READBACK" | "OWNER_REVIEW";
  blocking: boolean;
}

export function buildSelfTestPlan(requirements: readonly string[]): readonly AcceptanceCheck[] {
  return requirements
    .map((description, index): AcceptanceCheck => ({
      id: `ACC-${String(index + 1).padStart(3, "0")}`,
      description,
      oracle: /visual|layout|screen|design/i.test(description) ? "VISUAL" : "INTEGRATION",
      blocking: true,
    }))
    .filter((check) => check.description.trim().length > 0);
}

export function visualVerificationRequirement(input: {
  hasVisualTarget: boolean;
  providerVisionAvailable: boolean;
}): "REQUIRED" | "OWNER_REVIEW_FALLBACK" | "NOT_APPLICABLE" {
  if (!input.hasVisualTarget) return "NOT_APPLICABLE";
  return input.providerVisionAvailable ? "REQUIRED" : "OWNER_REVIEW_FALLBACK";
}

export function rootCauseRepairGate(input: {
  causeIdentified: boolean;
  patchAddressesCause: boolean;
  mitigationOnlyJustified: boolean;
}): { acceptable: boolean; reason: string } {
  if (input.causeIdentified && input.patchAddressesCause) return { acceptable: true, reason: "root-cause-addressed" };
  if (input.mitigationOnlyJustified) return { acceptable: true, reason: "temporary-mitigation-explicitly-justified" };
  return { acceptable: false, reason: "symptom-only-repair-rejected" };
}

export function contextCachePolicy(input: {
  stablePrefixCharacters: number;
  expectedReuseCount: number;
  cacheWriteCost: number;
  uncachedReuseCost: number;
  cachedReuseCost: number;
}): { useCache: boolean; estimatedSavings: number } {
  if (input.stablePrefixCharacters <= 0 || input.expectedReuseCount <= 0) return { useCache: false, estimatedSavings: 0 };
  const uncached = input.uncachedReuseCost * input.expectedReuseCount;
  const cached = input.cacheWriteCost + input.cachedReuseCost * input.expectedReuseCount;
  const estimatedSavings = uncached - cached;
  return { useCache: estimatedSavings > 0, estimatedSavings };
}

export interface MissionEvent {
  id: string;
  kind: "OBJECTIVE" | "PLAN" | "ACTION" | "OBSERVATION" | "BLOCKER" | "CHECKPOINT" | "OUTCOME";
  text: string;
  pending?: boolean;
  pinned?: boolean;
}

export function hydrateMissionContext(events: readonly MissionEvent[], maxCharacters = 16000): readonly MissionEvent[] {
  const priority = events.filter((event) => event.pending || event.pinned || event.kind === "OBJECTIVE" || event.kind === "PLAN");
  const selected = new Map(priority.map((event) => [event.id, event]));
  let used = priority.reduce((sum, event) => sum + event.text.length, 0);
  for (const event of [...events].reverse()) {
    if (selected.has(event.id)) continue;
    if (used + event.text.length > maxCharacters) continue;
    selected.set(event.id, event);
    used += event.text.length;
  }
  return events.filter((event) => selected.has(event.id));
}

export function executionHandHealthDecision(input: {
  healthy: boolean;
  stateExternalized: boolean;
  replacementAvailable: boolean;
}): "KEEP" | "REPLACE" | "CHECKPOINT_AND_STOP" {
  if (input.healthy) return "KEEP";
  if (input.stateExternalized && input.replacementAvailable) return "REPLACE";
  return "CHECKPOINT_AND_STOP";
}

export function approvalFatigueRisk(input: {
  approvalPrompts: number;
  approvalsGranted: number;
  repeatedPromptSimilarity: number;
}): "LOW" | "MEDIUM" | "HIGH" {
  if (input.approvalPrompts <= 0) return "LOW";
  const approvalRate = Math.max(0, Math.min(1, input.approvalsGranted / input.approvalPrompts));
  const fatigueScore = 0.55 * approvalRate + 0.25 * Math.min(1, input.approvalPrompts / 30) + 0.2 * Math.max(0, Math.min(1, input.repeatedPromptSimilarity));
  if (fatigueScore >= 0.75) return "HIGH";
  if (fatigueScore >= 0.5) return "MEDIUM";
  return "LOW";
}

export function containmentForOperator(input: {
  canReviewLowLevelActions: boolean;
  actionIrreversibility: number;
  dataSensitivity: number;
}): "STANDARD_SANDBOX" | "STRONG_SANDBOX" | "ISOLATED_VM" {
  const score =
    (input.canReviewLowLevelActions ? 0 : 0.35) +
    0.35 * Math.max(0, Math.min(1, input.actionIrreversibility)) +
    0.3 * Math.max(0, Math.min(1, input.dataSensitivity));
  if (score >= 0.7) return "ISOLATED_VM";
  if (score >= 0.4) return "STRONG_SANDBOX";
  return "STANDARD_SANDBOX";
}

export function securityPrimitiveDecision(input: {
  matureStandardAvailable: boolean;
  customCapabilityRequired: boolean;
  customComponentReviewed: boolean;
}): "USE_MATURE_STANDARD" | "ALLOW_CUSTOM" | "BLOCK_CUSTOM" {
  if (input.matureStandardAvailable && !input.customCapabilityRequired) return "USE_MATURE_STANDARD";
  if (input.customCapabilityRequired && input.customComponentReviewed) return "ALLOW_CUSTOM";
  return "BLOCK_CUSTOM";
}

export interface BrokeredCredential {
  id: string;
  environmentId: string;
  audience: string;
  expiresAtEpochMs: number;
}

export function validateEgressCredential(input: {
  credential: BrokeredCredential;
  activeEnvironmentId: string;
  destination: string;
  nowEpochMs: number;
}): { allowed: boolean; reason: string } {
  if (input.credential.environmentId !== input.activeEnvironmentId) return { allowed: false, reason: "credential-environment-provenance-mismatch" };
  if (input.credential.audience !== input.destination) return { allowed: false, reason: "credential-audience-mismatch" };
  if (input.credential.expiresAtEpochMs <= input.nowEpochMs) return { allowed: false, reason: "credential-expired" };
  return { allowed: true, reason: "credential-provenance-valid" };
}

export type ExternalReturnSource = "WEB" | "FILE" | "SHELL" | "CONNECTOR" | "MCP";

export function inspectionPolicyForReturn(input: {
  source: ExternalReturnSource;
  containsInstructions: boolean;
  containsSecrets: boolean;
}): "PASS_WITH_TRUST_LABEL" | "SCAN_AND_WARN" | "QUARANTINE" {
  if (input.containsSecrets) return "QUARANTINE";
  if (input.containsInstructions) return "SCAN_AND_WARN";
  return "PASS_WITH_TRUST_LABEL";
}

export interface EvalEnvironment {
  cpu: number;
  ramGb: number;
  timeoutSeconds: number;
  concurrency: number;
  egressProfile: string;
  runWindow: string;
}

export function normalizeEvalEnvironment(input: EvalEnvironment): EvalEnvironment {
  if (input.cpu <= 0 || input.ramGb <= 0 || input.timeoutSeconds <= 0 || input.concurrency <= 0) {
    throw new Error("invalid-eval-environment");
  }
  return { ...input, egressProfile: input.egressProfile.trim(), runWindow: input.runWindow.trim() };
}

export function bootstrapRealTaskEval<T>(tasks: readonly T[], target = 20): readonly T[] {
  return tasks.slice(0, Math.max(1, target));
}

export interface GraderResult {
  grader: "DETERMINISTIC" | "GROUNDEDNESS" | "RUBRIC" | "SOURCE_QUALITY" | "TOOL_EFFICIENCY";
  score: number;
  weight: number;
}

export function aggregateOutcomeGraders(results: readonly GraderResult[]): number {
  const valid = results.filter((result) => result.weight > 0);
  const totalWeight = valid.reduce((sum, result) => sum + result.weight, 0);
  if (totalWeight <= 0) return 0;
  return valid.reduce((sum, result) => sum + Math.max(0, Math.min(1, result.score)) * result.weight, 0) / totalWeight;
}

export function providerLifecycleDecision(input: {
  qualityDelta: number;
  costDelta: number;
  latencyDelta: number;
  safetyRegression: boolean;
  deprecationDaysRemaining?: number;
}): "PROMOTE_CHALLENGER" | "KEEP_INCUMBENT" | "MIGRATE_BEFORE_DEPRECATION" {
  if (typeof input.deprecationDaysRemaining === "number" && input.deprecationDaysRemaining <= 30) {
    return "MIGRATE_BEFORE_DEPRECATION";
  }
  if (input.safetyRegression) return "KEEP_INCUMBENT";
  const score = 0.55 * input.qualityDelta + 0.25 * input.costDelta + 0.2 * input.latencyDelta;
  return score > 0 ? "PROMOTE_CHALLENGER" : "KEEP_INCUMBENT";
}

export function anthropicV3Disposition(): Readonly<Record<AnthropicV3Maturity, number>> {
  return ANTHROPIC_CFBE_V3_GENOME.reduce<Record<AnthropicV3Maturity, number>>(
    (counts, gene) => {
      counts[gene.maturity] += 1;
      return counts;
    },
    { REUSE_VERIFIED: 0, SOURCE_IMPLEMENTED: 0, RUNTIME_GATED: 0, PROVIDER_GATED: 0 },
  );
}
