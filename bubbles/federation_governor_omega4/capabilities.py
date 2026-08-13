from __future__ import annotations

from .registry import FederationRegistry

DEFAULT_CAPABILITIES = [
    ("Bubbles", "Federation Mission Control", ["orchestration", "routing", "anti-stall"]),
    ("Lex", "Legal Mission Controller", ["legal", "analysis", "strategy"]),
    ("LabourProcedure", "Labour Procedure Specialist", ["legal", "labour", "procedure"]),
    ("Ledger", "Evidence & Verification Architect", ["evidence", "provenance", "verification"]),
    ("Forge", "Applied AI / Software Engineer", ["software", "code", "runtime"]),
    ("Sparks", "Cloud / Platform Engineer", ["cloud", "deployment", "provider"]),
    ("Patch", "Reliability / SRE Engineer", ["reliability", "recovery", "stall"]),
    ("Sentinel", "Security & Governance Architect", ["security", "governance", "privacy"]),
    ("Bridge", "Integration & Automation Engineer", ["integration", "connector", "automation"]),
]


def install_defaults(registry: FederationRegistry) -> None:
    for capability_id, role, tags in DEFAULT_CAPABILITIES:
        registry.register_capability(
            capability_id,
            role,
            tags,
            f"FEDERATION_CAPABILITY::{capability_id}",
        )
