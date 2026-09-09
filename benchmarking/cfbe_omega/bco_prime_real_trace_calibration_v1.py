from __future__ import annotations

"""Compatibility facade for the BCΩ-PRIME real-trace calibration engine.

The admitted calibration implementation remains byte-for-byte preserved in
``bco_prime_real_trace_calibration_v1_engine``.  This facade changes only the
default Git first-parent history retrieval ceiling so the existing 60-trace
assurance floor is not starved as the repository grows.  The chronological
future window, holdout floor, scoring logic, live-weight immutability and
external-effect boundary remain owned by the preserved engine.
"""

import json

from benchmarking.cfbe_omega import bco_prime_real_trace_calibration_v1_engine as _engine


# Keep the public API identical to the preserved engine, then override only the
# history-bound entry points below.
for _exported_name in _engine.__all__:
    globals()[_exported_name] = getattr(_engine, _exported_name)

DEFAULT_HISTORY_LIMIT = 256


def collect_real_mission_traces(
    repo,
    *,
    source_head_sha=None,
    cohort_size=_engine.DEFAULT_COHORT_SIZE,
    future_window=_engine.DEFAULT_FUTURE_WINDOW,
    history_limit=DEFAULT_HISTORY_LIMIT,
):
    """Collect genuine first-parent traces with a growth-safe default scan.

    No synthetic traces are introduced and no trace, holdout or future-window
    assurance threshold is reduced.  Callers may still provide an explicit
    ``history_limit`` when deliberately running a bounded experiment.
    """

    return _engine.collect_real_mission_traces(
        repo,
        source_head_sha=source_head_sha,
        cohort_size=cohort_size,
        future_window=future_window,
        history_limit=history_limit,
    )


def _parser():
    parser = _engine._parser()
    parser.set_defaults(history_limit=DEFAULT_HISTORY_LIMIT)
    return parser


def main() -> int:
    args = _parser().parse_args()
    traces = collect_real_mission_traces(
        args.repo,
        source_head_sha=args.source_head,
        cohort_size=args.cohort_size,
        future_window=args.future_window,
        history_limit=args.history_limit,
    )
    receipt = _engine.evaluate_calibration(
        traces,
        holdout_size=args.holdout_size,
        future_window=args.future_window,
    )
    print(json.dumps(receipt.to_dict(), sort_keys=True))
    return 0


def __getattr__(name: str):
    """Preserve access to private diagnostic helpers used by incumbent courts."""

    return getattr(_engine, name)


__all__ = tuple(dict.fromkeys((*_engine.__all__, "DEFAULT_HISTORY_LIMIT")))


if __name__ == "__main__":
    raise SystemExit(main())
