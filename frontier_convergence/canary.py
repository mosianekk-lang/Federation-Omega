"""Deterministic provider-disabled canary for Frontier Convergence."""
from __future__ import annotations

from dataclasses import asdict

from services.gemini_gateway.app import Gateway as GeminiGateway

from .core import (
    ConvergenceStage,
    ExperimentIdentityCompiler,
    FrontierConvergenceEngine,
    FrontierSignal,
    RobustnessCourt,
    RobustnessObservation,
    ValueReceipt,
)
from .gemini_adapter import GeminiAdapter


class _CanaryGeminiIdentity:
    def snapshot(self) -> dict[str, str]:
        return {
            "project_id": "sov-hybrid-suite",
            "project_number": "257649435135",
            "service_account": "sv-gemini-runtime@sov-hybrid-suite.iam.gserviceaccount.com",
            "authority_mode": "CLOUD_RUN_SERVICE_ACCOUNT_ADC",
        }


class _CanaryGeminiClient:
    location = "global"
    model = "gemini-2.5-flash"

    def __init__(self, nonce: str) -> None:
        self._nonce = nonce

    def generate(self, **_: object) -> dict[str, object]:
        return {
            "provider": "GOOGLE_VERTEX_AI_GEMINI",
            "provider_request_id": "synthetic-provider-request",
            "model_identity": "gemini-2.5-flash-synthetic",
            "configured_model": self.model,
            "finish_state": "STOP",
            "usage": {"totalTokenCount": 2},
            "latency_ms": 0,
            "provider_identity": _CanaryGeminiIdentity().snapshot(),
            "request_sha256": "a" * 64,
            "response_sha256": "b" * 64,
            "text": f"HANDSHAKE_RECEIPT:{self._nonce}",
        }


def _gemini_gateway_contract_canary() -> dict[str, object]:
    nonce = "FC-GEMINI-PROVIDER-DISABLED-CANARY"
    plan = GeminiAdapter.compile_call(
        mission_id="FC-CANARY",
        model_ref="gemini-2.5-flash",
        contents="provider-disabled contract check",
    )
    gateway = GeminiGateway(
        identity=_CanaryGeminiIdentity(),
        client=_CanaryGeminiClient(nonce),
    )
    health = gateway.health()
    receipt = gateway.handshake({"semantic_nonce": nonce})
    valid = (
        plan.credential_reference == "CLOUD_RUN_ADC"
        and plan.protocol == "VERTEX_AI_GENERATE_CONTENT_REST"
        and health["provider_execution_verified"] is False
        and receipt["status"] == "VERIFIED"
        and receipt["semantic_nonce"] == nonce
        and receipt["semantic_verified"] is True
        and receipt["provider_identity"]["project_id"] == "sov-hybrid-suite"
        and len(str(receipt["receipt_sha256"])) == 64
    )
    return {
        "valid": valid,
        "provider_effects": False,
        "credential_reference": plan.credential_reference,
        "protocol": plan.protocol,
        "receipt_sha256": receipt["receipt_sha256"],
    }


def run_canary() -> dict[str, object]:
    engine = FrontierConvergenceEngine()
    signal = FrontierSignal.create(
        source_organization="SYNTHETIC_FRONTIER",
        capability_class="provider_neutral_canary",
        mechanism="deterministic mechanism harvest without external effects",
        evidence_refs=("synthetic://fixture",),
        observed_at="2026-08-27T15:00:00+00:00",
    )
    observed = engine.observe(signal)
    candidate = engine.form_candidate(
        signals=(signal,),
        incumbent_capability_id="CANARY-INCUMBENT",
        architecture="provider-neutral deterministic shadow candidate",
        expected_metric_names=("quality", "reliability", "latency", "cost", "owner_burden"),
    )
    robustness = RobustnessCourt.evaluate(
        RobustnessObservation(gate=gate, passed=True, evidence_refs=(f"synthetic://{gate.lower()}",))
        for gate in RobustnessCourt.MANDATORY_GATES
    )
    experiment = ExperimentIdentityCompiler.compile(
        implementation_sha256="1" * 64,
        source_sha256="2" * 64,
        inputs={"fixture": 1},
        environment={"runtime": "provider-disabled"},
        observation_window="synthetic-canary",
        parameters={"temperature": 0},
        cost_latency_context={"cost": 0, "latency_class": "local"},
        controls={"provider_effects": False},
        authority={"ceiling": "A1_INTERNAL"},
    )
    value = ValueReceipt.create(
        candidate_id=candidate.candidate_id,
        quality=1.0,
        reliability=1.0,
        latency_ms=1.0,
        cost=0.0,
        owner_burden=0.0,
        outcome_value=1.0,
        evidence_refs=("synthetic://value",),
    )
    admission = engine.admission(
        candidate=candidate,
        stage=ConvergenceStage.ADOPTED,
        robustness=robustness,
        independent_quorum_outcome="ADMIT",
        value_receipt=value,
        rollback_proof_ref="synthetic://rollback",
        provider_readback_refs=(),
        experiment_identity=experiment,
    )
    gemini_gateway = _gemini_gateway_contract_canary()
    passed = (
        robustness.passed
        and admission.decision == "ADMIT"
        and engine.store.verify_event_chain()
        and observed["event_id"].startswith("FC-EVT-")
        and gemini_gateway["valid"] is True
        and gemini_gateway["provider_effects"] is False
    )
    return {
        "state": "PASS" if passed else "FAIL",
        "provider_effects": False,
        "event_chain_valid": engine.store.verify_event_chain(),
        "signal_id": signal.signal_id,
        "candidate_id": candidate.candidate_id,
        "experiment_fingerprint": experiment.fingerprint,
        "robustness": asdict(robustness),
        "admission": asdict(admission),
        "gemini_gateway_contract": gemini_gateway,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_canary(), sort_keys=True))
