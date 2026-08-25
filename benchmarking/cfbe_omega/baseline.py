from __future__ import annotations

from .benchmark_engine import Dimension


BASELINE_DIMENSIONS = [
    Dimension("D01", "Agent platform & lifecycle", 6, 3.0, 0.70),
    Dimension("D02", "Model portfolio & intelligent routing", 4, 1.5, 0.50),
    Dimension("D03", "Tools, connectors, APIs & MCP interoperability", 6, 3.5, 0.85),
    Dimension("D04", "Enterprise grounding, knowledge & semantic context", 5, 3.0, 0.70),
    Dimension("D05", "Workflow automation & eventing", 4, 3.0, 0.75),
    Dimension("D06", "Multi-agent orchestration", 8, 3.0, 0.65),
    Dimension("D07", "Observability, tracing & evaluation", 7, 2.5, 0.65),
    Dimension("D08", "Identity, secrets & Zero Trust", 8, 2.0, 0.60),
    Dimension("D09", "AI security, safety, red teaming & runtime guards", 8, 3.5, 0.75),
    Dimension("D10", "Secure SDLC, CI/CD & software supply chain", 8, 3.5, 0.85),
    Dimension("D11", "Reliability, SRE & incident operations", 4, 3.0, 0.70),
    Dimension("D12", "Governance, provenance & auditability", 8, 4.5, 0.90),
    Dimension("D13", "Data platform, analytics & semantic BI", 4, 2.0, 0.65),
    Dimension("D14", "Cloud runtime, elasticity & scaling", 5, 1.5, 0.40),
    Dimension("D15", "AI infrastructure, sovereign/edge/physical AI", 4, 0.5, 0.20),
    Dimension("D16", "Developer experience & platform engineering", 5, 3.0, 0.75),
    Dimension("D17", "Enterprise productivity UX", 8, 2.5, 0.65),
    Dimension("D18", "Continuous learning & institutional memory", 6, 4.0, 0.85),
    Dimension("D19", "Cost, FinOps & performance efficiency", 8, 2.0, 0.50),
    Dimension("D20", "Engineering operating model & team capability", 4, 2.5, 0.60),
]

