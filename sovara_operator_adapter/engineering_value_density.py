from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValueDensitySnapshot:
    snapshot_id: str
    added_lines: int
    distinct_files: int
    canonical_behavior_tests: int
    control_tables: int
    execution_surface_classes_proven: int = 0
    proof_current: bool = True
    critical_regression: bool = False
    material_cost_known: bool = True

    def validate(self) -> None:
        if not self.snapshot_id:
            raise ValueError("snapshot_id is required")
        if self.added_lines <= 0:
            raise ValueError("added_lines must be > 0")
        for name, value in (
            ("distinct_files", self.distinct_files),
            ("canonical_behavior_tests", self.canonical_behavior_tests),
            ("control_tables", self.control_tables),
            ("execution_surface_classes_proven", self.execution_surface_classes_proven),
        ):
            if value < 0:
                raise ValueError(f"{name} must be >= 0")
        if self.distinct_files == 0 or self.control_tables == 0:
            raise ValueError("distinct_files and control_tables must be > 0")

    @property
    def source_test_density_per_kloc(self) -> float | None:
        self.validate()
        if self.canonical_behavior_tests == 0:
            return None
        return self.canonical_behavior_tests / (self.added_lines / 1000.0)

    @property
    def lines_per_canonical_test(self) -> float | None:
        self.validate()
        if self.canonical_behavior_tests == 0:
            return None
        return self.added_lines / self.canonical_behavior_tests

    @property
    def canonical_tests_per_control_table(self) -> float:
        self.validate()
        return self.canonical_behavior_tests / self.control_tables


@dataclass(frozen=True)
class ValueDensityDelta:
    code_growth_factor: float
    test_growth_factor: float
    control_growth_factor: float
    proof_code_growth_ratio: float
    source_test_density_change_pct: float
    tests_per_control_change_pct: float
    execution_surface_breadth_delta: int
    verdict: str
    authorizes_pruning: bool = False


def _pct_change(current: float, baseline: float) -> float:
    if baseline == 0:
        raise ValueError("baseline must be non-zero")
    return ((current / baseline) - 1.0) * 100.0


def compare_value_density(
    baseline: ValueDensitySnapshot,
    current: ValueDensitySnapshot,
    *,
    compensating_verified_value_gain: bool,
    consecutive_value_dilution_checkpoints: int = 0,
) -> ValueDensityDelta:
    """Compare two comparable CFBE snapshots without turning activity into outcome.

    A negative source-test-density change is diagnostic only. It can trigger a
    watch or architecture hold, but it cannot authorize deletion or maturity
    promotion. Provider proof, quality, cost and verified value remain hard
    guardrails outside the activity ratios.
    """
    baseline.validate()
    current.validate()
    if baseline.canonical_behavior_tests <= 0:
        raise ValueError("baseline must be a runnable snapshot with canonical tests")
    if current.canonical_behavior_tests <= 0:
        raise ValueError("current snapshot must contain canonical tests")
    if consecutive_value_dilution_checkpoints < 0:
        raise ValueError("consecutive_value_dilution_checkpoints must be >= 0")

    baseline_density = baseline.source_test_density_per_kloc
    current_density = current.source_test_density_per_kloc
    assert baseline_density is not None and current_density is not None

    code_growth = current.added_lines / baseline.added_lines
    test_growth = current.canonical_behavior_tests / baseline.canonical_behavior_tests
    control_growth = current.control_tables / baseline.control_tables
    density_change = _pct_change(current_density, baseline_density)
    control_density_change = _pct_change(
        current.canonical_tests_per_control_table,
        baseline.canonical_tests_per_control_table,
    )

    if current.critical_regression:
        verdict = "HOLD_CRITICAL_REGRESSION"
    elif not current.proof_current:
        verdict = "HOLD_STALE_PROOF"
    elif not current.material_cost_known:
        verdict = "HOLD_UNKNOWN_MATERIAL_COST"
    elif consecutive_value_dilution_checkpoints >= 2 and not compensating_verified_value_gain:
        verdict = "HOLD_ARCHITECTURE_EXPANSION"
    elif density_change < 0 and compensating_verified_value_gain:
        verdict = "BALANCED_GROWTH_WITH_SOURCE_DENSITY_WATCH"
    elif density_change < 0:
        verdict = "SOURCE_DENSITY_WATCH"
    else:
        verdict = "VALUE_DENSITY_STABLE_OR_IMPROVING"

    return ValueDensityDelta(
        code_growth_factor=code_growth,
        test_growth_factor=test_growth,
        control_growth_factor=control_growth,
        proof_code_growth_ratio=test_growth / code_growth,
        source_test_density_change_pct=density_change,
        tests_per_control_change_pct=control_density_change,
        execution_surface_breadth_delta=(
            current.execution_surface_classes_proven
            - baseline.execution_surface_classes_proven
        ),
        verdict=verdict,
        authorizes_pruning=False,
    )
