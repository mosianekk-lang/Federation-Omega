from __future__ import annotations

"""Bubbles–CFBE Ω empirical frontier closure compiler v1.

This module adds no scheduler, memory store, agent hierarchy, provider authority,
or promotion path. It composes proof already owned by existing Federation
components into one fail-closed frontier register.

A lane records the strongest proof actually achieved and a separate terminal
promotion gate. Hosted proof never inherits provider proof; source readiness
never inherits observed value; and a credential/authority hold is a valid
terminal outcome until the missing external fact becomes available.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence


SCHEMA = "BUBBLES_CFBE_OMEGA_EMPIRICAL_FRONTIER_CLOSURE_V1"
SNAPSHOT_DATE_SAST = "2026-09-01"
MINIMUM_OWNER_VALUE_PAIRS = 10


class ProofState(str, Enum):
    PROVIDER_VERIFIED = "PROVIDER_VERIFIED"
    HOSTED_VERIFIED = "HOSTED_VERIFIED"
    OBSERVED_PARTIAL = "OBSERVED_PARTIAL"
    SOURCE_READY = "SOURCE_READY"
    HOLD_PROVIDER_AUTHORITY = "HOLD_PROVIDER_AUTHORITY"
    HOLD_CREDENTIAL_BINDING = "HOLD_CREDENTIAL_BINDING"
    HOLD_REAL_OBSERVATIONS = "HOLD_REAL_OBSERVATIONS"


@dataclass(frozen=True, slots=True)
class FrontierLane:
    lane_id: str
    objective: str
    state: ProofState
    evidence_refs: tuple[str, ...]
    proof_properties: tuple[str, ...]
    terminal_gate: str | None
    gate_owner: str | None
    provider_effect_authorized: bool = False
    stable_promotion_authorized: bool = False

    def validate(self) -> "FrontierLane":
        if not self.lane_id or not self.objective:
            raise ValueError("FRONTIER_LANE_IDENTITY_REQUIRED")
        if not self.evidence_refs:
            raise ValueError(f"{self.lane_id}_EVIDENCE_REQUIRED")
        if not self.proof_properties:
            raise ValueError(f"{self.lane_id}_PROOF_PROPERTIES_REQUIRED")
        if self.state in {
            ProofState.HOLD_PROVIDER_AUTHORITY,
            ProofState.HOLD_CREDENTIAL_BINDING,
            ProofState.HOLD_REAL_OBSERVATIONS,
        } and not self.terminal_gate:
            raise ValueError(f"{self.lane_id}_HOLD_GATE_REQUIRED")
        if self.provider_effect_authorized:
            raise ValueError("EMPIRICAL_CLOSURE_MUST_NOT_GRANT_PROVIDER_EFFECT")
        if self.stable_promotion_authorized:
            raise ValueError("EMPIRICAL_CLOSURE_MUST_NOT_GRANT_STABLE_PROMOTION")
        return self

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["evidence_refs"] = list(self.evidence_refs)
        payload["proof_properties"] = list(self.proof_properties)
        return payload


@dataclass(frozen=True, slots=True)
class EmpiricalFrontierClosure:
    schema: str
    snapshot_date_sast: str
    source_main_sha: str
    lanes: tuple[FrontierLane, ...]
    closure_sha256: str = ""

    def validate(self) -> "EmpiricalFrontierClosure":
        if self.schema != SCHEMA:
            raise ValueError("EMPIRICAL_FRONTIER_SCHEMA_INVALID")
        if len(self.source_main_sha) != 40 or any(c not in "0123456789abcdef" for c in self.source_main_sha.lower()):
            raise ValueError("EMPIRICAL_FRONTIER_SOURCE_SHA_INVALID")
        expected_ids = {
            "DURABLE_RUNTIME",
            "TOOLBOX_GOVERNANCE",
            "WORKLOAD_IDENTITY",
            "LIVE_AGENT_TELEMETRY",
            "TRACE_EVAL_OPTIMIZER",
            "SLSA_ATTESTATION",
            "MULTI_PROVIDER_ROUTING",
            "AI_ASSET_VALUE_GOVERNANCE",
            "OWNER_VALUE",
        }
        ids = {lane.lane_id for lane in self.lanes}
        if ids != expected_ids or len(self.lanes) != len(expected_ids):
            raise ValueError("EMPIRICAL_FRONTIER_NINE_LANES_REQUIRED")
        for lane in self.lanes:
            lane.validate()
        return self

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema": self.schema,
            "snapshot_date_sast": self.snapshot_date_sast,
            "source_main_sha": self.source_main_sha,
            "lane_count": len(self.lanes),
            "lanes": [lane.to_dict() for lane in sorted(self.lanes, key=lambda item: item.lane_id)],
            "summary": state_counts(self.lanes),
            "truth_boundary": {
                "hosted_is_not_serving_provider_deployment": True,
                "source_is_not_provider_proof": True,
                "credential_hold_is_not_capability_failure": True,
                "owner_value_requires_measured_matched_pairs_and_court_verification": True,
                "provider_effect_authority_not_granted": True,
                "stable_promotion_not_granted": True,
            },
        }
        if include_hash:
            payload["closure_sha256"] = self.closure_sha256 or canonical_hash(payload)
        return payload


def canonical_hash(value: Mapping[str, object]) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def state_counts(lanes: Iterable[FrontierLane]) -> dict[str, int]:
    counts = {state.value: 0 for state in ProofState}
    for lane in lanes:
        counts[lane.state.value] += 1
    return counts


def _lane(
    lane_id: str,
    objective: str,
    state: ProofState,
    evidence_refs: Sequence[str],
    proof_properties: Sequence[str],
    terminal_gate: str | None = None,
    gate_owner: str | None = None,
) -> FrontierLane:
    return FrontierLane(
        lane_id=lane_id,
        objective=objective,
        state=state,
        evidence_refs=tuple(evidence_refs),
        proof_properties=tuple(proof_properties),
        terminal_gate=terminal_gate,
        gate_owner=gate_owner,
    ).validate()


def current_snapshot(
    *,
    owner_value_pairs: int = 0,
    owner_value_court_verified: bool = False,
) -> EmpiricalFrontierClosure:
    """Return the verified Bubbles–CFBE Ω empirical state at this snapshot.

    Owner-value promotion is fail-closed: a raw pair count can never promote the
    lane. The caller must supply both the measured-pair count and an affirmative
    result from the existing owner-value court. The closure compiler itself
    cannot synthesize owner minutes, interventions, corrections, acceptance, or
    independent readback.
    """
    if owner_value_pairs < 0:
        raise ValueError("OWNER_VALUE_PAIR_COUNT_NONNEGATIVE_REQUIRED")
    if owner_value_court_verified and owner_value_pairs < MINIMUM_OWNER_VALUE_PAIRS:
        raise ValueError("OWNER_VALUE_COURT_CANNOT_VERIFY_SUBMINIMUM_COHORT")

    owner_proven = owner_value_court_verified and owner_value_pairs >= MINIMUM_OWNER_VALUE_PAIRS
    owner_state = ProofState.HOSTED_VERIFIED if owner_proven else ProofState.HOLD_REAL_OBSERVATIONS
    owner_gate = None if owner_proven else "MINIMUM_10_COURT_VERIFIED_OWNER_VALUE_PAIRS_REQUIRED"

    lanes = (
        _lane(
            "DURABLE_RUNTIME",
            "Provider-hostable resumable agent/workflow execution",
            ProofState.HOSTED_VERIFIED,
            (
                "github-actions:33443307546",
                "artifact:9777076355",
                "runtime-receipt:cc9c095a48a158438bd573b06a8ad471abc4583dbe9fb94d0e094bed00d583b8",
                "pr:920",
            ),
            (
                "non-root hosted runtime",
                "restart and persistence readback",
                "idempotent replay",
                "rollback verified",
                "provider effects disabled",
            ),
            "SERVING_PROVIDER_DEPLOYMENT_AND_HEALTH_READBACK_REQUIRED",
            "provider deployment authority",
        ),
        _lane(
            "TOOLBOX_GOVERNANCE",
            "Authenticated, versioned, least-privilege toolboxes",
            ProofState.SOURCE_READY,
            (
                "benchmarking/cfbe_omega/federation_frontier_refresh_v2.py:toolbox_governance_plan",
                "bubbles-provider-surface-readback",
            ),
            (
                "tool catalog contract",
                "version pinning contract",
                "least-privilege allowlist contract",
                "authenticated connector surfaces exist",
            ),
            "MANAGED_VERSIONED_TOOLBOX_PROVIDER_READBACK_REQUIRED",
            "toolbox provider",
        ),
        _lane(
            "WORKLOAD_IDENTITY",
            "Keyless workload identity and ADC transport",
            ProofState.PROVIDER_VERIFIED,
            (
                "github-actions:33450913670",
                "artifact:9779745969",
                "source:a0bcec57c6447f50176c86641fc76e8952076331",
                "issue:945",
            ),
            (
                "GitHub OIDC authenticated to Google WIF",
                "active canonical deployer service account observed",
                "WIF pool/provider ACTIVE",
                "external_account ADC credential verified",
                "service-account impersonation bound",
                "no long-lived service-account key",
                "no mutation or provider effect",
            ),
            "BRANCH_SCOPED_WIF_HARDENING_AND_DEPLOYMENT_ROLES_REMAIN_SEPARATE",
            "Google Cloud security/deployment configuration",
        ),
        _lane(
            "LIVE_AGENT_TELEMETRY",
            "Standardized mission/agent/tool/guardrail telemetry",
            ProofState.OBSERVED_PARTIAL,
            (
                "pr:916",
                "pr:919",
                "benchmarking/cfbe_omega/federation_frontier_refresh_v2.py:agent_telemetry_gate",
                "bubbles-provider-surface-readback",
            ),
            (
                "normalized observation ingress",
                "mission/provider readback signals observed",
                "agent telemetry schema and sensitive-field policy present",
            ),
            "SERVING_OTEL_EXPORTER_FRESHNESS_AND_COMPLETENESS_READBACK_REQUIRED",
            "serving telemetry backend",
        ),
        _lane(
            "TRACE_EVAL_OPTIMIZER",
            "Trace-derived evaluation, failure clustering, and guarded optimization",
            ProofState.HOSTED_VERIFIED,
            (
                "failed-g0-run:33450180065",
                "repaired-g0-run:33450913670",
                "pr:944",
                "benchmarking/cfbe_omega/federation_frontier_refresh_v2.py:evaluation_campaign_plan",
                "benchmarking/cfbe_omega/federation_frontier_refresh_v2.py:agent_optimizer_gate",
            ),
            (
                "real failure trace preserved",
                "failure cause isolated",
                "minimum repair admitted",
                "same provider path rerun passed",
                "optimizer promotion remains court-gated",
            ),
            "PROSPECTIVE_OPTIMIZER_NO_REGRESSION_COHORT_REQUIRED",
            "CFBE champion/challenger court",
        ),
        _lane(
            "SLSA_ATTESTATION",
            "Signed source/build provenance and artifact attestation",
            ProofState.PROVIDER_VERIFIED,
            (
                "github-actions:33450394976",
                "github-attestation:44277491",
                "rekor-log-index:2669237108",
                "artifact:9779538934",
                "subject-sha256:2f0d622c0b274a79867a59613734dc3b944aa5ba426eb6d75d258623270fb38b",
            ),
            (
                "GitHub artifact attestation created",
                "Sigstore signer workflow bound",
                "Rekor transparency entry observed",
                "exact subject digest machine-verified",
                "no registry/deployment effect",
            ),
        ),
        _lane(
            "MULTI_PROVIDER_ROUTING",
            "Observed same-task multi-model/provider routing",
            ProofState.HOLD_CREDENTIAL_BINDING,
            (
                "workflow:.github/workflows/openrouter-processor-mesh-canary.yml",
                "historical-run:33295207089",
                "pr:817",
            ),
            (
                "zero-cost provider canary exists",
                "credential absence fails closed before model execution",
                "provider/model route is not inferred from source",
            ),
            "OPENROUTER_ACTIONS_CREDENTIAL_BINDING_REQUIRED",
            "GitHub Actions secret / OpenRouter credential owner",
        ),
        _lane(
            "AI_ASSET_VALUE_GOVERNANCE",
            "AI asset inventory linked to proof, risk, ownership, and value state",
            ProofState.HOSTED_VERIFIED,
            (
                "benchmarking/cfbe_omega/FEDERATION_COMPETITIVE_UPGRADES_100_20260901.csv",
                "benchmarking/cfbe_omega/CFBE_HYPERLEVERAGE_100_CLOSURE_20260901.json",
                "benchmarking/cfbe_omega/empirical_frontier_closure_v1.py",
            ),
            (
                "100 capability genes inventoried",
                "proof state separated from provider state",
                "nine empirical frontier lanes inventoried",
                "terminal gate and gate owner explicit",
            ),
            "CROSS_PROVIDER_AI_ASSET_DISCOVERY_READBACK_REQUIRED_FOR_ENTERPRISE_COMPLETENESS",
            "connected provider estate",
        ),
        _lane(
            "OWNER_VALUE",
            "Sustained owner-value matched-pair evidence",
            owner_state,
            (
                "evidenceops/caseforge/owner_value_deployment_court_v2.py",
                "federation/sentinel_omega/owner_value_ingress.py",
                f"observed-owner-value-pairs:{owner_value_pairs}",
                f"owner-value-court-verified:{str(owner_value_court_verified).lower()}",
            ),
            (
                "proof-bound pair compiler exists",
                "minimum cohort is 10 measured pairs",
                "independent readback required",
                "court verification required in addition to pair count",
                "owner minutes/interventions/clarifications/corrections cannot be inferred",
            ),
            owner_gate,
            "prospective mission observations" if owner_gate else None,
        ),
    )

    closure = EmpiricalFrontierClosure(
        schema=SCHEMA,
        snapshot_date_sast=SNAPSHOT_DATE_SAST,
        source_main_sha="a0bcec57c6447f50176c86641fc76e8952076331",
        lanes=lanes,
    ).validate()
    without_hash = closure.to_dict(include_hash=False)
    return EmpiricalFrontierClosure(
        schema=closure.schema,
        snapshot_date_sast=closure.snapshot_date_sast,
        source_main_sha=closure.source_main_sha,
        lanes=closure.lanes,
        closure_sha256=canonical_hash(without_hash),
    ).validate()


def next_executable_lanes(closure: EmpiricalFrontierClosure) -> tuple[str, ...]:
    """Return lanes where another safe no-effect proof step is executable now."""
    executable: list[str] = []
    for lane in closure.lanes:
        if lane.lane_id in {
            "DURABLE_RUNTIME",
            "LIVE_AGENT_TELEMETRY",
            "TRACE_EVAL_OPTIMIZER",
            "AI_ASSET_VALUE_GOVERNANCE",
        }:
            executable.append(lane.lane_id)
    return tuple(sorted(executable))


def held_external_lanes(closure: EmpiricalFrontierClosure) -> tuple[str, ...]:
    held = [
        lane.lane_id
        for lane in closure.lanes
        if lane.state in {
            ProofState.HOLD_PROVIDER_AUTHORITY,
            ProofState.HOLD_CREDENTIAL_BINDING,
            ProofState.HOLD_REAL_OBSERVATIONS,
        }
        or lane.state is ProofState.SOURCE_READY
        or lane.terminal_gate is not None
    ]
    return tuple(sorted(set(held)))


def render_json(
    *,
    owner_value_pairs: int = 0,
    owner_value_court_verified: bool = False,
) -> str:
    return json.dumps(
        current_snapshot(
            owner_value_pairs=owner_value_pairs,
            owner_value_court_verified=owner_value_court_verified,
        ).to_dict(),
        indent=2,
        sort_keys=True,
    ) + "\n"


if __name__ == "__main__":
    print(render_json(), end="")
