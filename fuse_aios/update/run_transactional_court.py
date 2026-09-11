#!/usr/bin/env python3
import json
from transactional_host import TransactionalHost

BASE = "a" * 64
GOOD = "b" * 64
BAD = "c" * 64
CRASH = "d" * 64


def scenario_commit():
    host = TransactionalHost("0.1.0", BASE)
    host.stage("0.1.1", GOOD)
    host.activate()
    assert host.evaluate_health(True) == "COMMITTED"
    assert host.active_slot == "B"
    return host.receipt()


def scenario_failed_health():
    host = TransactionalHost("0.1.0", BASE)
    host.stage("0.1.1-bad", BAD)
    host.activate()
    assert host.evaluate_health(False) == "ROLLED_BACK"
    assert host.active_slot == "A"
    assert host.slots["B"].status == "QUARANTINED"
    return host.receipt()


def scenario_interrupted_activation():
    host = TransactionalHost("0.1.0", BASE)
    host.stage("0.1.1-interrupted", CRASH)
    host.activate()
    assert host.recover_after_interruption() == "ROLLED_BACK"
    assert host.active_slot == "A"
    return host.receipt()


def main():
    scenarios = {
        "commit": scenario_commit(),
        "failed_health": scenario_failed_health(),
        "interrupted_activation": scenario_interrupted_activation(),
    }
    out = {
        "schema": "FUSE-AIOS-TRANSACTIONAL-COURT-V1",
        "status": "PASS",
        "scenarios": scenarios,
        "truth": "TRANSACTIONAL_UPDATE_STATE_MACHINE_PROVED",
        "real_block_device_rollback_proved": False,
        "firmware_or_bootloader_rollback_proved": False,
    }
    print(json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    main()
