# EvidenceOps Permanent Google Cloud Capability

This root capability makes the owner-authorized full project-control route discoverable and inheritable by every EvidenceOps system, subsystem, AI agent, worker, node and future element. It preserves the exact project breadth in `contract.json` and centralizes execution through the governed Omega operator and Secure Capability Box.

Every element receives the capability context automatically. It does not receive a raw credential. Cloud Run workloads use their attached user-managed service identity and ADC; GitHub uses WIF; chat routes use the supported MCP adapter and Secure Capability Box. The operator executes the requested Google Cloud action within the configured project and returns provider readback.

Readiness fails if any EvidenceOps build contract or root runtime manifest is missing the canonical contract reference:

```bash
python -m evidenceops.cloud_capability.inheritance --require-all-bound
python -m unittest discover -s evidenceops/cloud_capability/tests -v
```

The source contract is not deployment proof. `contract.json` keeps WIF, runtime identity, provider canary, semantic readback and multi-cycle permanence as separate proof states.
