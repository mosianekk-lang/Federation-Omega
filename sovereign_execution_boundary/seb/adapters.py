from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from urllib import error, request


class AdapterUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class OpaDecision:
    allowed: bool
    raw: dict


class OpaHttpAdapter:
    def __init__(self, url: str = "http://127.0.0.1:8181/v1/data/seb/decision", timeout: float = 3.0):
        self.url, self.timeout = url, timeout

    def decide(self, input_document: dict) -> OpaDecision:
        req = request.Request(self.url, data=json.dumps({"input": input_document}).encode(),
                              method="POST", headers={"Content-Type": "application/json"})
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = json.loads(response.read())
        except (error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise AdapterUnavailable("OPA decision endpoint unavailable") from exc
        result = raw.get("result")
        if not isinstance(result, dict) or type(result.get("allow")) is not bool:
            raise AdapterUnavailable("OPA returned an invalid decision document")
        reasons = result.get("reasons")
        if not isinstance(reasons, list) or any(not isinstance(item, str) for item in reasons):
            raise AdapterUnavailable("OPA returned invalid decision reasons")
        if result["allow"] and reasons:
            raise AdapterUnavailable("OPA returned a contradictory decision")
        return OpaDecision(result["allow"], raw)

    @staticmethod
    def decision_digest(input_document: dict, raw: dict) -> str:
        body = json.dumps({"input": input_document, "response": raw}, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)
        return sha256(body.encode()).hexdigest()


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
        from .spiffe_mtls import validate_spiffe_id
        identity = validate_spiffe_id(self.spiffe_id)
        if identity.split("/", 3)[2] != trust_domain:
            raise ValueError("workload identity outside trust domain")
