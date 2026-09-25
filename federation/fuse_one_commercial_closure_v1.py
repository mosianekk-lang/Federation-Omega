from __future__ import annotations

"""FUSE One commercial closure compiler v1.

This module composes existing FUSE Product Genesis, Product Release Factory and
Hypercube bottleneck-resolution contracts. It creates no scheduler, provider
runtime, proof root, authority plane, foundry, memory root or deployment power.

Its purpose is to make commercial maturity falsifiable:
source/test presence can never become RELEASE_READY without the required
runtime, installer, supply-chain, recovery and owner/customer value proofs.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable, Sequence

from benchmarking.cfbe_omega.production_genesis_v1 import (
    MaturityStage,
    ProductContract,
    ProofKey,
    compile_build_plan,
    compile_production_genome,
    evaluate_progressive_go_live,
    evaluate_readiness,
)
from federation.product_release_factory_v1 import (
    ProductReleaseInput,
    compile_product_release_bundle,
    release_gate,
)
from superior_logic.hypercube_bottleneck_resolver import (
    BottleneckKind,
    BottleneckResolution,
    BottleneckSignal,
    HypercubeBottleneckResolver,
)

SCHEMA = "FUSE_ONE_COMMERCIAL_CLOSURE_V1"
VERSION = "1.0.0"
PRODUCT_ID = "FUSE_ONE_SOVEREIGN_WORKBENCH"
PRODUCT_VERSION = "0.1.0-candidate"
PROVIDER_EFFECT_AUTHORIZED = False

CANONICAL_OWNER_INTENT = (
    "HYPERCUBE_FUSE_ONE_TO_A_FINAL_COMMERCIALLY_VIABLE_SYSTEM_"
    "WITH_PROOF_BEFORE_CLAIM_AUTONOMOUS_CONTINUATION_LOCAL_FIRST_"
    "PROVIDER_NEUTRALITY_AND_OWNER_AUTHORITY"
)


def _canon(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def _sha(value: object) -> str:
    return sha256(_canon(value).encode("utf-8")).hexdigest()


OWNER_INTENT_HASH = sha256(CANONICAL_OWNER_INTENT.encode("utf-8")).hexdigest()


def canonical_product_contract() -> ProductContract:
    return ProductContract(
        product_id=PRODUCT_ID,
        objective=(
            "Turn owner intent into auditable provider-neutral AI work with "
            "local-first continuity, bounded execution, semantic readback and "
            "proof-carrying outcomes across Windows and optional web/mobile surfaces."
        ),
        user_classes=(
            "TECHNICAL_FOUNDER_OPERATOR",
            "AI_AUTOMATION_LEAD",
            "TRUST_SENSITIVE_KNOWLEDGE_TEAM",
        ),
        user_journeys=(
            "INSTALL_WITHOUT_ADMIN_ON_WINDOWS",
            "RUN_LOCAL_OFFLINE_MISSION",
            "CONNECT_APPROVED_PROVIDER_SURFACE",
            "RUN_AND_RESUME_LONG_MISSION",
            "VERIFY_EFFECT_WITH_SEMANTIC_READBACK",
            "EXPORT_AUDITABLE_ARTIFACT",
            "ROLL_BACK_FAILED_CHANGE",
            "USE_WEB_MOBILE_COMPANION",
        ),
        required_outcomes=(
            "WINDOWS_NON_ADMIN_INSTALL",
            "LOCAL_OFFLINE_CORE",
            "PROVIDER_NEUTRAL_ROUTING",
            "DURABLE_MISSION_RESUME",
            "SEMANTIC_EFFECT_READBACK",
            "PROOF_RECEIPTS",
            "SECURE_UPDATE_AND_ROLLBACK",
            "WEB_MOBILE_COMPANION",
            "EVIDENCE_GATED_TRUST_CENTER",
            "OWNER_CUSTOMER_VALUE_MEASURED",
        ),
        authority_ceiling="A1_INTERNAL",
        data_boundary="PRIVATE_LOCAL_FIRST",
        owner_intent_hash=OWNER_INTENT_HASH,
        quality_floor=0.95,
        security_floor=0.95,
        reliability_floor=0.95,
    ).validate()


def canonical_project_bottlenecks() -> tuple[BottleneckSignal, ...]:
    return (
        BottleneckSignal(
            bottleneck_id="COMMERCIAL-RUNTIME-CONVERGENCE",
            kind=BottleneckKind.SERIAL_DEPENDENCY,
            summary=(
                "Runtime convergence proofs exist in stacked candidate tranches "
                "but the commercial product needs one admitted current-head path."
            ),
            evidence_refs=("FRCB-001..007", "ProofOS", "Bubbles"),
            throughput_drag=0.75,
            latency_share=0.70,
            queue_wait_share=0.70,
            failure_recurrence=0.45,
            dependency_centrality=0.95,
            owner_burden=0.60,
            cost_pressure=0.30,
            proof_gap=0.65,
            risk=0.45,
            commercial_leverage=0.95,
            differentiation_potential=0.90,
            internal_coverage=0.85,
            affected_missions=8,
            internal_capabilities=("FRCB", "ProofOS", "Bubbles", "AAREK", "OF50"),
        ),
        BottleneckSignal(
            bottleneck_id="COMMERCIAL-INSTALLER-LIFECYCLE",
            kind=BottleneckKind.PROOF_EVIDENCE,
            summary=(
                "A commercial Windows product requires signed non-admin install, "
                "upgrade, repair, uninstall and rollback evidence."
            ),
            evidence_refs=("FUSE_PRODUCT_RELEASE_FACTORY_V1",),
            throughput_drag=0.40,
            latency_share=0.30,
            queue_wait_share=0.15,
            failure_recurrence=0.10,
            dependency_centrality=0.90,
            owner_burden=0.50,
            cost_pressure=0.25,
            proof_gap=0.95,
            risk=0.70,
            commercial_leverage=1.00,
            differentiation_potential=0.70,
            internal_coverage=0.35,
            affected_missions=5,
            internal_capabilities=("PRODUCT_RELEASE_FACTORY", "WINDOWS_FEDERATION_PLANE", "GENESIS"),
        ),
        BottleneckSignal(
            bottleneck_id="COMMERCIAL-OWNER-PC-RUNTIME",
            kind=BottleneckKind.PROVIDER_RUNTIME,
            summary=(
                "Hosted/source proof must be converted into live owner-PC "
                "execution, semantic readback and recovery evidence."
            ),
            evidence_refs=("WINDOWS_FEDERATION_PLANE", "FUSE_WINDOWS_SOVEREIGN_RELAY_V1"),
            throughput_drag=0.60,
            latency_share=0.35,
            queue_wait_share=0.25,
            failure_recurrence=0.45,
            dependency_centrality=1.00,
            owner_burden=0.75,
            cost_pressure=0.20,
            proof_gap=0.95,
            risk=0.80,
            commercial_leverage=1.00,
            differentiation_potential=0.95,
            internal_coverage=0.60,
            affected_missions=7,
            internal_capabilities=("FDOF", "WINDOWS_SOVEREIGN_RELAY", "NATIVE_EXECUTOR", "SEMANTIC_READBACK"),
        ),
        BottleneckSignal(
            bottleneck_id="COMMERCIAL-ARCHITECTURE-ENTROPY",
            kind=BottleneckKind.ARCHITECTURAL_DUPLICATION,
            summary=(
                "Commercialization requires one supported product path rather "
                "than exposing the full internal Federation topology to customers."
            ),
            evidence_refs=("HYPERCUBE", "ENTROPY_CONTROLLER", "PRODUCT_RELEASE_FACTORY"),
            throughput_drag=0.50,
            latency_share=0.35,
            queue_wait_share=0.20,
            failure_recurrence=0.30,
            dependency_centrality=0.85,
            owner_burden=0.70,
            cost_pressure=0.60,
            proof_gap=0.40,
            risk=0.45,
            commercial_leverage=0.90,
            differentiation_potential=0.80,
            internal_coverage=0.80,
            affected_missions=10,
            internal_capabilities=("HYPERCUBE", "ENTROPY_CONTROLLER", "CODE_RESTRUCTURING_PLANNER"),
        ),
        BottleneckSignal(
            bottleneck_id="COMMERCIAL-NATIVE-INTERACTION-BINDING",
            kind=BottleneckKind.EXTERNAL_BOUNDARY,
            summary=(
                "Native chat/desktop interaction telemetry is not equivalent to "
                "repository source and needs an authorized host binding."
            ),
            evidence_refs=("CHATBRIDGE", "BUBBLES_F130", "FUSE_ONE_DIRECTIVE"),
            throughput_drag=0.55,
            latency_share=0.35,
            queue_wait_share=0.30,
            failure_recurrence=0.35,
            dependency_centrality=0.90,
            owner_burden=0.65,
            cost_pressure=0.20,
            proof_gap=0.90,
            risk=0.65,
            commercial_leverage=0.95,
            differentiation_potential=0.90,
            internal_coverage=0.65,
            external_boundary=True,
            affected_missions=9,
            internal_capabilities=("CHATBRIDGE", "BUBBLES", "MISSION_RUNTIME_INTERLOCK"),
        ),
    )


@dataclass(frozen=True, slots=True)
class CommercialClosureInput:
    observed_proofs: tuple[str, ...] = ()
    release_terminal_proofs: tuple[str, ...] = ()
    exact_effect_authority: bool = False
    rollback_verified: bool = False
    semantic_canary_defined: bool = False
    bottlenecks: tuple[BottleneckSignal, ...] = ()


@dataclass(frozen=True, slots=True)
class CommercialClosureReport:
    schema: str
    version: str
    product_id: str
    product_version: str
    product_contract_fingerprint: str
    production_genome_id: str
    release_bundle_id: str
    maturity_stage: str
    go_live_status: str
    release_status: str
    commercial_state: str
    observed_proofs: tuple[str, ...]
    missing_to_next_stage: tuple[str, ...]
    missing_release_proofs: tuple[str, ...]
    hypercube_resolution_receipts: tuple[str, ...]
    commercial_features: tuple[str, ...]
    next_actions: tuple[str, ...]
    provider_effect_authorized: bool
    receipt_sha256: str


def _proof_keys(names: Iterable[str]) -> tuple[ProofKey, ...]:
    index = {item.value: item for item in ProofKey}
    normalized = tuple(sorted({str(name).strip() for name in names if str(name).strip()}))
    unknown = tuple(name for name in normalized if name not in index)
    if unknown:
        raise ValueError("FUSE_COMMERCIAL_UNKNOWN_PROOF:" + ",".join(unknown))
    return tuple(index[name] for name in normalized)


def _next_actions(
    *,
    missing_stage: Sequence[str],
    missing_release: Sequence[str],
    resolutions: Sequence[BottleneckResolution],
) -> tuple[str, ...]:
    actions: list[str] = []
    if missing_stage:
        actions.append("PROVE_NEXT_MATURITY:" + missing_stage[0])
    if missing_release:
        actions.append("CLOSE_RELEASE_PROOF:" + missing_release[0])
    for item in resolutions[:3]:
        actions.append(
            "HYPERCUBE_RESOLVE:"
            + item.bottleneck_id
            + ":"
            + item.selected.family.value
            + ":"
            + item.selected.candidate_id
        )
    if not actions:
        actions.append("RUN_FINAL_COMMERCIAL_RELEASE_COURT")
    return tuple(actions)


def compile_commercial_closure(
    request: CommercialClosureInput,
) -> CommercialClosureReport:
    contract = canonical_product_contract()
    genome = compile_production_genome(contract)
    compile_build_plan(genome)

    release = compile_product_release_bundle(
        ProductReleaseInput(
            product_id=PRODUCT_ID,
            product_contract_fingerprint=contract.fingerprint,
            version=PRODUCT_VERSION,
            executable_entrypoints=("fuse-one-desktop.exe", "fuse-one-cli.exe"),
            website_routes=("/", "/download", "/docs", "/trust", "/status"),
            installer_targets=("MSIX_USER", "ZIP_PORTABLE"),
            feature_flags=("LOCAL_AI", "CONNECTED_PROVIDERS", "WEB_MOBILE_COMPANION", "PROOF_EXPLORER"),
            auth_adapters=("OIDC", "PASSKEY"),
            tenant_modes=("SINGLE_TENANT", "MULTI_TENANT_READY"),
            authority_ceiling=contract.authority_ceiling,
            data_boundary=contract.data_boundary,
        )
    )

    proofs = _proof_keys(request.observed_proofs)
    readiness = evaluate_readiness(proofs)
    go_live = evaluate_progressive_go_live(
        proofs,
        exact_effect_authority=request.exact_effect_authority,
        rollback_verified=request.rollback_verified,
        semantic_canary_defined=request.semantic_canary_defined,
    )
    release_result = release_gate(release, request.release_terminal_proofs)

    resolver = HypercubeBottleneckResolver()
    signals = request.bottlenecks or canonical_project_bottlenecks()
    resolutions = tuple(resolver.resolve(signal) for signal in signals)

    features = tuple(
        sorted(
            {
                feature
                for result in resolutions
                for feature in result.product_features
            }
            | {
                "Windows non-admin install",
                "local/offline cold core",
                "provider-neutral capability routing",
                "durable resumable missions",
                "semantic action readback",
                "proof and provenance explorer",
                "secure update and rollback",
                "optional web/mobile companion",
                "evidence-gated trust center",
            }
        )
    )

    missing_stage = tuple(item.value for item in readiness.missing_to_next)
    missing_release = tuple(release_result["missing"])

    release_ready = (
        readiness.stage == MaturityStage.VALUE_VERIFIED
        and go_live.status == "READY_FOR_PROGRESSIVE_GO_LIVE"
        and release_result["status"] == "RELEASE_READY"
    )
    if release_ready:
        state = "COMMERCIAL_RELEASE_READY"
    elif readiness.stage >= MaturityStage.PROVIDER_CANARY_READY:
        state = "COMMERCIAL_CANARY_READY"
    elif readiness.stage >= MaturityStage.DETERMINISTIC_TESTED:
        state = "COMMERCIAL_BUILD_VALIDATED"
    else:
        state = "COMMERCIAL_CLOSURE_IN_PROGRESS"

    next_actions = _next_actions(
        missing_stage=missing_stage,
        missing_release=missing_release,
        resolutions=resolutions,
    )

    body = {
        "schema": SCHEMA,
        "version": VERSION,
        "product_id": PRODUCT_ID,
        "product_version": PRODUCT_VERSION,
        "product_contract_fingerprint": contract.fingerprint,
        "production_genome_id": genome.genome_id,
        "release_bundle_id": release.bundle_id,
        "maturity_stage": readiness.stage.name,
        "go_live_status": go_live.status,
        "release_status": release_result["status"],
        "commercial_state": state,
        "observed_proofs": [item.value for item in readiness.observed],
        "missing_to_next_stage": missing_stage,
        "missing_release_proofs": missing_release,
        "hypercube_resolution_receipts": [item.receipt_sha256 for item in resolutions],
        "commercial_features": features,
        "next_actions": next_actions,
        "provider_effect_authorized": False,
    }

    return CommercialClosureReport(
        schema=SCHEMA,
        version=VERSION,
        product_id=PRODUCT_ID,
        product_version=PRODUCT_VERSION,
        product_contract_fingerprint=contract.fingerprint,
        production_genome_id=genome.genome_id,
        release_bundle_id=release.bundle_id,
        maturity_stage=readiness.stage.name,
        go_live_status=go_live.status,
        release_status=release_result["status"],
        commercial_state=state,
        observed_proofs=tuple(item.value for item in readiness.observed),
        missing_to_next_stage=missing_stage,
        missing_release_proofs=missing_release,
        hypercube_resolution_receipts=tuple(item.receipt_sha256 for item in resolutions),
        commercial_features=features,
        next_actions=next_actions,
        provider_effect_authorized=False,
        receipt_sha256=_sha(body),
    )


__all__ = [
    "CANONICAL_OWNER_INTENT",
    "CommercialClosureInput",
    "CommercialClosureReport",
    "OWNER_INTENT_HASH",
    "PRODUCT_ID",
    "PRODUCT_VERSION",
    "canonical_product_contract",
    "canonical_project_bottlenecks",
    "compile_commercial_closure",
]
