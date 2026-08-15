from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Callable, Mapping


CANONICAL_SERVICE_ID = "VER-TRU-001"
CANONICAL_NAME = "Veritas-Ω"
CANONICAL_VERSION_FAMILY = "v3.x"
AUTHORITY_CEILING = "A0"
ALLOWED_OPERATIONS = frozenset(
    {
        "ASSESS",
        "FALSIFY",
        "CHECK_CONTRADICTIONS",
        "TRACE_PROVENANCE",
    }
)


@dataclass(frozen=True)
class VeritasRequest:
    request_id: str
    matter_id: str
    operation: str
    objective: str
    source_refs: tuple[str, ...]
    payload: Mapping[str, object]
    authority: str = AUTHORITY_CEILING
    external_effect: bool = False


@dataclass(frozen=True)
class AuthorityDecision:
    allowed: bool
    code: str
    authority: str


@dataclass(frozen=True)
class ExecutionProof:
    request_id: str
    service_id: str
    request_sha256: str
    output_sha256: str
    authority: str
    external_effect: bool
    state: str


class VeritasAdapter:
    """Fail-closed A0 adapter for the canonical Veritas-Ω service.

    The adapter supplies the common EvidenceOps DESCRIBE → ACCEPT → AUTHORISE
    → EXECUTE → PROVE → RECOVER contract.  It does not invent a truth engine:
    callers must provide the currently admitted deterministic evaluator.  The
    evaluator is invoked only after request and authority gates pass.

    This contract creates no provider, filing, legal, evidence-mutation, or
    external-effect authority.  A0 requests are read/analyse/simulate only.
    """

    def __init__(self, evaluator: Callable[[VeritasRequest], Mapping[str, object]]):
        if not callable(evaluator):
            raise TypeError("Veritas evaluator must be callable")
        self._evaluator = evaluator
        self._accepted: dict[str, VeritasRequest] = {}
        self._authorised: set[str] = set()
        self._outputs: dict[str, Mapping[str, object]] = {}

    def describe(self) -> Mapping[str, object]:
        return {
            "service_id": CANONICAL_SERVICE_ID,
            "canonical_name": CANONICAL_NAME,
            "version_family": CANONICAL_VERSION_FAMILY,
            "authority_ceiling": AUTHORITY_CEILING,
            "allowed_operations": tuple(sorted(ALLOWED_OPERATIONS)),
            "external_effect": False,
            "contracts": (
                "DESCRIBE",
                "ACCEPT",
                "AUTHORISE",
                "EXECUTE",
                "PROVE",
                "RECOVER",
            ),
        }

    def accept(self, request: VeritasRequest) -> VeritasRequest:
        if not request.request_id.strip():
            raise ValueError("request_id is required")
        if not request.matter_id.strip():
            raise ValueError("matter_id is required")
        if not request.objective.strip():
            raise ValueError("objective is required")
        if request.operation not in ALLOWED_OPERATIONS:
            raise ValueError("operation is not admitted for Veritas A0")
        if not request.source_refs:
            raise ValueError("at least one source reference is required")
        if any(not ref.strip() for ref in request.source_refs):
            raise ValueError("source references must be non-empty")
        if request.authority != AUTHORITY_CEILING:
            raise PermissionError("Veritas request exceeds or mismatches A0 authority")
        if request.external_effect:
            raise PermissionError("Veritas A0 requests must have external_effect=False")
        existing = self._accepted.get(request.request_id)
        if existing is not None and existing != request:
            raise ValueError("request_id collision with different payload")
        self._accepted[request.request_id] = request
        return request

    def authorise(self, request_id: str) -> AuthorityDecision:
        request = self._accepted.get(request_id)
        if request is None:
            return AuthorityDecision(False, "REQUEST_NOT_ACCEPTED", AUTHORITY_CEILING)
        if request.authority != AUTHORITY_CEILING or request.external_effect:
            return AuthorityDecision(False, "AUTHORITY_OR_EFFECT_VETO", AUTHORITY_CEILING)
        self._authorised.add(request_id)
        return AuthorityDecision(True, "A0_NO_EFFECT_AUTHORISED", AUTHORITY_CEILING)

    def execute(self, request_id: str) -> Mapping[str, object]:
        request = self._accepted.get(request_id)
        if request is None:
            raise ValueError("request must be accepted before execution")
        if request_id not in self._authorised:
            raise PermissionError("request must be authorised before execution")
        output = dict(self._evaluator(request))
        if output.get("external_effect") not in (None, False):
            raise PermissionError("evaluator attempted to report an external effect")
        output["external_effect"] = False
        output.setdefault("service_id", CANONICAL_SERVICE_ID)
        output.setdefault("authority", AUTHORITY_CEILING)
        self._outputs[request_id] = output
        return dict(output)

    def prove(self, request_id: str) -> ExecutionProof:
        request = self._accepted.get(request_id)
        output = self._outputs.get(request_id)
        if request is None or output is None:
            raise ValueError("execution output is required before proof")
        request_sha = hashlib.sha256(_canonical_json(_request_payload(request))).hexdigest()
        output_sha = hashlib.sha256(_canonical_json(output)).hexdigest()
        return ExecutionProof(
            request_id=request_id,
            service_id=CANONICAL_SERVICE_ID,
            request_sha256=request_sha,
            output_sha256=output_sha,
            authority=AUTHORITY_CEILING,
            external_effect=False,
            state="EXECUTED_A0_NO_EFFECT_PROOF_BOUND",
        )

    def recover(self, request_id: str) -> Mapping[str, object]:
        """Return the adapter to a pre-execution state without external effects."""
        existed = request_id in self._outputs or request_id in self._authorised
        self._outputs.pop(request_id, None)
        self._authorised.discard(request_id)
        return {
            "request_id": request_id,
            "service_id": CANONICAL_SERVICE_ID,
            "restored_to": "ACCEPTED" if request_id in self._accepted else "ABSENT",
            "had_runtime_state": existed,
            "external_effect": False,
            "state": "RECOVERED_NO_EFFECT",
        }


def _request_payload(request: VeritasRequest) -> Mapping[str, object]:
    return {
        "request_id": request.request_id,
        "matter_id": request.matter_id,
        "operation": request.operation,
        "objective": request.objective,
        "source_refs": list(request.source_refs),
        "payload": request.payload,
        "authority": request.authority,
        "external_effect": request.external_effect,
    }


def _canonical_json(value: Mapping[str, object]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


__all__ = [
    "ALLOWED_OPERATIONS",
    "AUTHORITY_CEILING",
    "AuthorityDecision",
    "CANONICAL_NAME",
    "CANONICAL_SERVICE_ID",
    "CANONICAL_VERSION_FAMILY",
    "ExecutionProof",
    "VeritasAdapter",
    "VeritasRequest",
]
