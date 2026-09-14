from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from .forest_integrity_adapter import ForestIntegrityShadowAdapter
from .forest_omega import ForestFirstOmega, ForestOmegaContext


class IntegrityMode(str, Enum):
    LEGACY = "LEGACY"
    SHADOW = "SHADOW"
    ENFORCED = "ENFORCED"


DEFAULT_INTEGRITY_MODE = IntegrityMode.SHADOW


@dataclass(frozen=True, slots=True)
class IntegrityModeResult:
    mode: str
    matter_id: str
    decision_source: str
    selected_path: str | None
    legacy_selected_path: str | None
    typed_selected_path: str | None
    held: bool
    hold_reasons: tuple[str, ...]
    shadow_attached: bool
    execution_authorized: bool
    provider_effect_proved: bool
    authority_ceiling: str = "A1_INTERNAL"
    external_effect: bool = False
    runtime_default_changed: bool = False
    truth_class: str = "INTERNAL_ROUTING_CONTROL_STATE_NOT_PROVIDER_EFFECT"
    shadow_report: dict[str, Any] | None = None


def _legacy_selected(result: Any) -> str | None:
    selected = result.decision.get("selected_path")
    return None if not selected else str(selected.get("route_id"))


def _typed_selected(report: Any) -> str | None:
    return None if not report.admissible_paths else str(report.admissible_paths[0]["path_id"])


class ForestIntegrityModeController:
    """Bounded migration controller for legacy, shadow and typed routing.

    SHADOW is the repository default. ENFORCED only changes internal path
    selection; it does not authorize provider execution, external effect, owner
    release, filing, sending, publishing, spending or any other consequential
    action. Those authorities remain separate gates.
    """

    def __init__(self, *, mode: IntegrityMode = DEFAULT_INTEGRITY_MODE) -> None:
        self.mode = IntegrityMode(mode)
        self.legacy = ForestFirstOmega()
        self.typed = ForestIntegrityShadowAdapter()

    def run(self, context: ForestOmegaContext) -> IntegrityModeResult:
        legacy = self.legacy.run(context)
        legacy_selected = _legacy_selected(legacy)

        if self.mode is IntegrityMode.LEGACY:
            return IntegrityModeResult(
                mode=self.mode.value,
                matter_id=context.matter_id,
                decision_source="LEGACY_FOREST_OMEGA",
                selected_path=legacy_selected,
                legacy_selected_path=legacy_selected,
                typed_selected_path=None,
                held=bool(legacy.decision.get("owner_hold")),
                hold_reasons=("LEGACY_OWNER_HOLD",) if legacy.decision.get("owner_hold") else (),
                shadow_attached=False,
                execution_authorized=False,
                provider_effect_proved=False,
            )

        typed = self.typed.evaluate(context)
        typed_selected = _typed_selected(typed)

        if self.mode is IntegrityMode.SHADOW:
            return IntegrityModeResult(
                mode=self.mode.value,
                matter_id=context.matter_id,
                decision_source="LEGACY_FOREST_OMEGA_WITH_TYPED_SHADOW",
                selected_path=legacy_selected,
                legacy_selected_path=legacy_selected,
                typed_selected_path=typed_selected,
                held=bool(legacy.decision.get("owner_hold")),
                hold_reasons=("LEGACY_OWNER_HOLD",) if legacy.decision.get("owner_hold") else (),
                shadow_attached=True,
                execution_authorized=False,
                provider_effect_proved=False,
                shadow_report=asdict(typed),
            )

        hold_reasons: list[str] = []
        if typed_selected is None:
            hold_reasons.append("NO_ADMISSIBLE_TYPED_PATH")
        if context.consequential_action_planned:
            hold_reasons.append("OWNER_AUTHORITY_REQUIRED_FOR_CONSEQUENTIAL_ACTION")
        if context.owner_only_dependency:
            hold_reasons.append("OWNER_ONLY_DEPENDENCY")
        held = bool(hold_reasons)

        return IntegrityModeResult(
            mode=self.mode.value,
            matter_id=context.matter_id,
            decision_source="TYPED_ADMISSIBILITY_GATE",
            selected_path=None if held and typed_selected is None else typed_selected,
            legacy_selected_path=legacy_selected,
            typed_selected_path=typed_selected,
            held=held,
            hold_reasons=tuple(hold_reasons),
            shadow_attached=True,
            execution_authorized=False,
            provider_effect_proved=False,
            shadow_report=asdict(typed),
        )


__all__ = [
    "DEFAULT_INTEGRITY_MODE",
    "ForestIntegrityModeController",
    "IntegrityMode",
    "IntegrityModeResult",
]
