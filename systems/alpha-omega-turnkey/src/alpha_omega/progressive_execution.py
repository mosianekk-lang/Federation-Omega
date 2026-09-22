from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from hashlib import sha256
import json
from time import perf_counter
from typing import Any, Callable, Iterable, Mapping

from .progressive_models import (
    AccelerationProfile,
    EffectClass,
    ProgressivePlan,
    StreamUnit,
    UnitState,
    WaveDecision,
    WaveExecutionReceipt,
    _SAFE_EFFECTS,
    _canonical_json,
    _stable_id,
)


class ProgressiveExecutionMixin:
    def next_wave(
        self,
        plan: ProgressivePlan,
        *,
        allow_provider_effects: bool = False,
        authorised_effect_classes: Iterable[EffectClass] = (),
    ) -> WaveDecision:
        return self.scheduler.next_wave(
            plan,
            allow_provider_effects=allow_provider_effects,
            authorised_effect_classes=authorised_effect_classes,
        )

    def start_wave(self, plan: ProgressivePlan, decision: WaveDecision) -> None:
        for unit_id in decision.runnable:
            unit = plan.unit(unit_id)
            if unit.state is not UnitState.PENDING:
                raise ValueError(f"unit is not pending: {unit_id}")
            unit.state = UnitState.RUNNING
            unit.attempts += 1
        for unit_id in decision.held:
            if plan.unit(unit_id).state is UnitState.PENDING:
                plan.unit(unit_id).state = UnitState.HELD
        for unit_id in decision.blocked:
            if plan.unit(unit_id).state is UnitState.PENDING:
                plan.unit(unit_id).state = UnitState.BLOCKED

    def record_result(
        self,
        plan: ProgressivePlan,
        unit_id: str,
        *,
        success: bool,
        output_refs: Iterable[str] = (),
        proof_refs: Iterable[str] = (),
        duration_ms: float | None = None,
        failure_fingerprint: str | None = None,
        reused: bool | None = None,
    ) -> UnitState:
        unit = plan.unit(unit_id)
        if unit.state not in {UnitState.RUNNING, UnitState.READY, UnitState.PENDING}:
            raise ValueError(f"unit cannot accept a result from state {unit.state.value}")
        unit.output_refs = tuple(str(item).strip() for item in output_refs if str(item).strip())
        unit.proof_refs = tuple(str(item).strip() for item in proof_refs if str(item).strip())
        unit.duration_ms = duration_ms
        if success and unit.proof_gate and not unit.proof_refs:
            success = False
            failure_fingerprint = f"MISSING_PROOF:{unit.proof_gate}"
        if success:
            unit.state = UnitState.SUCCEEDED
            if (
                unit.stage == "REGRESSION"
                and unit.metadata.get("reused")
                and not unit.metadata.get("reuse_counted")
            ):
                self._reuse_hits += 1
                self._work_units_avoided += int(unit.metadata.get("work_units_avoided", 1))
                unit.metadata["reuse_counted"] = True
            payload = {
                "mission_id": plan.mission_id,
                "cycle_id": plan.cycle_id,
                "unit_id": unit.unit_id,
                "stream_id": unit.stream_id,
                "stage": unit.stage,
                "path_id": unit.path_id,
                "reusable_key": unit.reusable_key,
                "output_refs": list(unit.output_refs),
                "proof_refs": list(unit.proof_refs),
                "duration_ms": duration_ms,
                "reused": bool(unit.metadata.get("reused")) if reused is None else bool(reused),
            }
            self.learning.append("SUCCESS", payload)
            return unit.state

        fingerprint = (failure_fingerprint or _stable_id("FAIL", unit.stage, unit.objective)).strip()
        unit.failure_fingerprint = fingerprint
        circuit_open = self.scheduler.register_failure(fingerprint)
        unit.state = UnitState.CIRCUIT_OPEN if circuit_open else UnitState.FAILED
        self.learning.append(
            "FAILURE",
            {
                "mission_id": plan.mission_id,
                "cycle_id": plan.cycle_id,
                "unit_id": unit.unit_id,
                "stream_id": unit.stream_id,
                "stage": unit.stage,
                "path_id": unit.path_id,
                "failure_fingerprint": fingerprint,
                "circuit_open": circuit_open,
                "duration_ms": duration_ms,
                "required_next_route": "MATERIALLY_DIFFERENT" if circuit_open else "REPAIR_OR_RETRY_WITHIN_BUDGET",
            },
        )
        return unit.state

    def reopen_held(self, plan: ProgressivePlan, unit_ids: Iterable[str]) -> None:
        for unit_id in unit_ids:
            unit = plan.unit(unit_id)
            if unit.state is not UnitState.HELD:
                raise ValueError(f"unit is not held: {unit_id}")
            unit.state = UnitState.PENDING

    def checkpoint(self, plan: ProgressivePlan) -> dict[str, Any]:
        payload = plan.to_dict()
        payload_hash = sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
        path = self.checkpoints / f"{plan.mission_id}-{payload_hash[:12]}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        receipt = {
            "mission_id": plan.mission_id,
            "cycle_id": plan.cycle_id,
            "checkpoint": str(path),
            "payload_sha256": payload_hash,
            "ledger_verified": self.learning.verify(),
            "states": self.state_counts(plan),
            "acceleration": asdict(self.acceleration_profile()),
            "truth_boundary": plan.truth_boundary,
        }
        self.learning.append("CHECKPOINT", receipt)
        return receipt

    def acceleration_profile(self) -> AccelerationProfile:
        return self.learning.acceleration_profile(self._reuse_hits, self._work_units_avoided)

    @staticmethod
    def state_counts(plan: ProgressivePlan) -> dict[str, int]:
        counts = {state.value: 0 for state in UnitState}
        for unit in plan.units.values():
            counts[unit.state.value] += 1
        return counts

    @staticmethod
    def complete(plan: ProgressivePlan) -> bool:
        material = [unit for unit in plan.units.values() if unit.effect_class in _SAFE_EFFECTS]
        return bool(material) and all(unit.state in {UnitState.SUCCEEDED, UnitState.SKIPPED} for unit in material)

    def run_wave(
        self,
        plan: ProgressivePlan,
        executors: Mapping[str, Callable[[StreamUnit], Mapping[str, Any]]],
        *,
        allow_provider_effects: bool = False,
        authorised_effect_classes: Iterable[EffectClass] = (),
    ) -> WaveDecision:
        """Execute one collision-safe wave concurrently and record deterministically.

        Executors are keyed by stage. Safe independent units run through a
        bounded thread pool; provider/consequential units remain serialized by
        the scheduler and require explicit admission. Results are written to the
        plan and learning ledger only after the concurrent work fan-in, avoiding
        concurrent canonical writes.
        """
        decision = self.next_wave(
            plan,
            allow_provider_effects=allow_provider_effects,
            authorised_effect_classes=authorised_effect_classes,
        )
        self.start_wave(plan, decision)
        started = perf_counter()
        results: dict[str, dict[str, Any]] = {}

        def execute(unit: StreamUnit) -> dict[str, Any]:
            executor = executors.get(unit.stage)
            if executor is None:
                return {
                    "success": False,
                    "failure_fingerprint": f"NO_EXECUTOR:{unit.stage}",
                    "duration_ms": 0.0,
                }
            unit_started = perf_counter()
            try:
                result = dict(executor(unit))
            except Exception as exc:  # noqa: BLE001 - convert runtime error to governed failure
                result = {
                    "success": False,
                    "failure_fingerprint": f"EXECUTOR_EXCEPTION:{unit.stage}:{type(exc).__name__}",
                    "exception_type": type(exc).__name__,
                }
            result.setdefault("duration_ms", round((perf_counter() - unit_started) * 1000.0, 3))
            return result

        if decision.runnable:
            workers = min(len(decision.runnable), self.scheduler.max_parallel_safe)
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="alpha-omega") as pool:
                futures = {pool.submit(execute, plan.unit(unit_id)): unit_id for unit_id in decision.runnable}
                for future in as_completed(futures):
                    unit_id = futures[future]
                    results[unit_id] = future.result()

        # Deterministic fan-in: canonical plan/ledger writes follow selected order.
        for unit_id in decision.runnable:
            result = results[unit_id]
            self.record_result(
                plan,
                unit_id,
                success=bool(result.get("success")),
                output_refs=result.get("output_refs", ()),
                proof_refs=result.get("proof_refs", ()),
                duration_ms=result.get("duration_ms"),
                failure_fingerprint=result.get("failure_fingerprint"),
                reused=result.get("reused"),
            )

        wall_ms = round((perf_counter() - started) * 1000.0, 3)
        summed_ms = round(
            sum(float(results[unit_id].get("duration_ms") or 0.0) for unit_id in decision.runnable),
            3,
        )
        ratio = None
        if len(decision.runnable) >= 2 and wall_ms > 0:
            ratio = round(summed_ms / wall_ms, 4)
        succeeded = tuple(
            unit_id for unit_id in decision.runnable if plan.unit(unit_id).state is UnitState.SUCCEEDED
        )
        failed = tuple(
            unit_id
            for unit_id in decision.runnable
            if plan.unit(unit_id).state in {UnitState.FAILED, UnitState.CIRCUIT_OPEN}
        )
        receipt = WaveExecutionReceipt(
            wave_id=decision.wave_id,
            runnable=decision.runnable,
            succeeded=succeeded,
            failed=failed,
            held=decision.held,
            blocked=decision.blocked,
            wall_duration_ms=wall_ms,
            summed_unit_duration_ms=summed_ms,
            measured_parallelism_ratio=ratio,
            ledger_verified=self.learning.verify(),
        )
        self.last_wave_receipt = receipt
        self.learning.append("WAVE_COMPLETED", asdict(receipt))
        return decision

    def run_local_canary(
        self,
        plan: ProgressivePlan,
        *,
        max_waves: int = 100,
    ) -> dict[str, Any]:
        """Run the complete safe A1 scope through a deterministic local adapter.

        This is a real local runtime canary for scheduling, collision control,
        parallel fan-out/fan-in, proof capture, learning and checkpointing. It
        performs no provider or external effect and cannot prove provider
        deployment.
        """
        output_dir = self.workspace / "progressive_outputs" / plan.mission_id
        output_dir.mkdir(parents=True, exist_ok=True)

        def executor(unit: StreamUnit) -> Mapping[str, Any]:
            payload = {
                "mission_id": plan.mission_id,
                "cycle_id": plan.cycle_id,
                "unit_id": unit.unit_id,
                "stream_id": unit.stream_id,
                "stage": unit.stage,
                "path_id": unit.path_id,
                "objective": unit.objective,
                "effect_class": unit.effect_class.value,
                "truth_boundary": "LOCAL_A1_ONLY_NO_PROVIDER_EFFECT",
            }
            body = _canonical_json(payload)
            digest = sha256(body.encode("utf-8")).hexdigest()
            path = output_dir / f"{unit.unit_id}.json"
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return {
                "success": True,
                "output_refs": [str(path)],
                "proof_refs": [f"sha256:{digest}"],
                "reused": bool(unit.metadata.get("reused")),
            }

        stages = {unit.stage for unit in plan.units.values()}
        receipts = self.run_until_quiescent(
            plan,
            {stage: executor for stage in stages},
            max_waves=max_waves,
            checkpoint_each_wave=True,
        )
        checkpoint = self.checkpoint(plan)
        held_provider = tuple(
            unit.unit_id
            for unit in plan.units.values()
            if unit.state is UnitState.HELD
            and unit.effect_class in {EffectClass.PROVIDER_EFFECT, EffectClass.CONSEQUENTIAL}
        )
        safe_complete = self.complete(plan)
        state = (
            "LOCAL_A1_SAFE_SCOPE_VERIFIED_PROVIDER_HELD"
            if safe_complete and held_provider
            else "LOCAL_A1_MULTISTREAM_CANARY_VERIFIED"
            if safe_complete
            else "LOCAL_A1_MULTISTREAM_CANARY_INCOMPLETE"
        )
        measured = [
            receipt.measured_parallelism_ratio
            for receipt in receipts
            if receipt.measured_parallelism_ratio is not None
        ]
        result = {
            "state": state,
            "mission_id": plan.mission_id,
            "cycle_id": plan.cycle_id,
            "safe_scope_complete": safe_complete,
            "provider_units_held": list(held_provider),
            "wave_count": len(receipts),
            "max_measured_parallelism_ratio": max(measured) if measured else None,
            "acceleration": asdict(self.acceleration_profile()),
            "checkpoint": checkpoint,
            "ledger_verified": self.learning.verify(),
            "truth_boundary": {
                "local_runtime_proven": safe_complete,
                "provider_runtime_proven": False,
                "external_effect": False,
                "measured_parallelism_is_local_wave_only": True,
            },
        }
        receipt_path = self.checkpoints / f"{plan.mission_id}-local-canary.json"
        receipt_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result["receipt_path"] = str(receipt_path)
        self.learning.append("EXPERIMENT_RESULT", result)
        return result

    def run_until_quiescent(
        self,
        plan: ProgressivePlan,
        executors: Mapping[str, Callable[[StreamUnit], Mapping[str, Any]]],
        *,
        max_waves: int = 100,
        checkpoint_each_wave: bool = True,
        allow_provider_effects: bool = False,
        authorised_effect_classes: Iterable[EffectClass] = (),
    ) -> tuple[WaveExecutionReceipt, ...]:
        if max_waves < 1:
            raise ValueError("max_waves must be >= 1")
        receipts: list[WaveExecutionReceipt] = []
        for _ in range(max_waves):
            decision = self.run_wave(
                plan,
                executors,
                allow_provider_effects=allow_provider_effects,
                authorised_effect_classes=authorised_effect_classes,
            )
            if self.last_wave_receipt is not None:
                receipts.append(self.last_wave_receipt)
            if checkpoint_each_wave and decision.runnable:
                self.checkpoint(plan)
            if not decision.runnable:
                break
        else:
            self.learning.append(
                "CONSTRAINT",
                {
                    "mission_id": plan.mission_id,
                    "cycle_id": plan.cycle_id,
                    "constraint": "MAX_WAVES_EXHAUSTED",
                    "max_waves": max_waves,
                    "states": self.state_counts(plan),
                },
            )
        return tuple(receipts)
