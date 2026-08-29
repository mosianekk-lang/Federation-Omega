"""Behavior-neutral ProofOS baseline probe.

This module deliberately has no imports, side effects, runtime registration, provider
calls, or executable behavior. Its sole purpose is to make ProofOS exercise the
existing full root unittest fallback against the unmodified canonical main behavior,
so a pre-existing suite failure can be distinguished from a safety-spine regression.
"""

PROBE_SCHEMA = "FEDOMEGA_PROOFOS_BASELINE_PROBE_V1"
EXTERNAL_EFFECT = False
