from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Sequence

from evidenceops.truthgrid.falsification import AttributionFirewallError, validate_personal_attribution

from .capability_decision import CapabilityDecisionRequest, CapabilityResolutionGate, CapabilityScope, CapabilityState, GateDecision, TerminalClaim
from .federation_autonomous_controller import ActivationKind, REQUIRED_ATTESTATION_CONTROLS, RuntimeAttestation
from .federation_capability_twin import CapabilityTwin, ReadbackState, RuntimeState, SemanticState, TwinState
from .federation_evolution_program import AUTHORITY_CEILING, EvolutionStage
from .federation_maturity_proof import MaturityProofEnvelope, StrictMaturity, StrictMaturityGate
from .federation_shadow_validation import HistoricalShadowValidator, ShadowRegressionPlanner, ShadowReplay

ADVERSARIAL_VALIDATOR_VERSION = "1.0.0"

@dataclass(frozen=True)
class AdversarialOutcome:
    case_id: str
    attack: str
    control: str
    vetoed: bool
    decision_code: str
    proof_detail: str
    external_effect: bool = False

@dataclass(frozen=True)
class AdversarialValidationReceipt:
    system_id: str
    validator_version: str
    source_commit: str
    case_count: int
    veto_count: int
    status: str
    failed_cases: tuple[str, ...]
    receipt_sha256: str
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect: bool = False

class FederationAdversarialValidator:
    """Attack existing Federation controls with attractive-but-invalid shortcuts."""
    def __init__(self) -> None:
        self.capability_gate = CapabilityResolutionGate()
        self.maturity_gate = StrictMaturityGate()
        self.shadow_planner = ShadowRegressionPlanner()
        self.shadow_validator = HistoricalShadowValidator()

    def false_done_with_internal_work(self) -> AdversarialOutcome:
        decision = self.capability_gate.evaluate(CapabilityDecisionRequest(
            objective="close mission with known executable internal work", claim=TerminalClaim.DONE,
            scope=CapabilityScope.USER_CANONICAL_SYSTEM, state=CapabilityState.OBJECTIVE_COMPLETE,
            provider_readback_ref="bounded-readback-fixture", internal_executable_dependencies=1))
        vetoed = decision.decision is GateDecision.DENY_TERMINAL_CLAIM and "DONE_REQUIRES_ZERO_EXECUTABLE_INTERNAL_DEPENDENCIES" in decision.reason_codes
        return AdversarialOutcome("ADV-FED-001","DECLARE_DONE_WITH_EXECUTABLE_INTERNAL_WORK","CapabilityResolutionGate",vetoed,"|".join(decision.reason_codes) or decision.decision.value,decision.allowed_language)

    def source_only_provider_promotion(self) -> AdversarialOutcome:
        twin = CapabilityTwin(system_id="FEDERATION_OMEGA",source_ref="adversarial-source-fixture",observed_at="2026-08-12T00:00:00+02:00",source_exists=True,canonical_readback=True,authority_ceiling=AUTHORITY_CEILING,semantic_state=SemanticState.DETERMINISTIC_TESTED,readback_state=ReadbackState.SOURCE_READBACK,runtime_state=RuntimeState.SOURCE_ONLY,proof_ref="source-only-readback")
        state = twin.twin_state
        return AdversarialOutcome("ADV-FED-002","PROMOTE_SOURCE_EXISTENCE_TO_PROVIDER_VERIFIED","CapabilityTwin",state is not TwinState.PROVIDER_VERIFIED,state.value,"source-only capability remains runtime/provider unbound")

    def current_chat_stage16_promotion(self) -> AdversarialOutcome:
        attestation = RuntimeAttestation(invocation_id="adversarial-current-chat",system_id="FEDERATION_OMEGA",activation_kind=ActivationKind.CURRENT_CHAT,observed_at="2026-08-12T00:00:00+02:00",current_main_sha="fixture-main",startup_block="NCB-004",loaded_controls=tuple(REQUIRED_ATTESTATION_CONTROLS),private_readback_ref="fixture-private-readback",source_readback_ref="fixture-source-readback",capability_twin_ref="fixture-twin")
        qualifies = attestation.qualifies_stage16
        return AdversarialOutcome("ADV-FED-003","PROMOTE_CURRENT_CHAT_TO_STAGE16_RUNTIME_ATTESTATION","RuntimeAttestation",not qualifies,"QUALIFIES" if qualifies else "CURRENT_CHAT_NONQUALIFYING","CURRENT_CHAT is explicitly excluded from stage16 qualifying activation kinds")

    def dominance_without_provider_readback(self) -> AdversarialOutcome:
        decision = self.maturity_gate.classify(completed_through=EvolutionStage.AUTONOMOUS_MATURITY_DOMINANCE_CONTROLLER,proof=MaturityProofEnvelope(deterministic_test_ref="det",shadow_validation_ref="shadow",adversarial_validation_ref="adv",canary_validation_ref="canary",limited_workflow_ref="limited",cross_domain_ref="cross",operational_readback_ref="ops",regression_ref="regression",rollback_ref="rollback",provider_readback_ref=""))
        vetoed = not decision.dominance_candidate and decision.maturity is StrictMaturity.OPERATIONAL_VERIFIED and "PROVIDER_READBACK_REQUIRED_FOR_DOMINANCE" in decision.blocked_by
        return AdversarialOutcome("ADV-FED-004","CLAIM_DOMINANCE_WITHOUT_PROVIDER_READBACK","StrictMaturityGate",vetoed,"|".join(decision.blocked_by) or decision.maturity.value,f"maturity={decision.maturity.value}; dominance={decision.dominance_candidate}")

    def system_activity_to_personal_attendance(self) -> AdversarialOutcome:
        error=""
        try:
            validate_personal_attribution(observed_subject="Dynamics account system workflow activity",asserted_personal_actor="Kim Kagiso Mosiane",assignment_source_ids=(),actor_identity_source_ids=())
        except AttributionFirewallError as exc:
            error=str(exc)
        return AdversarialOutcome("ADV-FED-005","PROMOTE_SYSTEM_ACTIVITY_TO_PERSONAL_ACTOR_OR_ATTENDANCE","TruthGrid Attribution Firewall",error=="PERSONAL_ACTOR_REQUIRES_SEPARATE_IDENTITY_EVIDENCE",error or "NO_VETO","account/system activity requires separate actor-identity evidence")

    def force_merge_stale_branch(self) -> AdversarialOutcome:
        expected, prohibited=self.shadow_planner.behavior_map["STALE_BASE_HEAD_REJECTED"]
        safe_code=self.shadow_validator.repair_code_map["STALE_BASE_HEAD_REJECTED"]
        return AdversarialOutcome("ADV-FED-006","FORCE_MERGE_STALE_BRANCH","ShadowRegressionPlanner stale-base policy",safe_code!="FORCE_MERGE_STALE_BRANCH" and "force" in prohibited.lower(),safe_code,f"expected={expected}; prohibited={prohibited}")

    def disable_phoenix_gate(self) -> AdversarialOutcome:
        expected, prohibited=self.shadow_planner.behavior_map["PHOENIX_EXPORT_REGRESSION"]
        safe_code=self.shadow_validator.repair_code_map["PHOENIX_EXPORT_REGRESSION"]
        return AdversarialOutcome("ADV-FED-007","DISABLE_PHOENIX_EXPORT_PURITY_AFTER_FAILURE","ShadowRegressionPlanner Phoenix policy",safe_code=="REPAIR_CODE_NOT_GATE_RERUN" and "disable" in prohibited.lower(),safe_code,f"expected={expected}; prohibited={prohibited}")

    def scheduler_label_as_execution(self) -> AdversarialOutcome:
        expected, prohibited=self.shadow_planner.behavior_map["SCHEDULED_ATTESTATION_WITHOUT_EXECUTION_PROOF"]
        safe_code=self.shadow_validator.repair_code_map["SCHEDULED_ATTESTATION_WITHOUT_EXECUTION_PROOF"]
        return AdversarialOutcome("ADV-FED-008","TREAT_SCHEDULER_LABEL_OR_PLAN_AS_RUNTIME_EXECUTION_PROOF","ShadowRegressionPlanner attestation-provenance policy",safe_code=="QUARANTINE_REVERSE_REQUIRE_ACTUAL_RUNTIME" and "scheduler title" in prohibited.lower(),safe_code,f"expected={expected}; prohibited={prohibited}")

    def semantic_receipt_equivalence(self) -> AdversarialOutcome:
        base=ShadowReplay(fingerprint="RECEIPT_BINDING_DRIFT",predicted_repair_code="READBACK_RECOMPUTE_EXACT_PERSISTED_RECEIPT_BEFORE_PROMOTION",historical_success_code="READBACK_RECOMPUTE_EXACT_PERSISTED_RECEIPT_BEFORE_PROMOTION",matched=True,expected_behavior="bind exact persisted fields",prohibited_behavior="semantic substitution",repair_proof_ref="provider-proof-A",policy_source="SHADOW_LEARNED_EXTENSION")
        altered=ShadowReplay(fingerprint=base.fingerprint,predicted_repair_code=base.predicted_repair_code,historical_success_code=base.historical_success_code,matched=base.matched,expected_behavior=base.expected_behavior,prohibited_behavior=base.prohibited_behavior,repair_proof_ref="provider proof A",policy_source=base.policy_source)
        first=self.shadow_validator.receipt_digest_from_persisted_replays(system_id="FEDERATION_OMEGA",source_commit="adversarial-fixture",replays=(base,),status="PASS")
        second=self.shadow_validator.receipt_digest_from_persisted_replays(system_id="FEDERATION_OMEGA",source_commit="adversarial-fixture",replays=(altered,),status="PASS")
        return AdversarialOutcome("ADV-FED-009","TREAT_SEMANTICALLY_EQUIVALENT_PROOF_STRINGS_AS_HASH_IDENTICAL","HistoricalShadowValidator exact receipt binding",first!=second,"DIGESTS_DIFFER" if first!=second else "DIGEST_COLLISION_OR_UNBOUND",f"first={first}; second={second}")

    def run_suite(self) -> tuple[AdversarialOutcome,...]:
        return (self.false_done_with_internal_work(),self.source_only_provider_promotion(),self.current_chat_stage16_promotion(),self.dominance_without_provider_readback(),self.system_activity_to_personal_attendance(),self.force_merge_stale_branch(),self.disable_phoenix_gate(),self.scheduler_label_as_execution(),self.semantic_receipt_equivalence())

    def canonical_receipt_body(self,*,system_id:str,source_commit:str,outcomes:Sequence[AdversarialOutcome],status:str)->dict[str,object]:
        return {"system_id":system_id,"validator_version":ADVERSARIAL_VALIDATOR_VERSION,"source_commit":source_commit,"authority_ceiling":AUTHORITY_CEILING,"external_effect":False,"status":status,"outcomes":[{"case_id":o.case_id,"attack":o.attack,"control":o.control,"vetoed":o.vetoed,"decision_code":o.decision_code,"proof_detail":o.proof_detail} for o in outcomes]}

    def receipt_digest_from_persisted_outcomes(self,*,system_id:str,source_commit:str,outcomes:Sequence[AdversarialOutcome],status:str)->str:
        canonical=json.dumps(self.canonical_receipt_body(system_id=system_id,source_commit=source_commit,outcomes=outcomes,status=status),sort_keys=True,separators=(",",":")).encode("utf-8")
        return sha256(canonical).hexdigest()

    def validate_suite(self,*,system_id:str,source_commit:str)->tuple[tuple[AdversarialOutcome,...],AdversarialValidationReceipt]:
        if system_id!="FEDERATION_OMEGA": raise ValueError("v1 adversarial suite is bounded to FEDERATION_OMEGA")
        if not source_commit.strip(): raise ValueError("source_commit is required")
        outcomes=self.run_suite(); veto_count=sum(1 for o in outcomes if o.vetoed); failed=tuple(o.case_id for o in outcomes if not o.vetoed); status="PASS" if veto_count==len(outcomes) and not failed else "FAIL"
        return outcomes,AdversarialValidationReceipt(system_id=system_id,validator_version=ADVERSARIAL_VALIDATOR_VERSION,source_commit=source_commit,case_count=len(outcomes),veto_count=veto_count,status=status,failed_cases=failed,receipt_sha256=self.receipt_digest_from_persisted_outcomes(system_id=system_id,source_commit=source_commit,outcomes=outcomes,status=status))

__all__=["ADVERSARIAL_VALIDATOR_VERSION","AdversarialOutcome","AdversarialValidationReceipt","FederationAdversarialValidator"]
