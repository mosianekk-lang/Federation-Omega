from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .runtime import SuperiorLogicRuntime

DB_PATH = os.getenv("SUPERIOR_LOGIC_DB", "/data/superior_logic.db")
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
runtime = SuperiorLogicRuntime(DB_PATH)
app = FastAPI(title="Federation Omega Superior Logic", version="3.0.0")


class MissionCreate(BaseModel):
    owner: str = "Kim Kagiso Mosiane"
    instruction: str = Field(min_length=1)


@app.get("/health")
def health() -> dict:
    state = runtime.snapshot()
    return {
        "status": "HEALTHY",
        "version": "3.0.0",
        "event_chain_valid": state["event_chain_valid"],
        "event_count": state["event_count"],
    }


@app.get("/state")
def state() -> dict:
    return runtime.snapshot()


@app.post("/missions")
def create_mission(request: MissionCreate) -> dict:
    mission_id = runtime.create_mission(request.owner, request.instruction)
    return {"status": "MISSION_CREATED", "mission_id": mission_id}
