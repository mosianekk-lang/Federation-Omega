"""Deterministic provider-disabled canary for Frontier Convergence."""
from __future__ import annotations

from dataclasses import asdict

from .core import (
    ConvergenceStage,
    ExperimentIdentityCompiler,
    FrontierConvergenceEngine,
    FrontierSignal,
    RobustnessCourt,
    RobustnessObservation,
    ValueReceipt,
)


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
    passed = (
        robustness.passed
        and admission.decision == "ADMIT"
        and engine.store.verify_event_chain()
        and observed["event_id"].startswith("FC-EVT-")
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
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_canary(), sort_keys=True))
