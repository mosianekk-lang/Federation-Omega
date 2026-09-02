from __future__ import annotations

import hashlib
import json
import unittest

try:
    from . import test_fdof_v1
    from .fdof_v1 import FDOF_VERSION
except ImportError:
    import test_fdof_v1
    from fdof_v1 import FDOF_VERSION


def stable_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(value):
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_fdof_v1)
    result = unittest.TestResult()
    suite.run(result)
    receipt = {
        "schema": "FEDERATION-DISTRIBUTED-OPERATING-FABRIC-PROOF-V1",
        "fdof_version": FDOF_VERSION,
        "tests_run": result.testsRun,
        "failures": [case.id() for case, _ in result.failures],
        "errors": [case.id() for case, _ in result.errors],
        "successful": result.wasSuccessful(),
        "proof_scope": "DETERMINISTIC_LOCAL_CONTROL_FABRIC",
        "provider_runtime_proven": False,
        "provider_effect_proven": False,
        "owner_value_proven": False,
        "claims": [
            "SOL62 primitives are reused rather than duplicated",
            "executor source registration does not imply health",
            "fresh health is mandatory for routing",
            "cost and authority routing fail closed",
            "consequential routes require rollback and readback capability",
            "transition execution reuses fencing leases",
            "runtime conflict resolution prefers provider-native evidence",
            "governance generation anchor preserves owner directive semantics",
            "source and runtime dimensions remain independently resolvable",
        ],
    }
    receipt["receipt_sha256"] = sha256(receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
