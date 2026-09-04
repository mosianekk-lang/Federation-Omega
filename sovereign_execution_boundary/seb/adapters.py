from __future__ import annotations

from dataclasses import dataclass
import json
from urllib import error, request


class AdapterUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class OpaDecision:
    allowed: bool
    raw: dict


class OpaHttpAdapter:
    def __init__(self, url: str = "http://opa:8181/v1/data/seb/allow", timeout: float = 3.0):
        self.url, self.timeout = url, timeout

    def decide(self, input_document: dict) -> OpaDecision:
        req = request.Request(self.url, data=json.dumps({"input": input_document}).encode(),
                              method="POST", headers={"Content-Type": "application/json"})
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = json.loads(response.read())
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AdapterUnavailable("OPA decision endpoint unavailable") from exc
        result = raw.get("result")
        return OpaDecision(bool(result), raw)


@dataclass(frozen=True)
class DurableWorkflowContract:
    workflow_id: str
    objective_fingerprint: str
    task_queue: str = "seb-missions"
    id_reuse_policy: str = "REJECT_DUPLICATE"

    def validate_replay(self, observed_fingerprint: str) -> None:
        if observed_fingerprint != self.objective_fingerprint:
            raise RuntimeError("replay objective drift detected")


@dataclass(frozen=True)
class WorkloadIdentity:
    spiffe_id: str

    def validate(self, trust_domain: str) -> None:
        prefix = f"spiffe://{trust_domain}/"
        if not self.spiffe_id.startswith(prefix):
            raise ValueError("workload identity outside trust domain")
