from __future__ import annotations

import atexit
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .ecasp import (
    CorpusActivationState,
    CorpusObject,
    CorpusPreservationState,
    ECASPRequest,
)
from .runtime import SuperiorLogicRuntime
from .slrk import (
    ActivationState,
    CapabilityContract,
    CapabilityState,
    EngineEnvironment,
    EnginePromotionRequest,
    FaultRecord,
    FaultSeverity,
    PreservationState,
    ProofLevel,
)

SERVICE_VERSION = "3.2.0"


class MissionCreate(BaseModel):
    owner: str = "Kim Kagiso Mosiane"
    instruction: str = Field(min_length=1)


class CorpusObjectModel(BaseModel):
    object_id: str = Field(min_length=1)
    discovered: bool = True
    indexed: bool = False
    body_retrieved: bool = False
    parsed: bool = False
    material_attachments_expected: int = Field(default=0, ge=0)
    material_attachments_processed: int = Field(default=0, ge=0)
    module_decomposed: bool = False
    deduped: bool = False
    version_reconciled: bool = False
    conflict_tested: bool = False
    requirement_coverage_tested: bool = False
    selected_or_rejected: bool = False
    verified: bool = False
    excluded_as_immaterial: bool = False
    exclusion_reason: str | None = None
    preservation_state: CorpusPreservationState = CorpusPreservationState.FULL_PRESERVED
    activation_state: CorpusActivationState = CorpusActivationState.PRESERVED_DORMANT
    permanent_exclusion_requested: bool = False
    owner_decision_reference: str | None = None
    preservation_copy_reference: str | None = None


class ECASPEvaluateModel(BaseModel):
    instruction: str = Field(min_length=1)
    intended_claim: str = ""
    expected_object_count: int = Field(gt=0)
    objects: list[CorpusObjectModel]
    capability_universe_mapped: bool = False
    lineage_map_complete: bool = False
    conflict_dependency_matrix_complete: bool = False
    requirement_coverage_complete: bool = False
    counterexample_search_complete: bool = False
    independent_readback_complete: bool = False
    bounded_selection: bool = False
    bounded_scope_description: str | None = None
    unresolved_material_objects_disclosed: bool = False


class CapabilityContractModel(BaseModel):
    capability_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    state: CapabilityState
    can_read: bool = False
    can_write: bool = False
    can_execute: bool = False
    can_verify: bool = False
    authority_required: bool = False
    external_effect: bool = False
    proof_required: str = ""
    fallback_route: str = ""
    preservation_state: PreservationState = PreservationState.FULL_PRESERVED
    activation_state: ActivationState = ActivationState.PRESERVED_DORMANT
    carrier_ids: tuple[str, ...] = ()
    superseded_by: str = ""
    permanent_exclusion_requested: bool = False
    owner_decision_reference: str = ""
    preservation_copy_reference: str = ""


class CapabilityAssessModel(BaseModel):
    required_capabilities: list[str] = Field(min_length=1)


class ClaimGovernModel(BaseModel):
    claim: str = Field(min_length=1)
    proof_level: ProofLevel
    execution_verified: bool = False
    gap_scan_complete: bool = False
    lifecycle_complete: bool = False


class FaultRecordModel(BaseModel):
    fault_id: str = Field(min_length=1)
    layer_type: str = Field(min_length=1)
    detected_problem: str = Field(min_length=1)
    banned_pattern: str = Field(min_length=1)
    bypass_rule: str = Field(min_length=1)
    severity: FaultSeverity
    proof_required: str = Field(min_length=1)
    route_id: str | None = None


class RouteClearModel(BaseModel):
    reason: str = Field(min_length=1)
    conditions_changed: bool = False


class EnginePromotionModel(BaseModel):
    engine_id: str = Field(min_length=1)
    target_environment: EngineEnvironment
    objective: str = Field(min_length=1)
    risk_class: str = Field(min_length=1)
    profile_complete: bool = False
    governor_attached: bool = False
    fault_rules_attached: bool = False
    proof_rules_attached: bool = False
    tests_passed: bool = False
    proof_ledger_written: bool = False
    risk_accepted: bool = False
    rollback_ready: bool = False
    status_path_ready: bool = False
    last_known_good_registered: bool = False
    approval_granted: bool = False
    live_readback_plan_ready: bool = False


def create_app(active_runtime: SuperiorLogicRuntime) -> FastAPI:
    api = FastAPI(title="Federation Omega Superior Logic", version=SERVICE_VERSION)

    @api.get("/health")
    def health() -> dict:
        state = active_runtime.snapshot()
        return {
            "status": "HEALTHY",
            "version": SERVICE_VERSION,
            "event_chain_valid": state["event_chain_valid"],
            "event_count": state["event_count"],
            "ecasp_algorithm": "ALG-ECASP-001",
            "non_dilution_policy": state["non_dilution_policy"],
            "slrk_controls": [
                "CAPABILITY_TRUTH",
                "CLAIM_GOVERNOR",
                "FAULT_ROUTE_MEMORY",
                "ENGINE_PROMOTION_GATE",
                "NON_DILUTION_PRESERVATION",
            ],
        }

    @api.get("/state")
    def state() -> dict:
        return active_runtime.snapshot()

    @api.post("/missions")
    def create_mission(request: MissionCreate) -> dict:
        mission_id = active_runtime.create_mission(request.owner, request.instruction)
        return {"status": "MISSION_CREATED", "mission_id": mission_id}

    @api.post("/ecasp/evaluate")
    def evaluate_corpus(request: ECASPEvaluateModel) -> dict:
        objects = tuple(CorpusObject(**item.model_dump()) for item in request.objects)
        internal = ECASPRequest(
            instruction=request.instruction,
            intended_claim=request.intended_claim,
            expected_object_count=request.expected_object_count,
            objects=objects,
            capability_universe_mapped=request.capability_universe_mapped,
            lineage_map_complete=request.lineage_map_complete,
            conflict_dependency_matrix_complete=request.conflict_dependency_matrix_complete,
            requirement_coverage_complete=request.requirement_coverage_complete,
            counterexample_search_complete=request.counterexample_search_complete,
            independent_readback_complete=request.independent_readback_complete,
            bounded_selection=request.bounded_selection,
            bounded_scope_description=request.bounded_scope_description,
            unresolved_material_objects_disclosed=request.unresolved_material_objects_disclosed,
        )
        return active_runtime.evaluate_corpus_selection(internal).to_dict()

    @api.post("/capabilities/register")
    def register_capability(request: CapabilityContractModel) -> dict:
        try:
            contract = CapabilityContract(**request.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        active_runtime.register_capability(contract)
        return {
            "status": "CAPABILITY_REGISTERED",
            "capability_id": contract.capability_id,
            "capability_state": contract.state.value,
            "preservation_state": contract.preservation_state.value,
            "activation_state": contract.activation_state.value,
            "preserved": contract.preserved,
        }

    @api.post("/capabilities/assess")
    def assess_capability_set(request: CapabilityAssessModel) -> dict:
        return active_runtime.assess_capabilities(tuple(request.required_capabilities)).to_dict()

    @api.post("/claims/govern")
    def govern_claim(request: ClaimGovernModel) -> dict:
        return active_runtime.govern_claim(
            request.claim,
            request.proof_level,
            execution_verified=request.execution_verified,
            gap_scan_complete=request.gap_scan_complete,
            lifecycle_complete=request.lifecycle_complete,
        ).to_dict()

    @api.post("/faults")
    def register_fault(request: FaultRecordModel) -> dict:
        record = FaultRecord(**request.model_dump())
        active_runtime.register_fault(record)
        response = {"status": "FAULT_REGISTERED", "fault_id": record.fault_id}
        if record.route_id:
            response["route"] = active_runtime.route_state(record.route_id)
        return response

    @api.get("/routes/{route_id}")
    def route_state(route_id: str) -> dict:
        return active_runtime.route_state(route_id)

    @api.post("/routes/{route_id}/clear")
    def clear_route(route_id: str, request: RouteClearModel) -> dict:
        try:
            return active_runtime.clear_route(
                route_id, request.reason, conditions_changed=request.conditions_changed
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @api.post("/engines/evaluate-promotion")
    def evaluate_promotion(request: EnginePromotionModel) -> dict:
        internal = EnginePromotionRequest(**request.model_dump())
        return active_runtime.evaluate_engine_promotion(internal).to_dict()

    return api


DB_PATH = os.getenv("SUPERIOR_LOGIC_DB", "/tmp/superior_logic.db")
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
runtime = SuperiorLogicRuntime(DB_PATH)
atexit.register(runtime.close)
app = create_app(runtime)
