from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from benchmarking.cfbe_omega.bco_provider_readback_adapter_v1 import (
    ProviderReadbackLevel,
    bind_provider_readback_request,
    compile_provider_readback_evidence,
    evaluate_provider_readback_floor,
)
from federation.mission_ir import MissionIR
from formation_omega.durable_mission_runtime_v1 import DurableMissionRuntimeV1
from formation_omega.mission_convergence import WorkItem, WorkStatus

_SCHEMA = "BCO-PROVIDER-READBACK-CONTINUITY-V1"
_POLICY = "bco-provider-readback-proof-floor-v1"
_ENVIRONMENT = "github-actions-bubbles-receipt-consumer-v1"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _mission_id(head_sha: str) -> str:
    cleaned = str(head_sha).strip().lower()
    if len(cleaned) < 12:
        raise ValueError("BCO_PROVIDER_CONTINUITY_HEAD_SHA_REQUIRED")
    return f"BCO-PROVIDER-READ-{cleaned[:12].upper()}"


def _mission(head_sha: str) -> MissionIR:
    cleaned = str(head_sha).strip().lower()
    return MissionIR(
        mission_id=_mission_id(cleaned),
        objective="Resume a BCΩ mission only at the evidence level actually proven by the Bubbles provider receipt.",
        domain="BCO_PROVIDER_READBACK",
        outcome_contract="One restart-safe provider-read request governed by an explicit readback proof floor.",
        source_frontier=f"main@{cleaned}",
        privacy_class="PUBLIC",
        rights_state="NOT_APPLICABLE",
        effect_class="READ_ONLY",
        rollback_required=False,
        proof_requirements=("READBACK",),
    ).normalized()


def _runtime(root: str | Path, head_sha: str) -> DurableMissionRuntimeV1:
    cleaned = str(head_sha).strip().lower()
    return DurableMissionRuntimeV1(
        root,
        source_frontier=f"main@{cleaned}",
        policy_sha256=_POLICY,
        environment_sha256=_ENVIRONMENT,
    )


@dataclass(frozen=True, slots=True)
class ProviderContinuityReceipt:
    schema: str
    state: str
    mission_id: str
    source_head_sha: str
    resume_state: str
    checkpoint_id: str
    request_id: str
    request_state: str
    required_level: str
    observed_level: str
    provider_receipt_sha256: str
    pending_request_count: int
    work_state: str
    mutation_attempted: bool
    provider_effect_authorized: bool
    financial_effect_authorized: bool
    publication_authorized: bool
    truth_boundary: tuple[str, ...]


def prepare(root: str | Path, *, head_sha: str, created_at: str | None = None) -> dict[str, Any]:
    runtime = _runtime(root, head_sha)
    mission = _mission(head_sha)
    runtime.open(mission, required_proof_axes=("source",), trace_id=f"provider-read:{head_sha[:12]}:prepare")
    runtime.set_work_item(
        mission.mission_id,
        WorkItem.create(
            work_id="PROVIDER-READ",
            lane="provider-read",
            objective="Bind only a provider receipt that meets the required readback proof floor.",
        ),
    )
    request = runtime.request(
        mission.mission_id,
        step_id="PROVIDER-READ",
        request_type="PROVIDER_READBACK",
        target="bubbles-provider-surface-readback",
        reason="Wait for the immutable Bubbles provider receipt and grade its actual proof strength.",
        input_identity={
            "source_head_sha": str(head_sha).strip().lower(),
            "required_level": ProviderReadbackLevel.ACTION_SPECIFIC_AUTHENTICATED_READ.name,
            "mutation": "NONE",
        },
        continuation_key="grade-bubbles-provider-receipt",
        effect_class="READ_ONLY",
        created_at=created_at or _now(),
    )
    checkpoint = runtime.checkpoint(
        mission.mission_id,
        trace_id=f"provider-read:{head_sha[:12]}:prepare",
        created_at=created_at or _now(),
    )
    return {
        "schema": _SCHEMA,
        "state": "PREPARED_PENDING_PROVIDER_RECEIPT",
        "mission_id": mission.mission_id,
        "request_id": request.request_id,
        "checkpoint_id": checkpoint.checkpoint_id,
        "provider_effect_authorized": False,
    }


def resume_and_bind(
    root: str | Path,
    *,
    head_sha: str,
    receipt: Mapping[str, Any],
    receipt_ref: str,
    now: str | None = None,
) -> ProviderContinuityReceipt:
    runtime = _runtime(root, head_sha)
    mission = _mission(head_sha)
    resume = runtime.resume(
        mission,
        now=now or _now(),
        trace_id=f"provider-read:{head_sha[:12]}:resume",
    )
    pending = runtime.pending_requests(mission.mission_id)
    if len(pending) != 1:
        raise ValueError(f"BCO_PROVIDER_CONTINUITY_PENDING_REQUEST_COUNT:{len(pending)}")
    request = pending[0]
    evidence = compile_provider_readback_evidence(receipt, proof_ref=receipt_ref)
    floor = evaluate_provider_readback_floor(
        evidence,
        ProviderReadbackLevel.ACTION_SPECIFIC_AUTHENTICATED_READ,
    )
    binding = bind_provider_readback_request(
        runtime,
        mission.mission_id,
        request.request_id,
        receipt,
        receipt_ref=receipt_ref,
        required_level=ProviderReadbackLevel.ACTION_SPECIFIC_AUTHENTICATED_READ,
        resolved_at=now or _now(),
    )
    if binding.request_resolved:
        runtime.update_work_status(
            mission.mission_id,
            "PROVIDER-READ",
            WorkStatus.VERIFIED,
            result_refs=(receipt_ref, evidence.receipt_sha256),
        )
    projection = runtime.project(mission.mission_id)
    request_state = runtime.requests(mission.mission_id)[0].state
    pending_count = len(runtime.pending_requests(mission.mission_id))
    return ProviderContinuityReceipt(
        schema=_SCHEMA,
        state=binding.state,
        mission_id=mission.mission_id,
        source_head_sha=str(head_sha).strip().lower(),
        resume_state=resume.state,
        checkpoint_id=resume.checkpoint_id,
        request_id=request.request_id,
        request_state=request_state,
        required_level=floor.required_level,
        observed_level=floor.observed_level,
        provider_receipt_sha256=evidence.receipt_sha256,
        pending_request_count=pending_count,
        work_state=projection.work_items["PROVIDER-READ"].status.value,
        mutation_attempted=evidence.mutation_attempted,
        provider_effect_authorized=False,
        financial_effect_authorized=False,
        publication_authorized=False,
        truth_boundary=(
            "this court consumes an existing read-only receipt and performs no provider call",
            "a workflow success does not upgrade the receipt evidence level",
            "an unmet authenticated-read floor remains a hold with the BCΩ request pending",
            "a met floor resolves only a read-only evidence request and grants no effect authority",
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the BCΩ provider-readback continuity court.")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--root", required=True)
    prepare_parser.add_argument("--head-sha", required=True)
    prepare_parser.add_argument("--output", required=True)

    resume_parser = sub.add_parser("resume")
    resume_parser.add_argument("--root", required=True)
    resume_parser.add_argument("--head-sha", required=True)
    resume_parser.add_argument("--receipt", required=True)
    resume_parser.add_argument("--receipt-ref", required=True)
    resume_parser.add_argument("--output", required=True)

    args = parser.parse_args()
    if args.command == "prepare":
        payload = prepare(args.root, head_sha=args.head_sha)
    else:
        receipt = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
        payload = asdict(
            resume_and_bind(
                args.root,
                head_sha=args.head_sha,
                receipt=receipt,
                receipt_ref=args.receipt_ref,
            )
        )

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
