import {
  compileAlphaOmegaFormationEvolution,
  type AlphaOmegaEvolutionPlan,
  type EvolutionStage,
} from './alphaOmegaFormationEvolution';
import type { OutcomeKind, OutcomeObservation } from './anthropicCfbeV4';

const MAX_LOCAL_EVOLUTION_RECEIPTS = 32;
let receiptSequence = 0;
const localReceipts: EvolutionReceipt[] = [];

export interface EvolutionOutcomeInput {
  kind: OutcomeKind;
  operation: 'OWNER_CONNECT' | 'FUSE_REQUEST' | 'OTHER';
  mode?: string;
  status: string;
  evidenceRefs: readonly string[];
  latencyMs?: number;
  failureClass?: string;
  successfulTechnique?: string;
  requirements?: readonly string[];
}

export interface EvolutionReceipt {
  receiptId: string;
  createdAt: string;
  outcomeKind: OutcomeKind;
  operation: EvolutionOutcomeInput['operation'];
  status: string;
  stage: EvolutionStage;
  innovationSeedId: string;
  innovationThesis: string;
  workPackageCount: number;
  agentRoles: readonly string[];
  ownerGateReasons: readonly string[];
  proofRequiredBeforePromotion: readonly string[];
  nextWork: readonly string[];
}

function normalizedEvidence(input: EvolutionOutcomeInput): readonly string[] {
  const unique = [...new Set(input.evidenceRefs.map((ref) => ref.trim()).filter(Boolean))];
  if (unique.length > 0) return unique;
  return [`LOCAL:${input.operation}:${input.kind}:${input.status || 'UNKNOWN'}`];
}

function objectiveFor(input: EvolutionOutcomeInput): string {
  const mode = input.mode?.trim() ? ` ${input.mode.trim()}` : '';
  return `${input.operation}${mode} outcome improvement`;
}

function observedStateFor(input: EvolutionOutcomeInput): string {
  const latency = input.latencyMs === undefined ? '' : `;latency_ms=${Math.max(0, Math.round(input.latencyMs))}`;
  return `kind=${input.kind};status=${input.status || 'UNKNOWN'}${latency}`;
}

function toObservation(input: EvolutionOutcomeInput): OutcomeObservation {
  receiptSequence += 1;
  return {
    outcomeId: `MOBILE-OUTCOME-${String(receiptSequence).padStart(6, '0')}`,
    kind: input.kind,
    objective: objectiveFor(input),
    expectedState: 'authorized operation completes with independent observable readback',
    observedState: observedStateFor(input),
    evidenceRefs: normalizedEvidence(input),
    failureClass: input.failureClass,
    successfulTechnique: input.successfulTechnique,
    latencyMs: input.latencyMs,
  };
}

function defaultRequirements(input: EvolutionOutcomeInput): readonly string[] {
  return [
    `${input.operation.toLowerCase()} outcome remains evidence-bound`,
    'no safety or authority regression',
    'independent readback remains available',
    'rollback or safe retry path remains available',
    ...(input.requirements ?? []),
  ];
}

function receiptFromPlan(
  input: EvolutionOutcomeInput,
  observation: OutcomeObservation,
  plan: AlphaOmegaEvolutionPlan,
): EvolutionReceipt {
  return {
    receiptId: `EVR:${observation.outcomeId}`,
    createdAt: new Date().toISOString(),
    outcomeKind: input.kind,
    operation: input.operation,
    status: input.status || 'UNKNOWN',
    stage: plan.stage,
    innovationSeedId: plan.innovationSeed.seedId,
    innovationThesis: plan.innovationSeed.thesis,
    workPackageCount: plan.workPackages.length,
    agentRoles: plan.agentCell.roles.map((role) => role.role),
    ownerGateReasons: [...plan.ownerGateReasons],
    proofRequiredBeforePromotion: [...plan.proofRequiredBeforePromotion],
    nextWork: plan.workPackages.map((item) => item.objective),
  };
}

/**
 * Every observed success, partial result, failure or blocker is converted into
 * a bounded Alpha-Omega Formation improvement plan. This function only creates
 * local planning/proof state; it does not mutate provider authority, secrets,
 * IAM, production traffic or repository source by itself.
 */
export function captureEvolutionOutcome(input: EvolutionOutcomeInput): EvolutionReceipt {
  const observation = toObservation(input);
  const plan = compileAlphaOmegaFormationEvolution({
    missionId: `EVOLUTION:${observation.outcomeId}`,
    objective: objectiveFor(input),
    observation,
    requirements: defaultRequirements(input),
    maxParallelAgents: 6,
    sprintBudgetMinutes: 55,
  });
  const receipt = receiptFromPlan(input, observation, plan);
  localReceipts.unshift(receipt);
  if (localReceipts.length > MAX_LOCAL_EVOLUTION_RECEIPTS) {
    localReceipts.splice(MAX_LOCAL_EVOLUTION_RECEIPTS);
  }
  return receipt;
}

export function latestEvolutionReceipt(): EvolutionReceipt | null {
  return localReceipts[0] ?? null;
}

export function listEvolutionReceipts(): readonly EvolutionReceipt[] {
  return [...localReceipts];
}

export function clearEvolutionReceiptsForTest(): void {
  localReceipts.splice(0, localReceipts.length);
  receiptSequence = 0;
}
