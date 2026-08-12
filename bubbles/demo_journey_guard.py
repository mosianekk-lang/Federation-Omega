from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


DEFAULT_JOURNEYS = Path(__file__).resolve().parent / "demo_journeys.json"


class DemoJourneyGuard:
    def __init__(self, payload: Mapping[str, Any]):
        self.payload = dict(payload)
        self.journeys = {str(j["journey_id"]): dict(j) for j in payload["journeys"]}
        if len(self.journeys) != len(payload["journeys"]):
            raise ValueError("journey IDs must be unique")
        for journey in self.journeys.values():
            if not journey.get("safe_data_only"):
                raise ValueError("portfolio demo journeys must be safe-data-only")
            step_ids = [str(step["id"]) for step in journey["steps"]]
            if len(step_ids) != len(set(step_ids)):
                raise ValueError("step IDs must be unique within a journey")

    @classmethod
    def load(cls, path: str | Path = DEFAULT_JOURNEYS) -> "DemoJourneyGuard":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def assess(self, journey_id: str, proofs: Mapping[str, str]) -> dict[str, Any]:
        journey = self.journeys[journey_id]
        required = tuple(str(item) for item in journey["completion_requirements"])
        missing = tuple(item for item in required if not str(proofs.get(item, "")).strip())
        complete = not missing
        return {
            "journey_id": journey_id,
            "project_id": journey["project_id"],
            "complete": complete,
            "missing_proofs": list(missing),
            "execution_state": journey["execution_state"] if not complete else "DEMO_PROOF_COMPLETE",
            "truth_boundary": journey["truth_boundary"],
        }

    def k10_render_claim_allowed(self, proofs: Mapping[str, str]) -> bool:
        result = self.assess("DEMO-K10-SAFE-001", proofs)
        return bool(result["complete"] and proofs.get("rendered_asset_ref") and proofs.get("export_receipt"))

    def ipep_result_is_safe(self, result: Mapping[str, Any]) -> bool:
        required = {"source_item_id", "segment_id", "start_seconds", "end_seconds", "review_state", "citation"}
        return required.issubset(result) and bool(str(result.get("citation", "")).startswith("audio:"))
