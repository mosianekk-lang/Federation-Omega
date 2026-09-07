"""Bubbles host adapter for FUSE Master Bible Production Portfolio Compiler v1.

This adapter is no-effect and provider-neutral. It proves the existing Bubbles GitHub
host can consume the portfolio compiler and produce a deterministic current-debt / ready
wave receipt. It creates no scheduler, background daemon, provider identity, authority,
memory or truth plane.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json

from federation.fuse_master_bible_portfolio_compiler_v1 import (
    CapabilityDeficitRecord,
    GapRecord,
    MasterBiblePortfolioCompiler,
    MissionClass,
    MissionRecord,
)
from federation.fuse_mbmpc_pilf_closure_bridge_v1 import PStage

SCHEMA = "BUBBLES-FUSE-MASTER-BIBLE-PORTFOLIO-HOST-V1"
VERSION = "1.0.0"


def _digest(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + sha256(body.encode("utf-8")).hexdigest()


class BubblesMasterBiblePortfolioHost:
    def __init__(self, *, max_parallel: int = 4) -> None:
        self.compiler = MasterBiblePortfolioCompiler(max_parallel=max_parallel)

    def compile(self, **kwargs):
        return self.compiler.compile(**kwargs)


def run_host_canary(*, source_ref: str) -> dict[str, object]:
    """Run a deterministic no-effect portfolio compile through the Bubbles host adapter."""
    host = BubblesMasterBiblePortfolioHost(max_parallel=3)
    missions = (
        MissionRecord(
            mission_id="MISSION-ACTIVE-RUNTIME",
            objective="Operate a durable strategic runtime autonomically 24x7 with governed autonomy",
            state="SOURCE_ADMITTED_RUNTIME_BINDING_OPEN",
            proof_state="SOURCE_ADMITTED",
            next_action="bind the callable host/provider executor",
            authority_ceiling="A1_INTERNAL",
            priority="P0",
            mission_class=MissionClass.RUNTIME_MISSION,
        ),
        MissionRecord(
            mission_id="MISSION-ESTATE-HOST",
            objective="Bind an internal capability into the existing Bubbles host and prove behaviour",
            state="HOST_BOUND_BEHAVIOUR_OPEN",
            proof_state="SOURCE_ADMITTED / HOST_BOUND",
            next_action="run behaviour cohort",
            authority_ceiling="A1_INTERNAL",
            priority="P1",
            mission_class=MissionClass.CAPABILITY_MISSION,
        ),
        MissionRecord(
            mission_id="MISSION-HISTORICAL-DONE",
            objective="Historical predecessor already complete",
            state="COMPLETE_VERIFIED",
            proof_state="PRODUCTION_PROMOTED",
            next_action="none",
            authority_ceiling="A1_INTERNAL",
            current_p_stage=PStage.P15_PRODUCTION_PROMOTED,
            required_p_stage=PStage.P15_PRODUCTION_PROMOTED,
        ),
    )
    gaps = (
        GapRecord(
            gap_id="GAP-ACTIVE-EXECUTOR",
            mission_id="MISSION-ACTIVE-RUNTIME",
            requirement="Callable provider/runtime executor binding",
            classification="UNBOUND",
            criticality="P0",
            dependency_on=(),
            closure_route="bind callable machine executor",
            executor_profile="EXEC-PROVIDER-BINDING",
            proof_gate="exact host/provider identity plus callable no-effect readback",
            state="OPEN",
        ),
        GapRecord(
            gap_id="GAP-ACTIVE-RECOVERY",
            mission_id="MISSION-ACTIVE-RUNTIME",
            requirement="Crash/missed-run recovery proof",
            classification="UNPROVEN",
            criticality="P0",
            dependency_on=("GAP-ACTIVE-EXECUTOR",),
            closure_route="run crash-resume and missed-run recovery",
            executor_profile="EXEC-RECOVERY",
            proof_gate="restart/readback/idempotency receipt",
            state="OPEN",
        ),
        GapRecord(
            gap_id="GAP-ACTIVE-OWNER",
            mission_id="MISSION-ACTIVE-RUNTIME",
            requirement="Consequential owner-only approval",
            classification="OWNER_ONLY",
            criticality="P1",
            dependency_on=(),
            closure_route="owner approval only when production-critical",
            executor_profile="HUMAN_OWNER",
            proof_gate="exact owner authorization",
            state="HELD_EXACT_OWNER_INTERACTION",
        ),
        GapRecord(
            gap_id="GAP-ESTATE-BEHAVIOUR",
            mission_id="MISSION-ESTATE-HOST",
            requirement="Representative host behaviour cohort",
            classification="UNPROVEN",
            criticality="P1",
            dependency_on=(),
            closure_route="run representative host behaviour cohort",
            executor_profile="EXEC-HOST-WITNESS",
            proof_gate="host behaviour receipt",
            state="OPEN",
        ),
    )
    deficits = (
        CapabilityDeficitRecord(
            capability_id="CAP-SHARED-TRACE",
            capability="Shared execution/learning trace projection",
            classification="MISSING",
            reusable=True,
            affected_missions=("MISSION-ACTIVE-RUNTIME", "MISSION-ESTATE-HOST"),
            closure_strategy="compose one shared trace projection through existing receipts",
            owner_burden="REDUCE_OWNER_BURDEN",
            priority="P0",
        ),
    )
    receipt = host.compile(
        missions=missions,
        gaps=gaps,
        capability_deficits=deficits,
        active_mission_id="MISSION-ACTIVE-RUNTIME",
    )
    ready = tuple((item.mission_id, item.gap_id) for item in receipt.ready_wave)
    host_binding_verified = bool(
        receipt.active_required_mission_count == 2
        and ready
        and ready[0] == ("MISSION-ACTIVE-RUNTIME", "GAP-ACTIVE-EXECUTOR")
        and receipt.total_owner_only_debt == 1
        and receipt.shared_enablers
        and receipt.shared_enablers[0].capability_id == "CAP-SHARED-TRACE"
        and receipt.portfolio_complete_verified is False
    )
    payload: dict[str, object] = {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "HOST_BOUND_VERIFIED" if host_binding_verified else "HOST_BINDING_HELD",
        "source_ref": source_ref,
        "host_surface": "BUBBLES_COMMAND_BUS_CONTRACT_JOB",
        "execution_route": "tests.test_bubbles_control_plane -> BubblesWorkGraphAdapterTests -> BubblesMasterBiblePortfolioHost",
        "host_binding_verified": host_binding_verified,
        "portfolio_receipt": asdict(receipt),
        "provider_execution_attempted": False,
        "external_effect": False,
        "authority_delta": "NONE",
        "truth_boundary": (
            "This receipt proves the existing Bubbles GitHub-hosted contract surface imported and executed the "
            "FUSE Master Bible portfolio compiler on a deterministic no-effect mission/debt snapshot. It does not "
            "prove that every live Bible mission was provider-executed, nor does it create provider authority or "
            "production maturity beyond the supplied evidence."
        ),
    }
    payload["receipt_sha256"] = _digest(payload)
    return payload


__all__ = ["BubblesMasterBiblePortfolioHost", "SCHEMA", "VERSION", "run_host_canary"]
