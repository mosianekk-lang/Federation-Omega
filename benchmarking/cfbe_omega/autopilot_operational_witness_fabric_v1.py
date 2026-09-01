from __future__ import annotations

"""AutoPilot Operational Witness Fabric v1.

The fabric compiles privacy-minimal, source-bound evidence witnesses from an
already completed operational runtime cycle. It does not call providers,
authorize effects, score metacognition, or claim that a witness bundle is an
observed metacognitive cohort.

The admitted adapter targets the existing Bubbles Command Bus
provider-surface-readback job on main. The separate workflow_run observer is
launched by GitHub only after that upstream workflow reaches a terminal state.
This gives the fabric two distinct proof axes:

1. an immutable execution witness for the Bubbles job; and
2. an independent GitHub-host completion readback witness for that execution.

External provider-surface readback remains a third, separately gated axis. A
real execution therefore remains independently host-verifiable even when FO,
Google, Archon or AFEME authentication is unavailable. In that case the fabric
emits execution + host readback and a bounded external-readback HOLD rather
than failing unrelated work or inventing external-provider proof.
"""

from argparse import ArgumentParser
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from benchmarking.cfbe_omega.autopilot_metacognition_observed_intake_v1 import (
    WITNESS_SCHEMA,
    EvidenceWitness,
)


SCHEMA = "CFBE-AUTOPILOT-OPERATIONAL-WITNESS-FABRIC-V1.1"
BUBBLES_PROBE_SCHEMA = "BUBBLES-PROVIDER-SURFACE-PROBE-V1"
ENVIRONMENT = "GITHUB_ACTIONS_MAIN_OPERATIONAL"
WORKFLOW_NAME = "Bubbles Command Bus"
JOB_NAME = "provider-surface-readback"

TRUSTED_READBACK_CLASSES = frozenset(
    {
        "AUTHENTICATED_READBACK_VERIFIED",
        "AUTHENTICATED_CAPABILITY_AUDIT_REACHABLE",
        "IDENTITY_TOKEN_READ_VERIFIED",
    }
)

FORBIDDEN_OUTPUT_KEYS = frozenset(
    {
        "prompt",
        "messages",
        "transcript",
        "body",
        "content",
        "response",
        "stdout",
        "stderr",
        "token",
        "secret",
        "api_key",
        "authorization",
    }
)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def canonical_hash(value: Any) -> str:
    return "sha256:" + sha256(canonical_json(value).encode("utf-8")).hexdigest()


def bytes_hash(value: bytes) -> str:
    return "sha256:" + sha256(value).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _is_sha(value: str) -> bool:
    return len(value) == 40 and all(character in "0123456789abcdef" for character in value.lower())


def _utc(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("WITNESS_FABRIC_OBSERVED_AT_INVALID") from exc
    _require(parsed.tzinfo is not None, "WITNESS_FABRIC_OBSERVED_AT_INVALID")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _surface_classifications(receipt: Mapping[str, Any]) -> dict[str, str]:
    surfaces = receipt.get("surfaces")
    _require(isinstance(surfaces, Mapping), "WITNESS_FABRIC_SURFACES_REQUIRED")
    classifications: dict[str, str] = {}
    for name, raw in surfaces.items():
        if not isinstance(raw, Mapping):
            continue
        classification = str(raw.get("classification") or "").strip()
        if classification:
            classifications[str(name)] = classification
    return classifications


def _verified_surface_names(classifications: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(sorted(name for name, state in classifications.items() if state in TRUSTED_READBACK_CLASSES))


def _assert_minimal_output(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            _require(normalized not in FORBIDDEN_OUTPUT_KEYS, "WITNESS_FABRIC_RAW_CONTENT_FIELD_FORBIDDEN")
            _assert_minimal_output(child)
    elif isinstance(value, list) or isinstance(value, tuple):
        for child in value:
            _assert_minimal_output(child)


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    source_head_sha: str
    run_id: str
    run_attempt: int
    event_name: str
    head_branch: str
    conclusion: str
    workflow: str
    job: str
    observed_at_utc: str

    def validate(self) -> "RuntimeIdentity":
        _require(_is_sha(self.source_head_sha), "WITNESS_FABRIC_SOURCE_SHA_INVALID")
        _require(self.run_id.isdigit() and int(self.run_id) > 0, "WITNESS_FABRIC_RUN_ID_INVALID")
        _require(self.run_attempt > 0, "WITNESS_FABRIC_RUN_ATTEMPT_INVALID")
        _require(self.event_name == "push", "WITNESS_FABRIC_REAL_MAIN_PUSH_REQUIRED")
        _require(self.head_branch == "main", "WITNESS_FABRIC_MAIN_BRANCH_REQUIRED")
        _require(self.conclusion == "success", "WITNESS_FABRIC_SUCCESSFUL_UPSTREAM_COMPLETION_REQUIRED")
        _require(self.workflow == WORKFLOW_NAME, "WITNESS_FABRIC_WORKFLOW_MISMATCH")
        _require(self.job == JOB_NAME, "WITNESS_FABRIC_JOB_MISMATCH")
        _utc(self.observed_at_utc)
        return self


@dataclass(frozen=True, slots=True)
class OperationalWitnessBundle:
    schema: str
    status: str
    blockers: tuple[str, ...]
    source_head_sha: str
    evidence_mode: str
    producer: str
    environment: str
    triggering_run_id: str
    triggering_run_attempt: int
    workflow: str
    job: str
    event_name: str
    head_branch: str
    conclusion: str
    provider_probe_schema: str
    provider_probe_digest: str
    verified_surface_count: int
    verified_surface_fingerprints: tuple[str, ...]
    execution_witness: dict[str, Any]
    host_readback_witness: dict[str, Any]
    readback_witness: dict[str, Any] | None
    observed_pair_emitted: bool
    observed_resume_emitted: bool
    provider_effect_authorized: bool
    stable_promotion_authorized: bool
    full_autopilot_runtime_proven: bool
    truth_boundary: tuple[str, ...]
    receipt_sha256: str = ""

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        payload["verified_surface_fingerprints"] = list(self.verified_surface_fingerprints)
        payload["truth_boundary"] = list(self.truth_boundary)
        if not include_hash:
            payload.pop("receipt_sha256", None)
        elif not payload["receipt_sha256"]:
            payload["receipt_sha256"] = canonical_hash({key: val for key, val in payload.items() if key != "receipt_sha256"})
        _assert_minimal_output(payload)
        return payload


def compile_bubbles_provider_readback_witnesses(
    *,
    identity: RuntimeIdentity,
    provider_probe_raw: bytes,
) -> OperationalWitnessBundle:
    identity.validate()
    try:
        probe = json.loads(provider_probe_raw)
    except json.JSONDecodeError as exc:
        raise ValueError("WITNESS_FABRIC_PROVIDER_PROBE_JSON_INVALID") from exc

    _require(isinstance(probe, Mapping), "WITNESS_FABRIC_PROVIDER_PROBE_OBJECT_REQUIRED")
    _require(probe.get("schema") == BUBBLES_PROBE_SCHEMA, "WITNESS_FABRIC_PROVIDER_PROBE_SCHEMA_MISMATCH")
    _require(probe.get("mutation_attempted") is False, "WITNESS_FABRIC_PROVIDER_MUTATION_REJECTED")
    _require(probe.get("secret_values_recorded") is False, "WITNESS_FABRIC_SECRET_RECORDING_REJECTED")

    classifications = _surface_classifications(probe)
    verified_surfaces = _verified_surface_names(classifications)
    observed_at = _utc(identity.observed_at_utc)
    probe_digest = bytes_hash(provider_probe_raw)
    surface_fingerprints = tuple(
        canonical_hash({"surface": name, "classification": classifications[name]})
        for name in verified_surfaces
    )

    execution_object = f"github-actions:{identity.run_id}:{identity.run_attempt}:{identity.job}"
    execution_payload = {
        "run_id": identity.run_id,
        "run_attempt": identity.run_attempt,
        "workflow": identity.workflow,
        "job": identity.job,
        "event_name": identity.event_name,
        "head_branch": identity.head_branch,
        "source_head_sha": identity.source_head_sha,
    }
    execution_ref = f"witness:github-actions:execution:{identity.run_id}:{identity.run_attempt}:{identity.job}"
    execution = EvidenceWitness(
        schema=WITNESS_SCHEMA,
        ref=execution_ref,
        kind="EXECUTION",
        evidence_class="IMMUTABLE_EXECUTION_RECEIPT",
        provider="github",
        environment=ENVIRONMENT,
        source_head_sha=identity.source_head_sha,
        provider_object_id=execution_object,
        digest=canonical_hash(execution_payload),
        verified=True,
        independent=False,
        observed_at_utc=observed_at,
    ).validate(expected_source_head_sha=identity.source_head_sha)

    host_readback_payload = {
        "run_id": identity.run_id,
        "run_attempt": identity.run_attempt,
        "workflow": identity.workflow,
        "event_name": identity.event_name,
        "head_branch": identity.head_branch,
        "source_head_sha": identity.source_head_sha,
        "conclusion": identity.conclusion,
        "completed_at_utc": observed_at,
    }
    host_readback_ref = f"witness:github-actions:completion-readback:{identity.run_id}:{identity.run_attempt}"
    host_readback = EvidenceWitness(
        schema=WITNESS_SCHEMA,
        ref=host_readback_ref,
        kind="READBACK",
        evidence_class="PROVIDER_LIVE_INDEPENDENT_READBACK",
        provider="github",
        environment=ENVIRONMENT,
        source_head_sha=identity.source_head_sha,
        provider_object_id=f"github-actions-workflow-run:{identity.run_id}:{identity.run_attempt}",
        digest=canonical_hash(host_readback_payload),
        verified=True,
        independent=True,
        observed_at_utc=observed_at,
    ).validate(expected_source_head_sha=identity.source_head_sha)

    external_readback: EvidenceWitness | None = None
    if verified_surfaces:
        external_readback_object = f"bubbles-provider-readback:{identity.run_id}:{identity.run_attempt}"
        external_readback_ref = f"witness:external-provider-readback:{identity.run_id}:{identity.run_attempt}"
        external_readback = EvidenceWitness(
            schema=WITNESS_SCHEMA,
            ref=external_readback_ref,
            kind="READBACK",
            evidence_class="PROVIDER_LIVE_INDEPENDENT_READBACK",
            provider="federation-provider-surfaces",
            environment=ENVIRONMENT,
            source_head_sha=identity.source_head_sha,
            provider_object_id=external_readback_object,
            digest=probe_digest,
            verified=True,
            independent=True,
            observed_at_utc=observed_at,
        ).validate(expected_source_head_sha=identity.source_head_sha)

    if external_readback:
        status = "WITNESS_EXECUTION_HOST_AND_EXTERNAL_READBACK_VERIFIED"
        blockers: tuple[str, ...] = ()
        evidence_mode = "OBSERVED_OPERATIONAL_WITNESS_INPUT"
    else:
        status = "WITNESS_EXECUTION_AND_HOST_READBACK_VERIFIED_EXTERNAL_READBACK_HELD"
        blockers = ("EXTERNAL_PROVIDER_READBACK_NOT_VERIFIED",)
        evidence_mode = "OBSERVED_OPERATIONAL_HOST_WITNESS_INPUT"

    base = OperationalWitnessBundle(
        schema=SCHEMA,
        status=status,
        blockers=blockers,
        source_head_sha=identity.source_head_sha,
        evidence_mode=evidence_mode,
        producer="BUBBLES_COMMAND_BUS_WORKFLOW_RUN_OBSERVER",
        environment=ENVIRONMENT,
        triggering_run_id=identity.run_id,
        triggering_run_attempt=identity.run_attempt,
        workflow=identity.workflow,
        job=identity.job,
        event_name=identity.event_name,
        head_branch=identity.head_branch,
        conclusion=identity.conclusion,
        provider_probe_schema=BUBBLES_PROBE_SCHEMA,
        provider_probe_digest=probe_digest,
        verified_surface_count=len(verified_surfaces),
        verified_surface_fingerprints=surface_fingerprints,
        execution_witness=asdict(execution),
        host_readback_witness=asdict(host_readback),
        readback_witness=asdict(external_readback) if external_readback else None,
        observed_pair_emitted=False,
        observed_resume_emitted=False,
        provider_effect_authorized=False,
        stable_promotion_authorized=False,
        full_autopilot_runtime_proven=False,
        truth_boundary=(
            "The GitHub workflow_run completion event is an independent provider-native readback of the Bubbles workflow execution, not proof of external FO/Google/Archon/AFEME semantics.",
            "An external provider-surface readback witness is included only when authenticated provider classifications are actually present.",
            "Provider response bodies, prompts, transcripts, credentials, stdout and stderr are intentionally excluded; only hashes, classifications and runtime identity are retained.",
            "A host-verified external-readback HOLD remains valid observed operational witness material and must not stall unrelated work or be promoted into external-provider proof.",
            "The bundle is witness material for later observed-operational pairing, but it is not itself a matched metacognition pair or cross-process resume observation.",
            "A successful witness bundle does not grant provider-effect authority, stable policy promotion, provider-native durable runtime status or full-autopilot maturity.",
        ),
    )
    digest = canonical_hash(base.to_dict(include_hash=False))
    result = OperationalWitnessBundle(**{**asdict(base), "receipt_sha256": digest})
    _assert_minimal_output(result.to_dict())
    return result


def main() -> int:
    parser = ArgumentParser(description="Compile privacy-minimal AutoPilot operational witnesses from a completed Bubbles provider-readback cycle.")
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True, type=int)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--head-branch", required=True)
    parser.add_argument("--conclusion", required=True)
    parser.add_argument("--workflow", default=WORKFLOW_NAME)
    parser.add_argument("--job", default=JOB_NAME)
    parser.add_argument("--observed-at-utc", required=True)
    parser.add_argument("--provider-readback-receipt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    identity = RuntimeIdentity(
        source_head_sha=args.source_sha,
        run_id=str(args.run_id),
        run_attempt=args.run_attempt,
        event_name=args.event_name,
        head_branch=args.head_branch,
        conclusion=args.conclusion,
        workflow=args.workflow,
        job=args.job,
        observed_at_utc=args.observed_at_utc,
    )
    result = compile_bubbles_provider_readback_witnesses(
        identity=identity,
        provider_probe_raw=Path(args.provider_readback_receipt).read_bytes(),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "schema": result.schema,
        "status": result.status,
        "source_head_sha": result.source_head_sha,
        "verified_surface_count": result.verified_surface_count,
        "host_readback_witness_emitted": True,
        "external_readback_witness_emitted": result.readback_witness is not None,
        "observed_pair_emitted": result.observed_pair_emitted,
        "provider_effect_authorized": result.provider_effect_authorized,
        "receipt_sha256": result.receipt_sha256,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
