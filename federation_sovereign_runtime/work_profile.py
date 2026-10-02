from __future__ import annotations

from dataclasses import dataclass


WORK_PUBLIC_SNAPSHOT_DATE = "2026-09-05"
WORK_PUBLIC_SOURCES = (
    "https://help.openai.com/en/articles/20001275",
    "https://help.openai.com/en/articles/20001280-using-cloud-browser-in-chatgpt",
    "https://openai.com/index/chatgpt-for-your-most-ambitious-work/",
)


@dataclass(frozen=True)
class WorkCapabilityGene:
    gene_id: str
    public_work_mechanism: str
    federation_target: str
    proof_gate: str


WORK_CAPABILITY_GENES = (
    WorkCapabilityGene(
        "WORK-G01",
        "Long multi-step work with finished deliverables",
        "MissionGraph + Artifact Foundry + Mission Completion Gate",
        "end-to-end deliverable cohort",
    ),
    WorkCapabilityGene(
        "WORK-G02",
        "Cloud browser on a separate remote computer",
        "SOVARA-governed Remote Execution Cell",
        "sandbox identity + provider-native action/readback canary",
    ),
    WorkCapabilityGene(
        "WORK-G03",
        "Continue after user leaves or closes device",
        "Durable external scheduler/executor independent of chat-turn lifetime",
        "fresh-process and host-loss resume proof",
    ),
    WorkCapabilityGene(
        "WORK-G04",
        "Pause for user input/sign-in/confirmation",
        "Human-First Boundary Interrupt Broker",
        "precise owner-decision and resume proof",
    ),
    WorkCapabilityGene(
        "WORK-G05",
        "Scheduled/triggered/monitoring tasks",
        "Federation Event Trigger Plane + Bubbles/ChatBridge continuity",
        "scheduled/event receiver-native proof",
    ),
    WorkCapabilityGene(
        "WORK-G06",
        "Connected apps and files",
        "Capability Registry + connector-neutral resource graph",
        "connector read/write authority and readback matrix",
    ),
    WorkCapabilityGene(
        "WORK-G07",
        "Projects preserve related chats/files/instructions",
        "Mission Workspace Capsule + KDV/ChatBridge",
        "cross-run restore fidelity",
    ),
    WorkCapabilityGene(
        "WORK-G08",
        "User can review progress, steer, and approve important actions",
        "Mission Steering Bus + Human-First consequential gate",
        "mid-mission steering and approval-fatigue cohort",
    ),
    WorkCapabilityGene(
        "WORK-G09",
        "Documents, spreadsheets, presentations, reports and Sites",
        "Artifact Foundry with domain-specific quality courts",
        "artifact semantic/visual acceptance",
    ),
    WorkCapabilityGene(
        "WORK-G10",
        "Desktop/browser computer use across apps and files",
        "Sovereign Computer Fabric with least-privilege action leases",
        "computer-use task/readback/rollback cohort",
    ),
)


__all__ = [
    "WORK_CAPABILITY_GENES",
    "WORK_PUBLIC_SNAPSHOT_DATE",
    "WORK_PUBLIC_SOURCES",
    "WorkCapabilityGene",
]
