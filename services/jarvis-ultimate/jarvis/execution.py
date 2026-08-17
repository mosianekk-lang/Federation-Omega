from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Callable, Mapping, Sequence


MAX_DIRECTIVE_SECONDS = 20 * 60
SPLIT_TRIGGER_SECONDS = 12 * 60
EXPANSION_CUTOFF_SECONDS = 15 * 60
FORCE_RELEASE_SECONDS = 18 * 60
MIN_SPEED_TARGET_SECONDS = 5 * 60
MAX_ACTIVE_PATHS = 3
MAX_ACTIVE_STREAMS = 6
EVIDENCE_MAX_AGE_SECONDS = 24 * 60 * 60

TRUSTED_SOURCE_CLASSES = frozenset(
    {
        "TRUSTED_LOCAL",
        "TEST_HARNESS",
        "PROVIDER_READBACK",
        "INDEPENDENT_VERIFIER",
        "SIGNED_RECEIPT",
    }
)

REQUIRED_QUALITY_GATES = (
    "OBJECTIVE_FORM_LOCK",
    "SOURCE_FIDELITY",
    "IMPLEMENTATION_OR_RESULT",
    "TEST_OR_VALIDATION",
    "ADVERSARIAL_CHECK",
    "SEMANTIC_READBACK",
    "KNOWN_FAILURE_REPLAY",
    "TRUTHFUL_COMPLETION_CLAIM",
    "NEXT_AUTOMATED_PATHWAY",
)

KNOWN_FAILURE_GENOMES = (
    "FALSE_PROGRESS",
    "FALSE_CAPABILITY_NEGATION",
    "LOCAL_AS_PROVIDER_DELIVERY",
    "SOURCE_OR_TEST_AS_DEPLOYMENT",
    "FALSE_BACKGROUND_WORK",
    "FORM_DRIFT",
    "MATURITY_INFLATION",
    "APOLOGY_WITHOUT_MISSION_RESUMPTION",
    "ADVISORY_RULE_AS_ENFORCED",
    "OWNER_BURDEN_TRANSFER",
    "WEAKER_TERMINAL_STATE_SUBSTITUTION",
    "UNCHANGED_RETRY_AFTER_NO_OP",
)

ROUTE_STATES = frozenset({"SUCCESS", "FAILURE", "BLOCKED", "NO_OP", "UNVERIFIED"})


class ExecutionEvidenceError(ValueError):
    """Raised when a completion or improvement claim lacks typed evidence."""


class TimeboxState(str, Enum):
    GREEN = "GREEN"
    SPLIT_REQUIRED = "SPLIT_REQUIRED"
    CONVERGENCE_ONLY = "CONVERGENCE_ONLY"
    RELEASE_ONLY = "RELEASE_ONLY"
    DEADLINE_REACHED = "DEADLINE_REACHED"


class CompletionState(str, Enum):
    COMPLETE_VERIFIED = "COMPLETE_VERIFIED"
    BOUNDED_COMPLETE = "BOUNDED_COMPLETE"
    BLOCKED_WITH_EXECUTABLE_NEXT_ROUTE = "BLOCKED_WITH_EXECUTABLE_NEXT_ROUTE"


@dataclass(frozen=True)
class PhaseBudget:
    id: str
    max_seconds: int
    terminal_fruit: str


@dataclass(frozen=True)
class ExecutionPath:
    id: str
    path_class: str
    objective: str
    streams: tuple[str, ...]
    exit_condition: str


@dataclass(frozen=True)
class QualityEvidence:
    gate: str
    passed: bool
    source_class: str
    proof_ref: str
    semantic_digest: str
    observed_at: int
    independent: bool

    @classmethod
    def from_mapping(
        cls,
        gate: str,
        value: Mapping[str, Any] | bool,
        *,
        now: int,
    ) -> "QualityEvidence":
        if isinstance(value, bool) or not isinstance(value, Mapping):
            raise ExecutionEvidenceError(f"QUALITY_GATE_EVIDENCE_OBJECT_REQUIRED:{gate}")
        required = {"passed", "sourceClass", "proofRef", "semanticDigest", "observedAt", "independent"}
        missing = sorted(required - set(value))
        if missing:
            raise ExecutionEvidenceError(f"QUALITY_GATE_EVIDENCE_FIELDS_MISSING:{gate}:{','.join(missing)}")
        passed = value["passed"]
        independent = value["independent"]
        observed_at = value["observedAt"]
        if not isinstance(passed, bool) or not isinstance(independent, bool):
            raise ExecutionEvidenceError(f"QUALITY_GATE_BOOLEAN_FIELDS_INVALID:{gate}")
        if isinstance(observed_at, bool) or not isinstance(observed_at, int):
            raise ExecutionEvidenceError(f"QUALITY_GATE_OBSERVED_AT_INVALID:{gate}")
        source_class = str(value["sourceClass"]).strip().upper()
        proof_ref = str(value["proofRef"]).strip()
        semantic_digest = str(value["semanticDigest"]).strip().lower()
        if source_class not in TRUSTED_SOURCE_CLASSES:
            raise ExecutionEvidenceError(f"QUALITY_GATE_SOURCE_UNTRUSTED:{gate}")
        if not proof_ref or len(proof_ref) > 2048:
            raise ExecutionEvidenceError(f"QUALITY_GATE_PROOF_REF_INVALID:{gate}")
        if not re.fullmatch(r"[0-9a-f]{64}", semantic_digest):
            raise ExecutionEvidenceError(f"QUALITY_GATE_DIGEST_INVALID:{gate}")
        if observed_at > now + 30:
            raise ExecutionEvidenceError(f"QUALITY_GATE_EVIDENCE_FROM_FUTURE:{gate}")
        if now - observed_at > EVIDENCE_MAX_AGE_SECONDS:
            raise ExecutionEvidenceError(f"QUALITY_GATE_EVIDENCE_STALE:{gate}")
        if gate == "ADVERSARIAL_CHECK" and not independent:
            raise ExecutionEvidenceError("ADVERSARIAL_CHECK_INDEPENDENCE_REQUIRED")
        return cls(gate, passed, source_class, proof_ref, semantic_digest, observed_at, independent)


@dataclass(frozen=True)
class RouteResult:
    route_id: str
    state: str
    state_delta: str
    proof_ref: str
    next_route: str | None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RouteResult":
        if not isinstance(value, Mapping):
            raise ExecutionEvidenceError("ROUTE_RESULT_OBJECT_REQUIRED")
        required = {"routeId", "state", "stateDelta", "proofRef"}
        missing = sorted(required - set(value))
        if missing:
            raise ExecutionEvidenceError("ROUTE_RESULT_FIELDS_MISSING:" + ",".join(missing))
        route_id = str(value["routeId"]).strip()
        state = str(value["state"]).strip().upper()
        state_delta = str(value["stateDelta"]).strip()
        proof_ref = str(value["proofRef"]).strip()
        next_route_value = value.get("nextRoute")
        next_route = str(next_route_value).strip() if next_route_value is not None else None
        if not route_id or len(route_id) > 256:
            raise ExecutionEvidenceError("ROUTE_ID_INVALID")
        if state not in ROUTE_STATES:
            raise ExecutionEvidenceError(f"ROUTE_STATE_INVALID:{route_id}")
        if state == "SUCCESS" and (not state_delta or state_delta.upper() in {"NONE", "NO_CHANGE", "UNKNOWN"}):
            raise ExecutionEvidenceError(f"SUCCESS_ROUTE_REQUIRES_STATE_DELTA:{route_id}")
        if state == "SUCCESS" and not proof_ref:
            raise ExecutionEvidenceError(f"SUCCESS_ROUTE_REQUIRES_PROOF:{route_id}")
        if state in {"FAILURE", "BLOCKED", "NO_OP", "UNVERIFIED"} and not next_route:
            raise ExecutionEvidenceError(f"EXECUTABLE_NEXT_ROUTE_REQUIRED:{route_id}")
        return cls(route_id, state, state_delta, proof_ref, next_route)


@dataclass(frozen=True)
class ExecutionPolicy:
    id: str
    lesson_gate_id: str
    max_directive_seconds: int
    split_trigger_seconds: int
    expansion_cutoff_seconds: int
    force_release_seconds: int
    max_active_paths: int
    max_active_streams: int
    completion_states: tuple[str, ...]
    quality_gates: tuple[str, ...]
    known_failure_genomes: tuple[str, ...]
    guarantee_scope: str
    external_limit: str
    email_send_rule: str
    improvement_rule: str


class TwentyMinuteGovernor:
    """Proof-bearing Alpha–Omega governor for one bounded execution attempt.

    The governor controls scope, fan-out, convergence and release. It never
    converts elapsed time or caller assertions into completion proof, cannot
    make an external provider respond faster, and never grants effect authority.
    """

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self.policy = ExecutionPolicy(
            id="T20-AO-OMEGA-SCIENTIST-1.1",
            lesson_gate_id="FEDERATION-72H-LESSON-GATE-20260817",
            max_directive_seconds=MAX_DIRECTIVE_SECONDS,
            split_trigger_seconds=SPLIT_TRIGGER_SECONDS,
            expansion_cutoff_seconds=EXPANSION_CUTOFF_SECONDS,
            force_release_seconds=FORCE_RELEASE_SECONDS,
            max_active_paths=MAX_ACTIVE_PATHS,
            max_active_streams=MAX_ACTIVE_STREAMS,
            completion_states=tuple(state.value for state in CompletionState),
            quality_gates=REQUIRED_QUALITY_GATES,
            known_failure_genomes=KNOWN_FAILURE_GENOMES,
            guarantee_scope="ONE_BOUNDED_JARVIS_EXECUTION_ATTEMPT",
            external_limit=(
                "EXTERNAL_PROVIDER_LATENCY, HUMAN APPROVAL AND THIRD_PARTY EFFECTS CANNOT BE FORCED; "
                "UNRESOLVED DEPENDENCIES MUST BE ISOLATED AND RELEASED WITH AN EXECUTABLE NEXT ROUTE"
            ),
            email_send_rule=(
                "GMAIL_SEND_AND_FORWARD_REQUIRE_EXPLICIT_CURRENT_OWNER_GRANT_PLUS_EXECUTOR_ONLY "
                "AUTHORITY_INTERSECTION_AND_SINGLE_USE_PERMIT"
            ),
            improvement_rule="PROMOTE_SPEED_GAIN_ONLY_AFTER PROOF-BEARING REGRESSION WITH NO QUALITY LOSS",
        )

    def describe(self) -> dict[str, Any]:
        return asdict(self.policy)

    def build_plan(
        self,
        mission_id: str,
        objective: str,
        deliverable_form: str | None = None,
        expected_state_delta: str | None = None,
    ) -> dict[str, Any]:
        mission_id = mission_id.strip()
        objective = objective.strip()
        deliverable = (deliverable_form or "USER_REQUESTED_FORM").strip()
        delta = (expected_state_delta or "VERIFIED_STATE_DELTA_REQUIRED").strip()
        if not mission_id:
            raise ExecutionEvidenceError("MISSION_REQUIRED")
        if not objective:
            raise ExecutionEvidenceError("OBJECTIVE_REQUIRED")
        if not deliverable:
            raise ExecutionEvidenceError("DELIVERABLE_FORM_REQUIRED")
        if not delta:
            raise ExecutionEvidenceError("EXPECTED_STATE_DELTA_REQUIRED")

        started_at = self._clock()
        phases = (
            PhaseBudget("PREFLIGHT", 120, "objective/form lock, current state, authority and proof target"),
            PhaseBudget("PARALLEL_EXECUTION", 600, "minimum sufficient implementation or requested result"),
            PhaseBudget("FAN_IN_AND_ASSURANCE", 300, "integrated tests, failure replay and semantic readback"),
            PhaseBudget("READBACK_AND_RELEASE", 180, "terminal receipt and next automated route"),
        )
        if sum(phase.max_seconds for phase in phases) != self.policy.max_directive_seconds:
            raise RuntimeError("INVALID_PHASE_BUDGET")

        streams = (
            "ST_SOURCE_TRUTH",
            "ST_IMPLEMENTATION",
            "ST_TEST_VALIDATION",
            "ST_ADVERSARIAL_RISK",
            "ST_SEMANTIC_READBACK",
            "ST_METHOD_LEARNING",
        )
        paths = (
            ExecutionPath(
                "PATH_PRIMARY",
                "PRIMARY",
                "Reach the requested Omega through the shortest currently verified route.",
                ("ST_SOURCE_TRUTH", "ST_IMPLEMENTATION", "ST_TEST_VALIDATION"),
                "Requested result exists in the locked form and decisive claims have proof.",
            ),
            ExecutionPath(
                "PATH_PROTECTIVE",
                "PROTECTIVE",
                "Preserve quality, authority, reversibility, continuity and truth boundaries.",
                ("ST_ADVERSARIAL_RISK", "ST_SEMANTIC_READBACK"),
                "Material risks are repaired, isolated or explicitly bounded.",
            ),
            ExecutionPath(
                "PATH_FALLBACK",
                "FAILURE_RECOVERY",
                "Isolate a blocker and release the highest-value bounded result without freezing independent work.",
                ("ST_IMPLEMENTATION", "ST_SEMANTIC_READBACK", "ST_METHOD_LEARNING"),
                "A usable bounded result and executable next automated route are released.",
            ),
        )
        return {
            "missionId": mission_id,
            "objective": objective,
            "objectiveLock": {
                "deliverableForm": deliverable,
                "expectedStateDelta": delta,
                "weakerSubstitution": "DENY",
                "maturitySubstitution": "DENY",
            },
            "alpha": {
                "startingState": "LIVE_REQUEST_AND_CURRENT_VERIFIED_SOURCES",
                "assumptionPolicy": "NOTHING_MATERIAL_ASSUMED",
                "staleProofPolicy": "EXPIRE_AND_REVERIFY",
            },
            "omega": {
                "primary": "REQUESTED_RESULT_COMPLETE_AND_VERIFIED_IN_LOCKED_FORM",
                "protective": "QUALITY_AUTHORITY_AND_REVERSIBILITY_PRESERVED",
                "fallback": "BOUNDED_RESULT_PLUS_EXECUTABLE_NEXT_AUTOMATED_ROUTE",
            },
            "startedAt": started_at,
            "deadlineAt": started_at + self.policy.max_directive_seconds,
            "phases": [asdict(phase) for phase in phases],
            "paths": [asdict(path) for path in paths],
            "streams": list(streams),
            "controls": {
                "fanOut": "ONLY_GENUINELY_INDEPENDENT_WORK",
                "fanIn": "MANDATORY_BEFORE_COMPLETION_CLAIM",
                "routeAccounting": "PER_ROUTE_SUCCESS_FAILURE_BLOCKED_NO_OP_OR_UNVERIFIED",
                "noOpCircuit": "FIRST_ZERO_DELTA_PROHIBITS_UNCHANGED_RETRY",
                "splitAtSeconds": self.policy.split_trigger_seconds,
                "stopExpansionAtSeconds": self.policy.expansion_cutoff_seconds,
                "forceReleaseAtSeconds": self.policy.force_release_seconds,
                "deadlineAction": "EMIT_HONEST_TERMINAL_RECEIPT_NEVER_FALSE_COMPLETION",
                "emailSend": self.policy.email_send_rule,
            },
            "qualityGates": list(self.policy.quality_gates),
            "knownFailureReplay": list(self.policy.known_failure_genomes),
            "allowedCompletionStates": list(self.policy.completion_states),
            "nextBestAutomatedPathwayRequired": True,
        }

    def control_state(self, started_at: float, now: float | None = None) -> dict[str, Any]:
        current = self._clock() if now is None else now
        elapsed = max(0, int(current - started_at))
        if elapsed >= self.policy.max_directive_seconds:
            state = TimeboxState.DEADLINE_REACHED
            action = "TERMINATE_ATTEMPT_AND_EMIT_HONEST_TERMINAL_RECEIPT"
        elif elapsed >= self.policy.force_release_seconds:
            state = TimeboxState.RELEASE_ONLY
            action = "NO_NEW_WORK_VERIFY_READBACK_AND_RELEASE"
        elif elapsed >= self.policy.expansion_cutoff_seconds:
            state = TimeboxState.CONVERGENCE_ONLY
            action = "STOP_SCOPE_EXPANSION_FAN_IN_AND_REPAIR"
        elif elapsed >= self.policy.split_trigger_seconds:
            state = TimeboxState.SPLIT_REQUIRED
            action = "SPLIT_MONOLITH_CONTINUE_ONLY_INDEPENDENT_HIGH_VALUE_LANES"
        else:
            state = TimeboxState.GREEN
            action = "EXECUTE_HIGHEST_INFORMATION_AND_DECISION_VALUE_LANES"
        return {
            "state": state.value,
            "elapsedSeconds": elapsed,
            "remainingSeconds": max(0, self.policy.max_directive_seconds - elapsed),
            "requiredAction": action,
        }

    def review_cycle(
        self,
        elapsed_seconds: int,
        quality_evidence: Mapping[str, Mapping[str, Any] | bool],
        route_results: Sequence[Mapping[str, Any]],
        next_best_automated_pathway: str,
        retries: int = 0,
    ) -> dict[str, Any]:
        if isinstance(elapsed_seconds, bool) or not isinstance(elapsed_seconds, int) or elapsed_seconds < 0:
            raise ExecutionEvidenceError("ELAPSED_SECONDS_INVALID")
        if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0:
            raise ExecutionEvidenceError("RETRIES_INVALID")
        if not isinstance(quality_evidence, Mapping):
            raise ExecutionEvidenceError("QUALITY_EVIDENCE_OBJECT_REQUIRED")
        if isinstance(route_results, (str, bytes)) or not isinstance(route_results, Sequence) or not route_results:
            raise ExecutionEvidenceError("ROUTE_RESULTS_REQUIRED")
        next_path = next_best_automated_pathway.strip()
        if not next_path:
            raise ExecutionEvidenceError("NEXT_BEST_AUTOMATED_PATHWAY_REQUIRED")

        now = int(self._clock())
        missing = [gate for gate in self.policy.quality_gates if gate not in quality_evidence]
        if missing:
            raise ExecutionEvidenceError("MISSING_QUALITY_GATES:" + ",".join(missing))
        evidence = [
            QualityEvidence.from_mapping(gate, quality_evidence[gate], now=now)
            for gate in self.policy.quality_gates
        ]
        routes = [RouteResult.from_mapping(value) for value in route_results]
        route_ids = [route.route_id for route in routes]
        if len(route_ids) != len(set(route_ids)):
            raise ExecutionEvidenceError("DUPLICATE_ROUTE_ID")

        failed_gates = [row.gate for row in evidence if not row.passed]
        success_routes = [row.route_id for row in routes if row.state == "SUCCESS"]
        open_routes = [row.route_id for row in routes if row.state in {"FAILURE", "BLOCKED", "UNVERIFIED"}]
        no_op_routes = [row.route_id for row in routes if row.state == "NO_OP"]
        deadline_pass = elapsed_seconds <= self.policy.max_directive_seconds
        quality_pass = not failed_gates
        meaningful_delta = bool(success_routes)
        cycle_pass = deadline_pass and quality_pass and meaningful_delta

        if cycle_pass and not open_routes and not no_op_routes:
            completion = CompletionState.COMPLETE_VERIFIED
            release_decision = "MERGE"
        elif cycle_pass:
            completion = CompletionState.BOUNDED_COMPLETE
            release_decision = "HOLD"
        else:
            completion = CompletionState.BLOCKED_WITH_EXECUTABLE_NEXT_ROUTE
            release_decision = "REPAIR" if (failed_gates or no_op_routes or not deadline_pass) else "HOLD"

        if completion is CompletionState.COMPLETE_VERIFIED:
            candidate = max(MIN_SPEED_TARGET_SECONDS, int(elapsed_seconds * 0.95))
            promotion = "SHADOW_CANDIDATE" if candidate < elapsed_seconds else "FLOOR_REACHED"
            repair = "NONE"
        elif failed_gates:
            candidate = self.policy.max_directive_seconds
            promotion = "REJECTED"
            repair = "REPAIR_FAILED_QUALITY_GATES_BEFORE_SPEED_OPTIMISATION"
        elif no_op_routes:
            candidate = self.policy.max_directive_seconds
            promotion = "REJECTED"
            repair = "OPEN_NO_OP_CIRCUIT_AND_CHANGE_ROUTE_BEFORE_RETRY"
        elif not deadline_pass:
            candidate = self.policy.max_directive_seconds
            promotion = "REJECTED"
            repair = "DECOMPOSE_EARLIER_AND_REDUCE_ACTIVE_DEPENDENCIES"
        else:
            candidate = self.policy.max_directive_seconds
            promotion = "HELD"
            repair = "PRESERVE_SUCCESSFUL_ROUTES_AND_RESOLVE_ONLY_OPEN_LANES"

        result: dict[str, Any] = {
            "policyId": self.policy.id,
            "lessonGateId": self.policy.lesson_gate_id,
            "cyclePass": cycle_pass,
            "deadlinePass": deadline_pass,
            "qualityPass": quality_pass,
            "meaningfulStateDelta": meaningful_delta,
            "completionState": completion.value,
            "releaseDecision": release_decision,
            "failedQualityGates": failed_gates,
            "successfulRoutes": success_routes,
            "openRoutes": open_routes,
            "noOpRoutes": no_op_routes,
            "noOpCircuitOpened": bool(no_op_routes),
            "retries": retries,
            "qualityEvidence": [asdict(row) for row in evidence],
            "routeResults": [asdict(row) for row in routes],
            "knownFailureGenomesReplayed": list(self.policy.known_failure_genomes),
            "nextBestAutomatedPathway": next_path,
            "emailSendRule": self.policy.email_send_rule,
            "omegaScientist": {
                "promotionState": promotion,
                "candidateNextTargetSeconds": candidate,
                "rule": self.policy.improvement_rule,
                "repair": repair,
            },
        }
        result["receiptDigest"] = hashlib.sha256(
            json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return result
