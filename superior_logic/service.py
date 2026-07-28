from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .ecasp import CorpusObject, ECASPRequest
from .runtime import SuperiorLogicRuntime

DB_PATH = os.getenv("SUPERIOR_LOGIC_DB", "/data/superior_logic.db")
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
runtime = SuperiorLogicRuntime(DB_PATH)
app = FastAPI(title="Federation Omega Superior Logic", version="3.1.0")


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


@app.get("/health")
def health() -> dict:
    state = runtime.snapshot()
    return {
        "status": "HEALTHY",
        "version": "3.1.0",
        "event_chain_valid": state["event_chain_valid"],
        "event_count": state["event_count"],
        "ecasp_algorithm": "ALG-ECASP-001",
    }


@app.get("/state")
def state() -> dict:
    return runtime.snapshot()


@app.post("/missions")
def create_mission(request: MissionCreate) -> dict:
    mission_id = runtime.create_mission(request.owner, request.instruction)
    return {"status": "MISSION_CREATED", "mission_id": mission_id}


@app.post("/ecasp/evaluate")
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
    return runtime.evaluate_corpus_selection(internal).to_dict()
