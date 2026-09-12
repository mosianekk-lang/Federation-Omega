import {
  buildSelfTestPlan,
  rootCauseRepairGate,
  type AcceptanceCheck,
} from './anthropicCfbeV3';
import {
  anthropicV4Disposition,
  computeBlastRadiusBudget,
  deriveOutcomeInnovationSeed,
  formSpecialistAgentCell,
  rankInnovationCandidates,
  runGeneralizationCourt,
  type AgentCellPlan,
  type AgentRoleSpec,
  type GeneralizationCourtInput,
  type InnovationCandidate,
  type InnovationSeed,
  type OutcomeObservation,
} from './anthropicCfbeV4';

export const ALPHA_OMEGA_FORMATION_ENGINE_VERSION = 'AO-FORMATION-EVOLUTION-1.0';
export const DEFAULT_SPRINT_BUDGET_MINUTES = 55;
export const DEFAULT_MAX_PARALLEL_AGENTS = 6;

export type EvolutionStage =
  | 'ALPHA_BIND'
  | 'OBSERVE'
  | 'FORMATION'
  | 'INNOVATE'
  | 'BUILD'
  | 'COURT'
  | 'OMEGA_HOLD'
  | 'OMEGA_PROMOTE_INTERNAL'
  | 'OWNER_GATE';

export type WorkKind =
  | 'ANALYZE'
  | 'REPRODUCE'
  | 'DESIGN'
  | 'BUILD'
  | 'TEST'
  | 'BENCHMARK'
  | 'CHALLENGE'
  | 'RECONCILE'
  | 'DIFFUSE';

export interface EvolutionMetrics {
  quality?: number;
  latencyMs?: number;
  ownerPrompts?: number;
  defects?: number;
  toolCalls?: number;
}

export interface AuthorityBoundary {
  createsExternalEffect: boolean;
  changesProviderAuthority: boolean;
  changesCredentialScope: boolean;
  createsRecurringCost: boolean;
  irreversibleMutation: boolean;
}

export interface EvolutionMissionInput {
  missionId: string;
  objective: string;
  observation: OutcomeObservation;
  requirements: readonly string[];
  metrics?: EvolutionMetrics;
  baselineMetrics?: EvolutionMetrics;
  authority?: Partial<AuthorityBoundary>;
  maxParallelAgents?: number;
  sprintBudgetMinutes?: number;
}

export interface EvolutionWorkPackage {
  workId: string;
  role: string;
  kind: WorkKind;
  objective: string;
  dependsOn: readonly string[];
  evidenceRefs: readonly string[];
  blocking: boolean;
  estimatedMinutes: number;
}

export interface EvolutionCheckpoint {
  checkpointId: string;
  stage: EvolutionStage;
  reason: string;
  evidenceRefs: readonly string[];
}

export interface AlphaOmegaEvolutionPlan {
  engineVersion: string;
  missionId: string;
  objective: string;
  stage: EvolutionStage;
  sprintBudgetMinutes: number;
  innovationSeed: InnovationSeed;
  agentCell: AgentCellPlan;
  acceptanceChecks: readonly AcceptanceCheck[];
  workPackages: readonly EvolutionWorkPackage[];
  checkpoints: readonly EvolutionCheckpoint[];
  ownerGateReasons: readonly string[];
  proofRequiredBeforePromotion: readonly string[];
  outcomeLearningMandatory: true;
}

export interface EvolutionCourtResult {
  missionId: string;
  stage: EvolutionStage;
  disposition: 'INNOVATE' | 'HOLD' | 'PROMOTE_INTERNAL' | 'OWNER_GATE';
  selectedCandidateId?: string;
  reasons: readonly string[];
  nextSequence: readonly string[];
}

function boundedMinutes(value: number | undefined): number {
  if (!Number.isFinite(value)) return DEFAULT_SPRINT_BUDGET_MINUTES;
  return Math.min(55, Math.max(5, Math.floor(value ?? DEFAULT_SPRINT_BUDGET_MINUTES)));
}

function boundedParallelism(value: number | undefined): number {
  if (!Number.isFinite(value)) return DEFAULT_MAX_PARALLEL_AGENTS;
  return Math.min(8, Math.max(1, Math.floor(value ?? DEFAULT_MAX_PARALLEL_AGENTS)));
}

function authorityBoundary(input?: Partial<AuthorityBoundary>): AuthorityBoundary {
  return {
    createsExternalEffect: input?.createsExternalEffect ?? false,
    changesProviderAuthority: input?.changesProviderAuthority ?? false,
    changesCredentialScope: input?.changesCredentialScope ?? false,
    createsRecurringCost: input?.createsRecurringCost ?? false,
    irreversibleMutation: input?.irreversibleMutation ?? false,
  };
}

function ownerGateReasons(boundary: AuthorityBoundary): readonly string[] {
  const reasons: string[] = [];
  if (boundary.createsExternalEffect) reasons.push('external-effect');
  if (boundary.changesProviderAuthority) reasons.push('provider-authority-change');
  if (boundary.changesCredentialScope) reasons.push('credential-scope-change');
  if (boundary.createsRecurringCost) reasons.push('recurring-cost');
  if (boundary.irreversibleMutation) reasons.push('irreversible-mutation');
  return reasons;
}

function specialistRoles(observation: OutcomeObservation): readonly AgentRoleSpec[] {
  const sharedContext = [...observation.evidenceRefs];
  const safetyRole: AgentRoleSpec = {
    role: 'SAFETY_PROOF_CRITIC',
    objective: 'Falsify unsafe, unproven or authority-expanding candidate routes before promotion.',
    contextRefs: sharedContext,
    writableScopes: [],
    independentFailureDomain: 'critic',
  };

  if (observation.kind === 'FAILURE') {
    return [
      {
        role: 'ROOT_CAUSE_ANALYST',
        objective: 'Reproduce the failure and isolate the smallest causal mechanism supported by evidence.',
        contextRefs: sharedContext,
        writableScopes: [],
        independentFailureDomain: 'analysis',
      },
      {
        role: 'REPRODUCTION_ENGINEER',
        objective: 'Build the minimum deterministic reproducer and preserve the failing preimage.',
        contextRefs: sharedContext,
        writableScopes: ['scratch/reproducer'],
        independentFailureDomain: 'reproduction',
      },
      {
        role: 'REPAIR_ARCHITECT',
        objective: 'Generate materially distinct root-cause repair hypotheses with explicit rollback paths.',
        contextRefs: sharedContext,
        writableScopes: ['scratch/candidates'],
        independentFailureDomain: 'design',
      },
      {
        role: 'REGRESSION_ENGINEER',
        objective: 'Convert the observed failure into a persistent blocking regression oracle.',
        contextRefs: sharedContext,
        writableScopes: ['scratch/tests'],
        independentFailureDomain: 'test',
      },
      {
        role: 'COUNTERFACTUAL_CHALLENGER',
        objective: 'Construct adversarial and holdout cases that can falsify an apparently successful repair.',
        contextRefs: sharedContext,
        writableScopes: ['scratch/holdout'],
        independentFailureDomain: 'challenge',
      },
      safetyRole,
    ];
  }

  if (observation.kind === 'SUCCESS') {
    return [
      {
        role: 'SUCCESS_PATTERN_MINER',
        objective: 'Extract the invariant responsible for the win without confusing correlation with causation.',
        contextRefs: sharedContext,
        writableScopes: [],
        independentFailureDomain: 'analysis',
      },
      {
        role: 'GENERALIZATION_CHALLENGER',
        objective: 'Create harder holdouts that test whether the success generalizes beyond the observed case.',
        contextRefs: sharedContext,
        writableScopes: ['scratch/holdout'],
        independentFailureDomain: 'challenge',
      },
      {
        role: 'SIMPLIFICATION_ENGINEER',
        objective: 'Seek a lower-cost, lower-latency or simpler implementation while preserving the invariant.',
        contextRefs: sharedContext,
        writableScopes: ['scratch/candidates'],
        independentFailureDomain: 'design',
      },
      {
        role: 'BENCHMARK_ENGINEER',
        objective: 'Measure incumbent versus challenger under frozen normalized conditions.',
        contextRefs: sharedContext,
        writableScopes: ['scratch/benchmarks'],
        independentFailureDomain: 'benchmark',
      },
      {
        role: 'DIFFUSION_ANALYST',
        objective: 'Identify compatible receivers for proven learning without assuming cross-surface equivalence.',
        contextRefs: sharedContext,
        writableScopes: [],
        independentFailureDomain: 'diffusion',
      },
      safetyRole,
    ];
  }

  return [
    {
      role: 'GAP_CLASSIFIER',
      objective: 'Partition proven state, unresolved state and external blockers without overstating completion.',
      contextRefs: sharedContext,
      writableScopes: [],
      independentFailureDomain: 'analysis',
    },
    {
      role: 'CAPABILITY_SCOUT',
      objective: 'Search for reusable capabilities before authoring a new implementation.',
      contextRefs: sharedContext,
      writableScopes: [],
      independentFailureDomain: 'discovery',
    },
    {
      role: 'ROUTE_ARCHITECT',
      objective: 'Compile the minimum safe gap-closing route with a falsifiable oracle.',
      contextRefs: sharedContext,
      writableScopes: ['scratch/candidates'],
      independentFailureDomain: 'design',
    },
    {
      role: 'COURT_ENGINEER',
      objective: 'Build the narrowest court that can prove or falsify the proposed closure.',
      contextRefs: sharedContext,
      writableScopes: ['scratch/tests'],
      independentFailureDomain: 'test',
    },
    safetyRole,
  ];
}

function estimatePackageMinutes(count: number, budgetMinutes: number): number {
  return Math.max(1, Math.floor(budgetMinutes / Math.max(1, count + 2)));
}

function workKindForStep(step: string): WorkKind {
  if (/reproduce/i.test(step)) return 'REPRODUCE';
  if (/benchmark/i.test(step)) return 'BENCHMARK';
  if (/test|court|regression|oracle/i.test(step)) return 'TEST';
  if (/challenge|holdout|falsif/i.test(step)) return 'CHALLENGE';
  if (/build|generate|repair|simplification|alternate-route/i.test(step)) return 'BUILD';
  if (/diffus|receiver|reuse|skill/i.test(step)) return 'DIFFUSE';
  if (/reconcile/i.test(step)) return 'RECONCILE';
  if (/design|plan|compile/i.test(step)) return 'DESIGN';
  return 'ANALYZE';
}

function compileWorkPackages(
  seed: InnovationSeed,
  roles: readonly AgentRoleSpec[],
  budgetMinutes: number,
): readonly EvolutionWorkPackage[] {
  const perPackage = estimatePackageMinutes(seed.requiredWork.length, budgetMinutes);
  return seed.requiredWork.map((step, index) => {
    const role = roles[index % roles.length];
    if (!role) throw new Error('EVOLUTION_ROLE_ALLOCATION_FAILED');
    return {
      workId: `WP-${String(index + 1).padStart(2, '0')}:${step}`,
      role: role.role,
      kind: workKindForStep(step),
      objective: step,
      dependsOn: index === 0 ? [] : [`WP-${String(index).padStart(2, '0')}:${seed.requiredWork[index - 1] ?? ''}`],
      evidenceRefs: [...seed.evidenceRefs],
      blocking: true,
      estimatedMinutes: perPackage,
    };
  });
}

function proofTargetsFor(observation: OutcomeObservation): readonly string[] {
  const common = [
    'exact-source-state',
    'blocking-test-or-court',
    'independent-readback',
    'no-safety-regression',
    'rollback-or-restorable-preimage',
  ];
  if (observation.kind === 'FAILURE') return [...common, 'failure-reproduced-before-repair', 'root-cause-addressed'];
  if (observation.kind === 'SUCCESS') return [...common, 'harder-holdout-pass', 'measured-benefit-over-incumbent'];
  return [...common, 'unresolved-gap-closed-with-observation'];
}

export function compileAlphaOmegaFormationEvolution(input: EvolutionMissionInput): AlphaOmegaEvolutionPlan {
  if (!input.missionId.trim()) throw new Error('EVOLUTION_MISSION_ID_REQUIRED');
  if (!input.objective.trim()) throw new Error('EVOLUTION_OBJECTIVE_REQUIRED');
  if (input.observation.evidenceRefs.length === 0) throw new Error('EVOLUTION_EVIDENCE_REQUIRED');

  const budget = boundedMinutes(input.sprintBudgetMinutes);
  const maxParallel = boundedParallelism(input.maxParallelAgents);
  const seed = deriveOutcomeInnovationSeed(input.observation);
  const roles = specialistRoles(input.observation);
  const cell = formSpecialistAgentCell({
    cellId: `${input.missionId}:FORMATION-CELL`,
    roles,
    maxParallel,
  });
  const checks = buildSelfTestPlan([
    ...input.requirements,
    ...seed.falsificationTargets.map((target) => `falsify:${target}`),
  ]);
  const packages = compileWorkPackages(seed, cell.roles, budget);
  const boundary = authorityBoundary(input.authority);
  const gateReasons = ownerGateReasons(boundary);
  const stage: EvolutionStage = gateReasons.length > 0 ? 'OWNER_GATE' : 'FORMATION';

  const blastRadius = computeBlastRadiusBudget({
    authorityLevel: gateReasons.length > 0 ? 2 : 1,
    reversibility: boundary.irreversibleMutation ? 0 : 1,
    affectedResources: Math.max(1, packages.length),
    externalEffect: boundary.createsExternalEffect,
    independentReadback: true,
  });

  const checkpoints: EvolutionCheckpoint[] = [
    {
      checkpointId: `${input.missionId}:ALPHA`,
      stage: 'ALPHA_BIND',
      reason: 'objective-and-evidence-bound-before-formation',
      evidenceRefs: [...input.observation.evidenceRefs],
    },
    {
      checkpointId: `${input.missionId}:FORMATION`,
      stage,
      reason: gateReasons.length > 0 ? `owner-gate:${gateReasons.join(',')}` : `blast-radius:${blastRadius.reason}`,
      evidenceRefs: [...input.observation.evidenceRefs],
    },
  ];

  return {
    engineVersion: ALPHA_OMEGA_FORMATION_ENGINE_VERSION,
    missionId: input.missionId,
    objective: input.objective,
    stage,
    sprintBudgetMinutes: budget,
    innovationSeed: seed,
    agentCell: cell,
    acceptanceChecks: checks,
    workPackages: packages,
    checkpoints,
    ownerGateReasons: gateReasons,
    proofRequiredBeforePromotion: proofTargetsFor(input.observation),
    outcomeLearningMandatory: true,
  };
}

export function evaluateFailureRepair(input: {
  causeIdentified: boolean;
  patchAddressesCause: boolean;
  mitigationOnlyJustified?: boolean;
}): { acceptable: boolean; reason: string; nextSequence: readonly string[] } {
  const gate = rootCauseRepairGate({
    causeIdentified: input.causeIdentified,
    patchAddressesCause: input.patchAddressesCause,
    mitigationOnlyJustified: input.mitigationOnlyJustified ?? false,
  });
  return {
    acceptable: gate.acceptable,
    reason: gate.reason,
    nextSequence: gate.acceptable
      ? ['run-targeted-regression', 'run-full-no-regression-court', 'capture-repair-learning']
      : ['reproduce-again', 'generate-new-causal-hypotheses', 'falsify-each-hypothesis', 'build-root-cause-repair'],
  };
}

function metricGain(baseline: number | undefined, candidate: number | undefined, lowerIsBetter = false): number {
  if (baseline === undefined || candidate === undefined) return 0;
  if (baseline === 0) return candidate === 0 ? 0 : 0.5;
  const delta = lowerIsBetter ? (baseline - candidate) / Math.abs(baseline) : (candidate - baseline) / Math.abs(baseline);
  return Math.max(0, Math.min(1, delta));
}

export function deriveMeasuredInnovationCandidate(input: {
  candidateId: string;
  baseline: EvolutionMetrics;
  candidate: EvolutionMetrics;
  evidenceRefs: readonly string[];
  novelty: number;
  resilienceGain?: number;
  risk?: number;
  cost?: number;
  reversible?: boolean;
}): InnovationCandidate {
  return {
    candidateId: input.candidateId,
    novelty: input.novelty,
    expectedQualityGain: metricGain(input.baseline.quality, input.candidate.quality),
    expectedLatencyGain: metricGain(input.baseline.latencyMs, input.candidate.latencyMs, true),
    expectedOwnerBurdenGain: metricGain(input.baseline.ownerPrompts, input.candidate.ownerPrompts, true),
    expectedResilienceGain: Math.max(0, Math.min(1, input.resilienceGain ?? 0)),
    risk: Math.max(0, Math.min(1, input.risk ?? 0)),
    cost: Math.max(0, Math.min(1, input.cost ?? 0)),
    reversible: input.reversible ?? true,
    evidenceRefs: [...input.evidenceRefs],
  };
}

export function concludeAlphaOmegaFormationCycle(input: {
  plan: AlphaOmegaEvolutionPlan;
  candidates: readonly InnovationCandidate[];
  court?: GeneralizationCourtInput;
  proofRefs: readonly string[];
}): EvolutionCourtResult {
  if (input.plan.ownerGateReasons.length > 0) {
    return {
      missionId: input.plan.missionId,
      stage: 'OWNER_GATE',
      disposition: 'OWNER_GATE',
      reasons: input.plan.ownerGateReasons,
      nextSequence: ['hold-external-effect', 'prepare-owner-decision-packet'],
    };
  }

  const ranked = rankInnovationCandidates(input.candidates);
  const selected = ranked[0];
  const court = input.court ? runGeneralizationCourt(input.court) : undefined;
  const disposition = anthropicV4Disposition({
    observation: {
      outcomeId: input.plan.innovationSeed.outcomeId,
      kind: input.plan.innovationSeed.sourceKind,
      objective: input.plan.objective,
      expectedState: input.plan.objective,
      observedState: input.plan.innovationSeed.thesis,
      evidenceRefs: input.plan.innovationSeed.evidenceRefs,
    },
    candidateCount: ranked.length,
    courtPassed: court?.promote ?? false,
    proofRefs: input.proofRefs,
  });

  if (!selected) {
    return {
      missionId: input.plan.missionId,
      stage: 'INNOVATE',
      disposition: 'INNOVATE',
      reasons: ['no-qualified-candidate'],
      nextSequence: ['generate-materially-distinct-candidates', 'run-bounded-experiments'],
    };
  }

  if (!court || !court.promote || disposition !== 'PROMOTE_INTERNAL') {
    return {
      missionId: input.plan.missionId,
      stage: 'OMEGA_HOLD',
      disposition: court ? 'HOLD' : 'INNOVATE',
      selectedCandidateId: selected.candidateId,
      reasons: court?.reasons ?? ['generalization-court-required'],
      nextSequence: [
        'mine-court-failure-or-gap',
        'trigger-new-innovation-seed',
        'generate-next-challenger',
        'repeat-court-with-frozen-oracles',
      ],
    };
  }

  return {
    missionId: input.plan.missionId,
    stage: 'OMEGA_PROMOTE_INTERNAL',
    disposition: 'PROMOTE_INTERNAL',
    selectedCandidateId: selected.candidateId,
    reasons: ['generalization-court-passed', 'proof-present', 'internal-authority-only'],
    nextSequence: [
      'capture-success-invariant',
      'generate-harder-success-challenger',
      'search-harness-simplification',
      'evaluate-compatible-learning-diffusion',
    ],
  };
}
