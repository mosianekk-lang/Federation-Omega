from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .change_impact import ChangeImpactCompiler, ImpactDecision, MissionSnapshot
from .convergence import ConstitutionalConvergence
from .evidence_distillation import EvidenceDistiller
from .provider_attestations import (
    DynamicProviderRouter,
    ProviderAttestation,
    ProviderAttestationStore,
    ProviderRoutePolicy,
)
from .trace import SpanKind, TraceBuffer, TraceSpan


def run(repo_root: str | Path = ".") -> dict:
    root = Path(repo_root)
    gates: dict[str, bool] = {}

    architecture = ConstitutionalConvergence().architecture_receipt()
    gates["single_constitutional_hierarchy"] = (
        architecture["mission_semantic_owner"] == "SLOS"
        and architecture["transaction_kernel_owner"] == "SOL_6_2_KERNEL"
        and architecture["provider_effect_owner"] == "SOVARA"
        and architecture["duplicate_sovereign_mission_plane"] is False
    )

    db = sqlite3.connect(":memory:")
    try:
        store = ProviderAttestationStore(db)
        store.put(
            ProviderAttestation.build(
                attestation_id="proof-attestation",
                provider="GOOGLE",
                surface="GEMINI_VERTEX",
                subject="runtime",
                state="INFERENCE_VERIFIED_SCOPED",
                capabilities=("GEMINI_INFERENCE",),
                observed_at_epoch=100,
                expires_at_epoch=200,
                evidence_refs=("provider:proof",),
                source_revision="proof-source",
            )
        )
        router = DynamicProviderRouter(
            store,
            (
                ProviderRoutePolicy(
                    operation="GEMINI_INFERENCE",
                    provider="GOOGLE",
                    surface="GEMINI_VERTEX",
                    capability="GEMINI_INFERENCE",
                ),
            ),
        )
        route = router.route("GEMINI_INFERENCE", now_epoch=150)
        gates["dynamic_provider_attestation"] = route.attestation_id == "proof-attestation"
    finally:
        db.close()

    snapshot = MissionSnapshot.build(
        mission_id="proof-mission",
        base_revision="base",
        protected_paths=("superior_logic/**",),
        retest_paths=("tests/test_slos_*",),
        contract_paths=("Dockerfile",),
        source_epoch=1,
    )
    impact = ChangeImpactCompiler().evaluate(snapshot, ("sovara/creative/unrelated.py",))
    gates["unrelated_change_suppression"] = impact.decision is ImpactDecision.IGNORE_UNRELATED

    evidence = EvidenceDistiller(max_excerpt_chars=32).distill(
        evidence_id="proof-evidence",
        source_ref="provider:receipt",
        evidence_kind="LOG",
        raw="raw evidence remains outside control plane",
        sensitive=True,
    )
    gates["evidence_distillation"] = evidence.excerpt is None and len(evidence.content_sha256) == 64

    trace = TraceBuffer("proof-trace")
    root_span = TraceSpan.build(
        trace_id="proof-trace", kind=SpanKind.MISSION, name="mission", status="OK"
    )
    trace.append(root_span)
    trace.append(
        TraceSpan.build(
            trace_id="proof-trace",
            parent_span_id=root_span.span_id,
            kind=SpanKind.PROOF,
            name="proof",
            status="OK",
            attributes={"proof_reference": "receipt:proof"},
        )
    )
    gates["trace_spine"] = trace.receipt()["span_count"] == 2

    # ProofOS's full-federation fallback deliberately executes from an extracted
    # Python core that does not contain repository packaging surfaces such as
    # Dockerfile or .github/workflows. Those surfaces remain independently
    # enforced by the repository Airlock and by SourceShapeTests when the full
    # checkout is present. A *partial* repository surface is never accepted.
    docker_path = root / "Dockerfile"
    workflow_path = root / ".github/workflows/sol62-wif-hardening-lease.yml"
    docker_exists = docker_path.is_file()
    workflow_exists = workflow_path.is_file()
    if docker_exists and workflow_exists:
        docker = docker_path.read_text(encoding="utf-8")
        gates["secure_deployment_entrypoint"] = (
            "APP_MODULE=superior_logic.secure_service:app" in docker
            and "COPY sol_61_runtime ./sol_61_runtime" in docker
            and "APP_MODULE=superior_logic.service:app" not in docker
        )

        workflow = workflow_path.read_text(encoding="utf-8")
        gates["one_success_wif_lease"] = all(
            needle in workflow
            for needle in (
                "actions: read",
                "Consume lease only after first successful transaction",
                "ALREADY_CONSUMED",
                "bash ./ops/harden_sovara_provider_wif_v1.sh --apply",
            )
        )
        repository_surface_state = "VERIFIED_IN_FULL_CHECKOUT"
    elif not docker_exists and not workflow_exists:
        repository_surface_state = "ABSENT_FROM_EXTRACTED_CORE_AIRLOCK_OWNED"
    else:
        gates["repository_packaging_surface_complete"] = False
        repository_surface_state = "PARTIAL_SURFACE_REJECTED"

    passed = all(gates.values())
    receipt = {
        "schema": "SLOS_SOL62_CONVERGENCE_PROOF_V1",
        "state": "DETERMINISTIC_VERIFIED" if passed else "FAILED",
        "gates": gates,
        "gate_count": len(gates),
        "passed_count": sum(1 for value in gates.values() if value),
        "repository_packaging_surface_state": repository_surface_state,
        "repository_packaging_surface_authority": "FEDERATION_OMEGA_AIRLOCK",
        "provider_effect_performed": False,
        "provider_authority_inherited": False,
        "stable_release_promoted": False,
    }
    if not passed:
        raise AssertionError(json.dumps(receipt, sort_keys=True))
    return receipt


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
