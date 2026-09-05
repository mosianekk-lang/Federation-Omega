from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Callable, Mapping
from urllib import error as urlerror
from urllib import request as urlrequest

from federation.fuse_serving_kernel_v1 import PolicyDecisionReceipt, ServingLaneSpec
from federation.mission_ir import MissionIR


_DEFAULT_DECISION_PATH = "/v1/data/federation/fkpf_omega_v3/allow"


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class OPAEndpoint:
    base_url: str
    policy_ref: str
    decision_path: str = _DEFAULT_DECISION_PATH
    timeout_seconds: float = 2.0

    def validate(self) -> None:
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("FUSE_OPA_BASE_URL_INVALID")
        if not self.policy_ref.strip():
            raise ValueError("FUSE_OPA_POLICY_REF_REQUIRED")
        if not self.decision_path.startswith("/"):
            raise ValueError("FUSE_OPA_DECISION_PATH_INVALID")
        if self.timeout_seconds <= 0:
            raise ValueError("FUSE_OPA_TIMEOUT_INVALID")


class OPAHTTPPolicyGateV1:
    """Thin HTTP adapter over the already-admitted FKPF OPA/Rego policy.

    Policy semantics remain in Rego. This adapter only transports an externally
    constructed, evidence-bound input to OPA and converts the response into a
    hash-bound FUSE decision receipt. A transport failure or malformed response
    fails closed as DENY; it never falls back to an allow decision.
    """

    version = "1.0.0"

    def __init__(
        self,
        endpoint: OPAEndpoint,
        *,
        input_factory: Callable[[MissionIR, ServingLaneSpec], Mapping[str, Any]],
        opener: Callable[..., Any] | None = None,
    ) -> None:
        endpoint.validate()
        self.endpoint = endpoint
        self.input_factory = input_factory
        self.opener = opener or urlrequest.urlopen

    def _receipt(
        self,
        *,
        decision: str,
        policy_input: Mapping[str, Any],
        raw_result: object,
        reason: str = "",
    ) -> PolicyDecisionReceipt:
        return PolicyDecisionReceipt.create(
            decision=decision,
            policy_ref=self.endpoint.policy_ref,
            input_sha256=_digest(policy_input),
            result_sha256=_digest(raw_result),
            reason=reason,
        )

    def authorize(self, *, mission: MissionIR, lane: ServingLaneSpec) -> PolicyDecisionReceipt:
        mission = mission.normalized()
        mission.validate()
        lane.validate()
        policy_input = dict(self.input_factory(mission, lane))
        if not policy_input:
            return self._receipt(
                decision="DENY",
                policy_input={},
                raw_result={"error": "EMPTY_POLICY_INPUT"},
                reason="EMPTY_POLICY_INPUT",
            )

        body = _stable_json({"input": policy_input}).encode("utf-8")
        url = self.endpoint.base_url.rstrip("/") + self.endpoint.decision_path
        req = urlrequest.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self.opener(req, timeout=self.endpoint.timeout_seconds) as response:
                raw = response.read()
        except (urlerror.URLError, TimeoutError, OSError) as exc:
            result = {"transport_error": type(exc).__name__}
            return self._receipt(
                decision="DENY",
                policy_input=policy_input,
                raw_result=result,
                reason="OPA_TRANSPORT_FAILURE",
            )

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            result = {"response_sha256": sha256(raw).hexdigest()}
            return self._receipt(
                decision="DENY",
                policy_input=policy_input,
                raw_result=result,
                reason="OPA_RESPONSE_INVALID",
            )

        result = decoded.get("result") if isinstance(decoded, Mapping) else None
        if result is True:
            return self._receipt(
                decision="ALLOW",
                policy_input=policy_input,
                raw_result=decoded,
            )
        return self._receipt(
            decision="DENY",
            policy_input=policy_input,
            raw_result=decoded,
            reason="OPA_POLICY_DENY",
        )


_EFFECT_MAP = {
    "NO_EFFECT": "NONE",
    "READ_ONLY": "NONE",
    "BOUNDED_EFFECT": "PROVIDER_REVERSIBLE",
    "CONSEQUENTIAL_EFFECT": "CONSEQUENTIAL",
}
_AUTHORITY_ORDER = {
    "A0_OBSERVE": 0,
    "A1_INTERNAL": 1,
    "A2_PROVIDER_REVERSIBLE": 2,
    "A3_OWNER_RESERVED": 3,
}


def mission_effect_input(
    mission: MissionIR,
    lane: ServingLaneSpec,
    *,
    identity_authority: str,
    identity_effect: str,
    owner_approval: bool = False,
    contains_raw_secret: bool = False,
) -> dict[str, Any]:
    """Build the exact input shape expected by FKPF federation.rego.

    `owner_approval` is evidence supplied by the caller/deployment. This helper
    never infers approval from `mission.owner_approval_required`.
    """

    mission = mission.normalized()
    mission.validate()
    lane.validate()
    identity_authority = str(identity_authority).strip().upper()
    identity_effect = str(identity_effect).strip().upper()
    if identity_authority not in _AUTHORITY_ORDER:
        raise ValueError("FUSE_OPA_IDENTITY_AUTHORITY_INVALID")
    if identity_effect not in {"NONE", "INTERNAL_REVERSIBLE", "PROVIDER_REVERSIBLE", "CONSEQUENTIAL"}:
        raise ValueError("FUSE_OPA_IDENTITY_EFFECT_INVALID")

    mission_authority = "A0_OBSERVE"
    for authority in mission.authority_requirements:
        value = str(authority).strip().upper()
        if value in _AUTHORITY_ORDER and _AUTHORITY_ORDER[value] > _AUTHORITY_ORDER[mission_authority]:
            mission_authority = value

    effect = _EFFECT_MAP[lane.effect_class.strip().upper()]
    return {
        "kind": "mission_effect",
        "mission": {
            "mission_id": mission.mission_id,
            "authority": mission_authority,
            "effect": effect,
        },
        "identity": {
            "mission_id": mission.mission_id,
            "authority": identity_authority,
            "effect": identity_effect,
        },
        "owner_approval": bool(owner_approval),
        "provider_readback_required": True,
        "independent_verification_required": True,
        "contains_raw_secret": bool(contains_raw_secret),
    }
