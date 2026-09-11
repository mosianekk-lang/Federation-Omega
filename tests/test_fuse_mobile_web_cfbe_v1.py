from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile" / "fuse-mobile"


def read(relative: str) -> str:
    return (MOBILE / relative).read_text(encoding="utf-8")


def test_web_export_and_static_host_contract() -> None:
    package = json.loads(read("package.json"))
    app = json.loads(read("app.json"))
    assert package["version"] == "0.3.0"
    assert package["scripts"]["export:web"] == "expo export --platform web"
    assert package["scripts"]["verify:web"] == "expo export --platform web --output-dir dist-web"
    assert app["expo"]["web"] == {"bundler": "metro", "output": "static"}
    assert app["expo"]["orientation"] == "default"


def test_platform_specific_owner_identity_and_session_are_present() -> None:
    web_iap = read("src/iap.web.ts")
    web_session = read("src/session.web.ts")
    native_iap = read("src/iap.ts")
    native_session = read("src/session.ts")
    assert "accounts.google.com/gsi/client" in web_iap
    assert "sessionStorage" in web_iap
    assert "sessionStorage" in web_session
    assert "localStorage" not in web_session
    assert "@react-native-google-signin/google-signin" in native_iap
    assert "expo-secure-store" in native_session


def test_pwa_shell_never_caches_authorized_api_traffic() -> None:
    html = read("app/+html.tsx")
    manifest = json.loads(read("public/manifest.webmanifest"))
    sw = read("public/sw.js").lower()
    assert "serviceworker.register('/sw.js')" in html.lower()
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    assert "authorization" in sw
    assert "x-fuse-authorization" in sw
    assert "request.method !== 'get'" in sw
    assert "url.origin !== self.location.origin" in sw


def test_abort_signal_reaches_gateway_transport() -> None:
    federation = read("src/federation.ts")
    owner = read("src/ownerConnection.ts")
    home = read("app/index.tsx")
    assert "externalSignal?: AbortSignal" in federation
    assert "sendFuseMessage" in federation and "signal?: AbortSignal" in federation
    assert "sendOwnerFuseMessage" in owner and "signal?: AbortSignal" in owner
    assert "AbortController" in home
    assert "handleStop" in home


def test_cfbe_capability_passport_is_exact_and_complete() -> None:
    passport = read("src/cfbeCapabilityPassport.ts")
    ids = re.findall(r"id: 'FM-CFBE-(\d{3})'", passport)
    assert len(ids) == 100
    assert len(set(ids)) == 100
    assert ids == [f"{number:03d}" for number in range(1, 101)]
    assert "WORK_PACKAGE_CREATED" in passport


def test_proof_visible_ui_contract() -> None:
    home = read("app/index.tsx")
    required = [
        "LIVE DIAGNOSTICS",
        "PROVIDER READBACK",
        "ACTION TIMELINE",
        "Authority preview",
        "source_refs",
        "trace_id",
        "Proof-before-claim",
        "CFBE {passport.total}",
    ]
    for marker in required:
        assert marker in home
    assert "EXECUTE" in home
    assert "PRIVATE" in home


def test_no_web_identity_or_session_secret_is_hardcoded() -> None:
    joined = "\n".join([read("src/iap.web.ts"), read("src/session.web.ts")])
    lowered = joined.lower()
    assert "client_secret" not in lowered
    assert "private_key" not in lowered
    assert "refresh_token" not in lowered
    assert "sk-" not in lowered


def test_anthropic_harvest_registry_has_42_unique_genes() -> None:
    source = read("src/anthropicCfbe.ts")
    ids = re.findall(r'id: "(ANTH-\d{3})"', source)
    assert len(ids) == 42
    assert len(set(ids)) == 42
    assert ids[0] == "ANTH-001"
    assert ids[-1] == "ANTH-042"


def test_anthropic_harvest_runtime_primitives_are_present() -> None:
    source = read("src/anthropicCfbe.ts")
    required = {
        "discoverDeferredTools",
        "selectProgressiveSkills",
        "screenUntrustedContext",
        "classifyActionRisk",
        "compactSessionEvents",
        "buildResearchFanout",
        "chooseModelLane",
        "createMissionCheckpoint",
        "evaluateObservedOutcome",
        "compileDeviceCapability",
        "capBlastRadius",
        "gateSubagentHandoff",
        "harvestDisposition",
    }
    for name in required:
        assert f"function {name}" in source


def test_anthropic_harvest_effect_gate_is_fail_closed() -> None:
    source = read("src/anthropicCfbe.ts")
    assert 'const deny = effect === "PRIVILEGED" && secretSignal' in source
    assert 'requiresOwnerApproval: !deny' in source
    assert "dangerously-skip-permissions" not in source


def test_anthropic_harvest_context_screen_and_truth_boundary() -> None:
    source = read("src/anthropicCfbe.ts")
    doc = read("CFBE_ANTHROPIC_DEEP_HARVEST_V1.md")
    for marker in ['"instruction-override"', '"secret-request"', '"authority-escalation"']:
        assert marker in source
    assert "[UNTRUSTED_CONTEXT:" in source
    assert '"RUNTIME_GATED"' in source
    assert '"PROVIDER_GATED"' in source
    assert "Still requires empirical/provider proof" in doc
    assert "No gene may be promoted merely because a file exists" in doc


def test_anthropic_harvest_context_efficiency_and_outcome_truth() -> None:
    source = read("src/anthropicCfbe.ts")
    for marker in ["deferredSchema", "bodyRef", "resourceRefs", "semantic-token-overlap"]:
        assert marker in source
    assert "claim-observation-mismatch" in source
    assert "observedState" in source


def test_anthropic_harvest_device_contract_defaults_to_owner_presence() -> None:
    source = read("src/anthropicCfbe.ts")
    assert "requiresOwnerPresence: input.requiresOwnerPresence ?? true" in source
    assert "maxConcurrentActions: Math.max(1" in source


def test_anthropic_harvest_embeds_no_provider_secret_material() -> None:
    joined = "\n".join([read("src/anthropicCfbe.ts"), read("CFBE_ANTHROPIC_DEEP_HARVEST_V1.md")])
    for token in ["sk-ant-", "ANTHROPIC_API_KEY=", "OPENAI_API_KEY=", "GOOGLE_API_KEY="]:
        assert token not in joined


def test_anthropic_v2_extends_genome_to_72_unique_genes() -> None:
    v1 = read("src/anthropicCfbe.ts")
    v2 = read("src/anthropicCfbeV2.ts")
    ids = re.findall(r'id: "(ANTH-\d{3})"', v1 + "\n" + v2)
    assert len(ids) == 72
    assert len(set(ids)) == 72
    assert ids == [f"ANTH-{number:03d}" for number in range(1, 73)]


def test_anthropic_v2_contains_deep_runtime_controls() -> None:
    source = read("src/anthropicCfbeV2.ts")
    required = {
        "chooseAdvisorDelegation",
        "chooseAdaptiveEffort",
        "chooseExecutionLocus",
        "chooseToolset",
        "planContextPressure",
        "planMemoryAccess",
        "evaluateOutcomeIteration",
        "chooseContainmentProfile",
        "twoStageActionGate",
        "researchSuitability",
        "scoreResearchRubric",
        "planCitationAudit",
        "budgetToolResult",
        "harnessSimplificationCandidates",
        "benchmarkNoiseDecision",
        "validateParallelCodeShards",
        "compileDeviceCommand",
        "deviceRecoveryDecision",
        "incidentToRegressionCase",
        "anthropicV2Disposition",
    }
    for name in required:
        assert f"function {name}" in source
    assert "class VersionedMemoryStore" in source
    assert "class AgentDefinitionStore" in source


def test_anthropic_v2_memory_and_containment_are_fail_closed() -> None:
    source = read("src/anthropicCfbeV2.ts")
    assert "persistent-memory-poisoning-risk" in source
    assert "memory-write-requires-trusted-input" in source
    assert 'secrets: "ABSENT"' in source
    assert 'network: "PROXY_ENFORCED"' in source
    assert "outside-containment-boundary" in source


def test_anthropic_v2_device_write_defaults_to_owner_presence() -> None:
    source = read("src/anthropicCfbeV2.ts")
    assert 'const write = input.kind === "WRITE"' in source
    assert "requiresOwnerPresence: write" in source
    assert 'return "STOP_AND_ESCALATE"' in source


def test_anthropic_v2_benchmark_and_harness_truth_controls() -> None:
    source = read("src/anthropicCfbeV2.ts")
    assert "delta-clears-noise-and-practicality-floor" in source
    assert "delta-not-distinguishable-from-noise-or-too-small" in source
    assert "measuredBenefit" in source
    assert "maintenanceCost" in source


def test_anthropic_v2_has_no_provider_secret_or_unsafe_permission_bypass() -> None:
    source = read("src/anthropicCfbeV2.ts")
    for token in ["sk-ant-", "ANTHROPIC_API_KEY=", "OPENAI_API_KEY=", "GOOGLE_API_KEY=", "dangerously-skip-permissions"]:
        assert token not in source


def test_anthropic_v3_completes_100_unique_genes() -> None:
    sources = "\n".join([
        read("src/anthropicCfbe.ts"),
        read("src/anthropicCfbeV2.ts"),
        read("src/anthropicCfbeV3.ts"),
    ])
    ids = re.findall(r'id: "(ANTH-\d{3})"', sources)
    assert len(ids) == 100
    assert len(set(ids)) == 100
    assert ids == [f"ANTH-{number:03d}" for number in range(1, 101)]


def test_anthropic_v3_contains_physical_ai_and_long_horizon_controls() -> None:
    source = read("src/anthropicCfbeV3.ts")
    required = {
        "compileDeviceManifest",
        "validateDeviceWrite",
        "planObserveAdjustLoop",
        "validateParallelDevicePlan",
        "shouldCompileDeterministicRoutine",
        "createAsyncMission",
        "recoverAsyncMission",
        "createProgressHeartbeat",
        "buildSelfTestPlan",
        "visualVerificationRequirement",
        "rootCauseRepairGate",
        "contextCachePolicy",
        "hydrateMissionContext",
        "executionHandHealthDecision",
        "approvalFatigueRisk",
        "containmentForOperator",
        "securityPrimitiveDecision",
        "validateEgressCredential",
        "inspectionPolicyForReturn",
        "normalizeEvalEnvironment",
        "bootstrapRealTaskEval",
        "aggregateOutcomeGraders",
        "providerLifecycleDecision",
        "anthropicV3Disposition",
    }
    for name in required:
        assert f"function {name}" in source


def test_anthropic_v3_enforces_device_and_egress_safety() -> None:
    source = read("src/anthropicCfbeV3.ts")
    assert "below-driver-safety-minimum" in source
    assert "above-driver-safety-maximum" in source
    assert "credential-environment-provenance-mismatch" in source
    assert "credential-audience-mismatch" in source
    assert "credential-expired" in source
    assert 'if (input.containsSecrets) return "QUARANTINE"' in source


def test_anthropic_v3_preserves_truth_and_recovery_boundaries() -> None:
    source = read("src/anthropicCfbeV3.ts")
    doc = read("CFBE_ANTHROPIC_DEEP_HARVEST_V2.md")
    assert "symptom-only-repair-rejected" in source
    assert "CHECKPOINT_AND_STOP" in source
    assert "PROVIDER_GATED" in source
    assert "No maturity label can advance from prose" in doc
    assert "Physical writes remain proof- and authority-gated" in doc


def test_anthropic_100_gene_harvest_embeds_no_provider_secrets() -> None:
    joined = "\n".join([
        read("src/anthropicCfbe.ts"),
        read("src/anthropicCfbeV2.ts"),
        read("src/anthropicCfbeV3.ts"),
        read("CFBE_ANTHROPIC_DEEP_HARVEST_V1.md"),
        read("CFBE_ANTHROPIC_DEEP_HARVEST_V2.md"),
    ])
    for token in ["sk-ant-", "ANTHROPIC_API_KEY=", "OPENAI_API_KEY=", "GOOGLE_API_KEY=", "dangerously-skip-permissions"]:
        assert token not in joined
