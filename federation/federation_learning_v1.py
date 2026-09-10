"""Privacy-minimised Federation Learning event model and durable ledger."""
from __future__ import annotations


from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable


SCHEMA = "FUSE-FEDERATION-LEARNING-EVENT-V1"




@dataclass(frozen=True, slots=True)
class LearningEvent:
    event_id: str
    timestamp: str
    mission_id: str
    mission_class: str
    prompt_version: str
    prompt_gene_versions: dict[str, str]
    current_maturity: str
    problem_class: str
    route_attempted: str
    winning_route: str
    failed_routes: tuple[str, ...] = ()
    failure_fingerprint: str = ""
    tool_runtime_provider_class: str = ""
    parallelism_available: int = 1
    parallelism_achieved: int = 1
    critical_path_delta: float = 0.0
    completion_delta: float = 0.0
    correctness_delta: float = 0.0
    proof_delta: float = 0.0
    latency_delta: float = 0.0
    cost_delta: float = 0.0
    owner_burden_delta: float = 0.0
    prompt_mutation: tuple[str, ...] = ()
    algorithm_mutation: tuple[str, ...] = ()
    new_regression_test: tuple[str, ...] = ()
    receiver_compatibility: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    rollback_ref: str = ""
    promotion_state: str = "OBSERVED"
    private_chain_of_thought_stored: bool = False


    def validate(self) -> "LearningEvent":
        if self.private_chain_of_thought_stored:
            raise ValueError("PRIVATE_CHAIN_OF_THOUGHT_MUST_NOT_BE_STORED")
        if not self.event_id or not self.mission_id or not self.prompt_version:
            raise ValueError("LEARNING_EVENT_REQUIRED_FIELDS_MISSING")
        if self.parallelism_available < 0 or self.parallelism_achieved < 0:
            raise ValueError("PARALLELISM_INVALID")
        return self


    def body(self) -> dict:
        out = asdict(self)
        out["schema"] = SCHEMA
        return out




class FederationLearningLedger:
    """Append-only hash-linked JSONL ledger.


    The ledger stores distilled operational outcomes only; no hidden reasoning.
    """


    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)


    def _tail_hash(self) -> str:
        if not self.path.exists() or not self.path.stat().st_size:
            return "GENESIS"
        last = self.path.read_text().splitlines()[-1]
        return json.loads(last)["record_sha256"]


    def append(self, event: LearningEvent) -> dict:
        event.validate()
        prev = self._tail_hash()
        record = {"previous_sha256": prev, "event": event.body()}
        raw = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        record_sha = sha256(raw.encode()).hexdigest()
        envelope = {**record, "record_sha256": record_sha}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(envelope, sort_keys=True, ensure_ascii=False) + "\n")
        return envelope


    def verify(self) -> tuple[bool, int]:
        if not self.path.exists():
            return True, 0
        prev = "GENESIS"
        count = 0
        for line in self.path.read_text().splitlines():
            row = json.loads(line)
            if row["previous_sha256"] != prev:
                return False, count
            record = {"previous_sha256": row["previous_sha256"], "event": row["event"]}
            expected = sha256(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
            if row["record_sha256"] != expected:
                return False, count
            prev = row["record_sha256"]
            count += 1
        return True, count




def plan_receiver_propagation(event: LearningEvent, receivers: Iterable[tuple[str, bool, bool, str]]) -> list[dict]:
    event.validate()
    out = []
    allowed = set(event.receiver_compatibility)
    for receiver_id, compatible, regression_green, rollback_ref in receivers:
        if receiver_id not in allowed or not compatible:
            action, reason = "HOLD", "INCOMPATIBLE_OR_NOT_DECLARED"
        elif not regression_green:
            action, reason = "HOLD", "RECEIVER_REGRESSION_NOT_GREEN"
        elif not rollback_ref:
            action, reason = "HOLD", "ROLLBACK_REQUIRED"
        else:
            action, reason = "ELIGIBLE", "COMPATIBLE_GREEN_WITH_ROLLBACK"
        out.append({"receiver_id": receiver_id, "action": action, "reason": reason})
    return out
