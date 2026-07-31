from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Literal

app = FastAPI(title="EvidenceOps Audio Worker", version="0.1.0")

class CanaryRequest(BaseModel):
    run_id: str
    chunk_id: str
    provider: Literal["openai", "google"]
    drive_file_id: str

@app.get("/health")
def health():
    return {"status": "ok", "maturity": "SCAFFOLD"}

@app.post("/transcription/canary")
def transcription_canary(req: CanaryRequest):
    raise HTTPException(status_code=501, detail={
        "state": "ADAPTER_BINDING_REQUIRED",
        "run_id": req.run_id,
        "chunk_id": req.chunk_id,
        "provider": req.provider
    })
