from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .state import DurableState


PROFILES: Dict[str, Dict[str, List[str]]] = {
    "legal_email_review": {
        "specialists": ["Lex", "LabourProcedure", "Ledger"],
        "connectors": ["Gmail", "Google Drive"],
        "excluded": ["Canva", "GitHub", "Cloud", "Calendar"],
    },
    "legal_case_analysis": {
        "specialists": ["Lex", "LabourProcedure", "Ledger"],
        "connectors": ["Google Drive"],
        "excluded": ["Canva", "GitHub", "Cloud"],
    },
    "software_build": {
        "specialists": ["Bubbles", "Forge", "Patch", "Ledger"],
        "connectors": ["GitHub"],
        "excluded": ["Canva", "Gmail"],
    },
    "cloud_deployment": {
        "specialists": ["Bubbles", "Sparks", "Sentinel", "Ledger"],
        "connectors": ["GitHub", "Cloud"],
        "excluded": ["Canva", "Gmail"],
    },
    "general": {
        "specialists": ["Bubbles", "Ledger"],
        "connectors": [],
        "excluded": [],
    },
}


COGNITIVE_PRECISION_SIGNALS = (
    "legal", "disciplinary", "labour", "ccma", "arbitration", "suspension", "grievance",
    "medical", "financial", "forensic", "evidence", "causal", "root cause", "contradiction",
    "strategy", "architecture", "system design", "high-risk", "high risk", "irreversible",
    "compare", "competing", "hypothesis", "falsify", "adversarial", "integrity", "provenance",
)


def _stable_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def _sha(value: Any) -> str:
    return hashlib.sha256(_stable_json(value)).hexdigest()


def classify_mission(objective: str) -> str:
    text = objective.lower()
    legal = any(x in text for x in ("legal", "disciplinary", "labour", "ccma", "arbitration", "suspension", "grievance"))
    email = any(x in text for x in ("email", "gmail", "mail", "message", "joel", "pule"))
    if legal and email:
        return "legal_email_review"
    if any(x in text for x in ("deploy", "cloud run", "provider runtime", "production", "canary")):
        return "cloud_deployment"
    if legal:
        return "legal_case_analysis"
    if any(x in text for x in ("build", "code", "github", "runtime", "api", "software")):
        return "software_build"
    return "general"


@dataclass
class MissionPlan:
    mission_id: str
    objective: str
    mission_type: str
    active_specialists: List[str]
    active_connectors: List[str]
    excluded_connectors: List[str]
    retrieval_budget: int
    tool_result_token_budget: int
    max_parallel_lanes: int
    created_at: str
    cognitive_precision_required: bool = False
    plan_sha256: str = ""


class AdaptiveBudgeter:
    """Use observed latency and failure pressure to tighten or relax work budgets."""

    def __init__(self, state: DurableState) -> None:
        self.state = state

    def retrieval_budget(self) -> int:
        latency = self.state.metric("connector.latency_ms")
        failure = self.state.metric("connector.failure_rate")
        budget = 3
        if latency is not None and latency > 1500:
            budget -= 1
        elif latency is not None and latency < 300:
            budget += 1
        if failure is not None and failure > 0.20:
            budget -= 1
        return max(2, min(8, budget))

    def token_budget(self) -> int:
        latency = self.state.metric("connector.latency_ms")
        budget = 4000
        if latency is not None and latency > 1500:
            budget = 3000
        elif latency is not None and latency < 300:
            budget = 5000
        return max(2000, min(8000, budget))


class MissionCompiler:
    def __init__(self, state: DurableState) -> None:
        self.state = state
        self.budgeter = AdaptiveBudgeter(state)
        self._cognitive_kernel = None

    @staticmethod
    def needs_cognitive_precision(
        objective: str,
        *,
        candidate_count: int = 0,
        risk_level: str = "",
    ) -> bool:
        text = objective.lower()
        risk = risk_level.upper().strip()
        return (
            candidate_count >= 2
            or risk in {"HIGH", "CRITICAL", "IRREVERSIBLE"}
            or any(signal in text for signal in COGNITIVE_PRECISION_SIGNALS)
        )

    def evaluate_decision(
        self,
        *,
        candidates: Sequence[Mapping[str, Any]],
        experiments: Sequence[Mapping[str, Any]] = (),
        context_metrics: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self._cognitive_kernel is None:
            from .cognitive_precision import CognitivePrecisionKernel
            self._cognitive_kernel = CognitivePrecisionKernel()
        return self._cognitive_kernel.compile_decision(
            candidates=candidates,
            experiments=experiments,
            context_metrics=context_metrics,
        )

    def compile(
        self,
        objective: str,
        *,
        mission_id: Optional[str] = None,
        mission_type: Optional[str] = None,
        required_specialists: Optional[Sequence[str]] = None,
        required_connectors: Optional[Sequence[str]] = None,
    ) -> MissionPlan:
        kind = mission_type or classify_mission(objective)
        profile = PROFILES.get(kind, PROFILES["general"])
        specialists = list(dict.fromkeys(required_specialists or profile["specialists"]))
        connectors = list(dict.fromkeys(required_connectors or profile["connectors"]))
        excluded = [c for c in profile["excluded"] if c not in connectors]
        mission_id = mission_id or f"mission_{_sha({'objective': objective, 'time': time.time()})[:16]}"
        base = {
            "mission_id": mission_id,
            "objective": objective,
            "mission_type": kind,
            "active_specialists": specialists,
            "active_connectors": connectors,
            "excluded_connectors": excluded,
            "retrieval_budget": self.budgeter.retrieval_budget(),
            "tool_result_token_budget": self.budgeter.token_budget(),
            "max_parallel_lanes": 4,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cognitive_precision_required": self.needs_cognitive_precision(objective),
        }
        plan = MissionPlan(**base, plan_sha256=_sha(base))
        self.state.save_plan(asdict(plan))
        return plan


class MemoryGovernor:
    """HOT-0 = this response; HOT-1 = mission capsule; WARM/COLD remain by pointer."""

    HOT0_MAX_BYTES = 6000
    HOT1_MAX_BYTES = 16000
    HOT1_MAX_EVENTS = 15

    def classify(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        hot0 = {
            "current_question": snapshot.get("current_question", snapshot.get("objective")),
            "needed_facts": snapshot.get("needed_facts", []),
            "needed_source_pointers": snapshot.get("needed_source_pointers", []),
        }
        hot1 = {
            "objective": snapshot.get("objective"),
            "verified_facts": snapshot.get("verified_facts", []),
            "active_source_pointers": snapshot.get("active_source_pointers", []),
            "open_questions": snapshot.get("open_questions", []),
            "decisions": snapshot.get("decisions", []),
            "blockers": snapshot.get("blockers", []),
            "next_action": snapshot.get("next_action"),
            "material_events": snapshot.get("material_events", [])[-self.HOT1_MAX_EVENTS:],
        }
        warm = {
            "project_state_pointer": snapshot.get("project_state_pointer"),
            "verified_cache_pointer": snapshot.get("verified_cache_pointer"),
            "capability_registry_pointer": snapshot.get("capability_registry_pointer"),
        }
        cold = {
            "archive_pointer": snapshot.get("archive_pointer"),
            "policy": "Hydrate raw archive only when a current proof dependency requires it.",
        }
        if len(_stable_json(hot0)) > self.HOT0_MAX_BYTES:
            hot0["needed_facts"] = hot0["needed_facts"][-8:]
            hot0["needed_source_pointers"] = hot0["needed_source_pointers"][-8:]
        result = {"HOT_0": hot0, "HOT_1": hot1, "WARM": warm, "COLD": cold}
        result["capsule_sha256"] = _sha(result)
        return result

    def rollover_required(self, snapshot: Dict[str, Any]) -> bool:
        memory = self.classify(snapshot)
        return (
            len(_stable_json(memory["HOT_1"])) > self.HOT1_MAX_BYTES
            or len(snapshot.get("material_events", [])) > self.HOT1_MAX_EVENTS
        )
