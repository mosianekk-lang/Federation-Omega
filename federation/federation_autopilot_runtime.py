from __future__ import annotations

"""Federation Autopilot unattended-operation runtime contract.

This module composes existing Federation controls instead of creating another
sovereign scheduler or authority plane. It is designed for recurring unattended
cycles (for example a ChatGPT scheduled automation) and answers four questions:

1. Is this receiver current with the canonical FKPF knowledge head?
2. Which pending lanes may continue without owner presence?
3. Which lanes must be held because they are consequential or unproven?
4. Did a missed tick require catch-up before normal work resumes?

Execution authority remains with the existing Federation provider/tool surfaces.
This module never grants email, filing, settlement, IAM, secret, spend,
destructive, publication, traffic-cutover, or calendar-write authority.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import argparse
import json
from pathlib import Path
from typing import Iterable

from federation.bubbles_autopilot_policy import (
    HIGH_CONSEQUENCE,
    NO_EFFECT,
    REVERSIBLE_EXTERNAL,
    REVERSIBLE_INTERNAL,
    AutopilotStep,
    decide_autopilot,
)

SCHEMA = "FEDERATION-AUTOPILOT-RUNTIME-V1"
DEFAULT_TICK_MINUTES = 60

FORBIDDEN_UNATTENDED_OPERATIONS = frozenset(
    {
        "EMAIL_SEND",
        "LEGAL_FILE_OR_SERVE",
        "SETTLEMENT_OR_CONCESSION",
        "IAM_OR_ROLE_CHANGE",
        "SECRET_OR_CREDENTIAL_CHANGE",
        "BILLING_OR_SPEND",
        "DELETE_OR_DESTRUCTIVE",
        "PUBLICATION_OR_EXTERNAL_POST",
        "PRODUCTION_TRAFFIC_CUTOVER",
        "CALENDAR_WRITE",
    }
)


@dataclass(frozen=True, slots=True)
class AutopilotWorkItem:
    work_id: str
    objective: str
    effect_class: str
    operation_kind: str = "INTERNAL_WORK"
    priority: float = 0.0
    blocked: bool = False
    alternate_route_available: bool = False
    authority_proven: bool = False
    provider_readback_available: bool = False
    owner_choice_required: bool = False
    proof_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.work_id.strip():
            raise ValueError("FED_AUTOPILOT_WORK_ID_REQUIRED")
        if not self.objective.strip():
            raise ValueError("FED_AUTOPILOT_OBJECTIVE_REQUIRED")
        if self.effect_class not in {
            NO_EFFECT,
            REVERSIBLE_INTERNAL,
            REVERSIBLE_EXTERNAL,
            HIGH_CONSEQUENCE,
        }:
            raise ValueError("FED_AUTOPILOT_EFFECT_CLASS_INVALID")
        if self.priority < 0:
            raise ValueError("FED_AUTOPILOT_PRIORITY_NON_NEGATIVE_REQUIRED")


@dataclass(frozen=True, slots=True)
class AutopilotCycleInput:
    source_ref: str
    canonical_head: int
    local_watermark: int
    scheduled_at: str
    observed_at: str
    owner_present: bool
    work_items: tuple[AutopilotWorkItem, ...] = ()
    tick_minutes: int = DEFAULT_TICK_MINUTES

    def validate(self) -> None:
        if not self.source_ref.strip():
            raise ValueError("FED_AUTOPILOT_SOURCE_REF_REQUIRED")
        if self.canonical_head < 0 or self.local_watermark < 0:
            raise ValueError("FED_AUTOPILOT_HEAD_NON_NEGATIVE_REQUIRED")
        if self.local_watermark > self.canonical_head:
            raise ValueError("FED_AUTOPILOT_WATERMARK_AHEAD_OF_HEAD")
        if self.tick_minutes <= 0:
            raise ValueError("FED_AUTOPILOT_TICK_POSITIVE_REQUIRED")
        _parse_time(self.scheduled_at)
        _parse_time(self.observed_at)
        ids = [item.work_id for item in self.work_items]
        if len(ids) != len(set(ids)):
            raise ValueError("FED_AUTOPILOT_WORK_IDS_UNIQUE_REQUIRED")
        for item in self.work_items:
            item.validate()


@dataclass(frozen=True, slots=True)
class LaneDecision:
    work_id: str
    state: str
    continue_without_owner: bool
    owner_interrupt_required: bool
    reason: str


@dataclass(frozen=True, slots=True)
class AutopilotCycleReceipt:
    schema: str
    cycle_id: str
    source_ref: str
    canonical_head: int
    local_watermark: int
    currentness_state: str
    missed_ticks: int
    catch_up_required: bool
    selected_work_ids: tuple[str, ...]
    held_work_ids: tuple[str, ...]
    reroute_work_ids: tuple[str, ...]
    lane_decisions: tuple[LaneDecision, ...]
    continue_without_owner: bool
    owner_interrupt_required: bool
    next_tick_minutes: int
    provider_effect_authorized: bool
    high_consequence_authorized: bool
    truth_boundary: tuple[str, ...]
    receipt_sha256: str = ""

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        payload = asdict(self)
        for key in (
            "selected_work_ids",
            "held_work_ids",
            "reroute_work_ids",
            "truth_boundary",
        ):
            payload[key] = list(payload[key])
        payload["lane_decisions"] = [asdict(item) for item in self.lane_decisions]
        if not include_hash:
            payload.pop("receipt_sha256", None)
        return payload


def _parse_time(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("FED_AUTOPILOT_TIME_INVALID") from exc
    if dt.tzinfo is None:
        raise ValueError("FED_AUTOPILOT_TIMEZONE_REQUIRED")
    return dt.astimezone(timezone.utc)


def _missed_ticks(scheduled_at: str, observed_at: str, tick_minutes: int) -> int:
    scheduled = _parse_time(scheduled_at)
    observed = _parse_time(observed_at)
    delay_seconds = max(0.0, (observed - scheduled).total_seconds())
    tick_seconds = tick_minutes * 60
    return max(0, int(delay_seconds // tick_seconds))


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def _lane_decision(item: AutopilotWorkItem) -> LaneDecision:
    operation = item.operation_kind.strip().upper()
    if operation in FORBIDDEN_UNATTENDED_OPERATIONS:
        return LaneDecision(
            item.work_id,
            "HOLD_CONSEQUENTIAL_OPERATION",
            False,
            True,
            f"{operation} remains owner-gated while unattended.",
        )

    policy = decide_autopilot(
        AutopilotStep(
            step_id=item.work_id,
            effect_class=item.effect_class,
            blocked=item.blocked,
            alternate_route_available=item.alternate_route_available,
            authority_proven=item.authority_proven,
            provider_readback_available=item.provider_readback_available,
            owner_choice_required=item.owner_choice_required,
            proof_refs=item.proof_refs,
        )
    )
    return LaneDecision(
        item.work_id,
        policy.state,
        policy.continue_without_owner,
        policy.owner_interrupt_required,
        policy.reason,
    )


class FederationAutopilotRuntime:
    """Compile one proof-bounded unattended Federation cycle."""

    def run_cycle(self, cycle: AutopilotCycleInput) -> AutopilotCycleReceipt:
        cycle.validate()
        missed = _missed_ticks(cycle.scheduled_at, cycle.observed_at, cycle.tick_minutes)
        catch_up = cycle.local_watermark < cycle.canonical_head
        currentness = "ACTIVE_CURRENT" if not catch_up else "ACTIVE_STALE_CATCH_UP_REQUIRED"

        records = tuple(sorted(cycle.work_items, key=lambda item: (-item.priority, item.work_id)))
        decisions = tuple(_lane_decision(item) for item in records)
        by_id = {item.work_id: item for item in records}

        selected: list[str] = []
        held: list[str] = []
        reroute: list[str] = []

        if catch_up:
            # Normal mission work is held until the canonical head is consumed.
            held.extend(item.work_id for item in records)
        else:
            for decision in decisions:
                if decision.state == "ISOLATE_BLOCKED_LANE_AND_REROUTE":
                    reroute.append(decision.work_id)
                    continue
                if decision.continue_without_owner:
                    selected.append(decision.work_id)
                else:
                    held.append(decision.work_id)

        owner_interrupt = bool(held) and not selected and any(
            decision.owner_interrupt_required for decision in decisions
        )
        continue_without_owner = catch_up or bool(selected) or bool(reroute) or not records

        unsigned = {
            "schema": SCHEMA,
            "source_ref": cycle.source_ref,
            "canonical_head": cycle.canonical_head,
            "local_watermark": cycle.local_watermark,
            "scheduled_at": cycle.scheduled_at,
            "observed_at": cycle.observed_at,
            "missed_ticks": missed,
            "selected": selected,
            "held": held,
            "reroute": reroute,
        }
        cycle_id = "AUTOPILOT-" + _digest(unsigned).split(":", 1)[1][:20].upper()

        base = AutopilotCycleReceipt(
            schema=SCHEMA,
            cycle_id=cycle_id,
            source_ref=cycle.source_ref,
            canonical_head=cycle.canonical_head,
            local_watermark=cycle.local_watermark,
            currentness_state=currentness,
            missed_ticks=missed,
            catch_up_required=catch_up,
            selected_work_ids=tuple(selected),
            held_work_ids=tuple(held),
            reroute_work_ids=tuple(reroute),
            lane_decisions=decisions,
            continue_without_owner=continue_without_owner,
            owner_interrupt_required=owner_interrupt,
            next_tick_minutes=cycle.tick_minutes,
            provider_effect_authorized=any(
                by_id[work_id].effect_class == REVERSIBLE_EXTERNAL for work_id in selected
            ),
            high_consequence_authorized=False,
            truth_boundary=(
                "Autopilot may continue safe/no-effect/internal-reversible work while the owner is absent.",
                "Reversible external work is eligible only when pre-existing route authority and provider-native readback are both proven and the operation is not on the unattended denylist.",
                "Email send, legal filing/service, settlement/concession, IAM/secret changes, billing/spend, destructive deletion, public posting, production cutover and calendar writes remain owner-gated while unattended.",
                "Catch-up/currentness work is allowed automatically, but normal mission work must not run from a stale FKPF watermark.",
                "This receipt is a control decision, not evidence that any provider action or mission result occurred.",
            ),
        )
        receipt_hash = _digest(base.to_dict(include_hash=False))
        return AutopilotCycleReceipt(**{**asdict(base), "receipt_sha256": receipt_hash})


def _load_work(path: str | None) -> tuple[AutopilotWorkItem, ...]:
    if not path:
        return ()
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("FED_AUTOPILOT_WORK_FILE_LIST_REQUIRED")
    return tuple(AutopilotWorkItem(**item) for item in raw)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile one Federation Autopilot unattended cycle receipt.")
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--canonical-head", required=True, type=int)
    parser.add_argument("--local-watermark", required=True, type=int)
    parser.add_argument("--scheduled-at", required=True)
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--tick-minutes", type=int, default=DEFAULT_TICK_MINUTES)
    parser.add_argument("--owner-present", action="store_true")
    parser.add_argument("--work-file")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    cycle = AutopilotCycleInput(
        source_ref=args.source_ref,
        canonical_head=args.canonical_head,
        local_watermark=args.local_watermark,
        scheduled_at=args.scheduled_at,
        observed_at=args.observed_at,
        owner_present=args.owner_present,
        work_items=_load_work(args.work_file),
        tick_minutes=args.tick_minutes,
    )
    receipt = FederationAutopilotRuntime().run_cycle(cycle)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "schema": receipt.schema,
        "cycle_id": receipt.cycle_id,
        "currentness_state": receipt.currentness_state,
        "selected_count": len(receipt.selected_work_ids),
        "held_count": len(receipt.held_work_ids),
        "owner_interrupt_required": receipt.owner_interrupt_required,
        "receipt_sha256": receipt.receipt_sha256,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
