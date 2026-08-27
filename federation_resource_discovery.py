"""Proof-ordered Federation execution-route discovery.

Registrations are candidates, not execution proof. A route may be declared
exhausted only after capability, installation, source identity and receipt
evidence have all been inspected in that order.
"""

DISCOVERY_ORDER = ("capabilities", "commands", "source", "receipts")


def classify_execution_route(*, function_name, source_sha256, capabilities, commands, receipts):
    capability = next(
        (item for item in capabilities if item.get("name") == function_name and item.get("enabled") is True),
        None,
    )
    if capability is None:
        return {"state": "NOT_REGISTERED", "routeExhaustionAllowed": True, "checked": DISCOVERY_ORDER}

    installs = [
        item for item in commands
        if item.get("event") == "MODULE_INSTALLED_FROM_DRIVE"
        and item.get("status") == "DONE"
        and item.get("sourceSha256") == source_sha256
    ]
    if not installs:
        return {"state": "REGISTERED_NOT_INSTALLED", "routeExhaustionAllowed": False, "checked": DISCOVERY_ORDER}

    verified = next(
        (item for item in receipts
         if item.get("functionName") == function_name
         and item.get("sourceSha256") == source_sha256
         and item.get("semanticState") == "VERIFIED"),
        None,
    )
    if verified is None:
        return {"state": "INSTALLED_UNPROVEN", "routeExhaustionAllowed": False, "checked": DISCOVERY_ORDER}

    return {
        "state": "VERIFIED_LIVE",
        "routeExhaustionAllowed": False,
        "checked": DISCOVERY_ORDER,
        "proofRef": verified.get("proofRef"),
    }
