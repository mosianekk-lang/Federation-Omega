from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class RealityState:
    intended: dict[str, Any]
    declared: dict[str, Any]
    observed: dict[str, Any]
    proven: dict[str, Any]
    outcome: dict[str, Any]

    def reconcile(self) -> dict[str, Any]:
        return {
            "intent_gap": self.intended != self.observed,
            "declaration_gap": self.declared != self.observed,
            "proof_gap": self.observed != self.proven,
            "outcome_gap": self.proven != self.outcome,
        }


@dataclass
class ActionContract:
    action_id: str
    intent: str
    preconditions: list[str]
    allowed_effects: list[str]
    forbidden_effects: list[str]
    success_evidence: list[str]
    rollback_required: bool = True

    def validate(self, context: dict[str, bool], requested_effects: list[str]) -> dict[str, Any]:
        missing = [item for item in self.preconditions if not context.get(item, False)]
        forbidden = sorted(set(requested_effects) & set(self.forbidden_effects))
        undeclared = sorted(set(requested_effects) - set(self.allowed_effects) - set(self.forbidden_effects))
        return {
            "valid": not missing and not forbidden and not undeclared,
            "missing_preconditions": missing,
            "forbidden_effects": forbidden,
            "undeclared_effects": undeclared,
        }


@dataclass
class Invariant:
    invariant_id: str
    predicate: Callable[[dict[str, Any]], bool]
    severity: str = "HIGH"


class FormalKernel:
    def verify(self, state: dict[str, Any], invariants: list[Invariant]) -> dict[str, Any]:
        failures = [i.invariant_id for i in invariants if not i.predicate(state)]
        return {"valid": not failures, "counterexamples": failures}


@dataclass
class CyberneticController:
    target: float
    degraded_threshold: float
    recovered_threshold: float
    gain: float = 0.5
    mode: str = "HEALTHY"
    failed_repairs: int = 0

    def step(self, observed: float) -> dict[str, Any]:
        error = self.target - observed
        if self.mode == "HEALTHY" and observed < self.degraded_threshold:
            self.mode = "DEGRADED"
        elif self.mode == "DEGRADED" and observed >= self.recovered_threshold:
            self.mode = "HEALTHY"
        correction = max(-1.0, min(1.0, error * self.gain))
        return {"mode": self.mode, "error": error, "correction": correction}

    def record_repair(self, passed: bool) -> dict[str, Any]:
        if passed:
            self.failed_repairs = 0
        else:
            self.failed_repairs += 1
        adapted = False
        if self.failed_repairs >= 3:
            self.gain = max(0.1, self.gain * 0.5)
            self.failed_repairs = 0
            adapted = True
        return {"adapted": adapted, "gain": self.gain}


class CausalMultiversePlanner:
    def select(self, candidates: list[dict[str, Any]], weights: dict[str, float]) -> dict[str, Any]:
        scored = []
        for candidate in candidates:
            metrics = candidate.get("metrics", {})
            score = sum(metrics.get(key, 0.0) * value for key, value in weights.items())
            scored.append({**candidate, "score": score})
        if not scored:
            raise ValueError("at least one candidate is required")
        return max(scored, key=lambda item: item["score"])


@dataclass
class ReliabilityModel:
    attempts: int = 0
    successes: int = 0
    false_completions: int = 0
    estimates: list[tuple[float, bool]] = field(default_factory=list)

    def record(self, confidence: float, success: bool, claimed_complete: bool = False) -> None:
        self.attempts += 1
        self.successes += int(success)
        self.false_completions += int(claimed_complete and not success)
        self.estimates.append((confidence, success))

    def report(self) -> dict[str, Any]:
        success_rate = self.successes / self.attempts if self.attempts else 0.0
        calibration_error = (
            sum(abs(confidence - float(success)) for confidence, success in self.estimates) / len(self.estimates)
            if self.estimates else 0.0
        )
        return {
            "attempts": self.attempts,
            "success_rate": success_rate,
            "false_completions": self.false_completions,
            "calibration_error": calibration_error,
        }


class ConstitutionalCouncil:
    REQUIRED_ROLES = {"architect", "builder", "security", "verifier", "operations", "evidence"}

    def decide(self, votes: dict[str, str]) -> dict[str, Any]:
        missing = sorted(self.REQUIRED_ROLES - set(votes))
        objections = sorted(role for role, vote in votes.items() if vote == "OBJECT")
        approvals = sum(vote == "APPROVE" for vote in votes.values())
        return {
            "valid_quorum": not missing,
            "missing_roles": missing,
            "objections": objections,
            "approved": not missing and not objections and approvals >= 4,
        }


class AlphaOmegaInstitution:
    def evaluate_release(
        self,
        reality: RealityState,
        contract: ActionContract,
        context: dict[str, bool],
        effects: list[str],
        state: dict[str, Any],
        invariants: list[Invariant],
        votes: dict[str, str],
    ) -> dict[str, Any]:
        reality_result = reality.reconcile()
        contract_result = contract.validate(context, effects)
        formal_result = FormalKernel().verify(state, invariants)
        council_result = ConstitutionalCouncil().decide(votes)
        eligible = (
            not any(reality_result.values())
            and contract_result["valid"]
            and formal_result["valid"]
            and council_result["approved"]
        )
        return {
            "eligible": eligible,
            "reality": reality_result,
            "contract": contract_result,
            "formal": formal_result,
            "council": council_result,
        }
