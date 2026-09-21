from __future__ import annotations

"""FUSE Toka public-capability clean-room harvest v1.

Only publicly described functional outcomes are captured. Proprietary implementation
details are neither inferred nor copied. Sensitive offensive-access concepts are
translated into authorised defensive, forensic, simulation, evidence-handling, or
risk-reduction mechanisms before they can enter FUSE capability DNA.

This module is A0/A1 only: it performs source reading, classification, mapping,
compilation and proof reporting. It grants no surveillance, intrusion, physical-entry,
weapon, provider, credential, deployment, or external-effect authority.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
from html.parser import HTMLParser
import argparse
import json
import re
import urllib.request
from typing import Any, Iterable, Mapping

SCHEMA = "FUSE_TOKA_PUBLIC_CAPABILITY_HARVEST_V1"
VERSION = "1.0.0"
AUTHORITY_CEILING = "A1_INTERNAL"
INHERITANCE_SCOPE = "ALL_RELEVANT_CURRENT_AND_FUTURE_FUSE_FEDERATION_SYSTEMS"

PUBLIC_SOURCES: Mapping[str, str] = {
    "mission": "https://tokagroup.com/mission/",
    "home": "https://tokagroup.com/",
    "about": "https://tokagroup.com/about/",
    "platform_2026": "https://tokagroup.com/news/toka-advances-integrated-high-stakes-intelligence-operations/",
    "company_2026": "https://tokagroup.com/news/toka-deepens-engagement-with-u-s-and-allied-government-partners-names-gregg-smith-ceo/",
}

FUSE_TARGETS = (
    "HYPERCUBE_CFBE",
    "SUPERIOR_LOGIC_MISSION_IR",
    "FEDERATION_DIGITAL_TWIN",
    "EVIDENCEOPS",
    "PROOFOS",
    "REALITYGUARD",
    "SOVARA_AUTHORITY_ROUTER",
    "BUBBLES_COMMAND_BUS",
    "CAPABILITY_HEARTBEAT",
    "RUNTIME",
    "SECURITY",
    "VERIFICATION",
)

RESTRICTED_DIRECT_REPLICATION = frozenset({
    "Targeting & Tracking",
    "Suspect Surveillance",
    "SWAT Support",
    "Network Intelligence",
    "Systems Access & Collection",
    "Data Exfiltration",
    "Covert Entry",
    "Close Access Operations",
    "Tactical Operations",
    "Frictionless Surveillance",
})

SAFE_MECHANISMS: Mapping[str, str] = {
    "Intelligence, Surveillance, and Reconnaissance (ISR)": "authorised multi-source situational-awareness and evidence-fusion workflow",
    "Criminal Investigations": "case-scoped lawful investigative analytics and evidence correlation",
    "Cyber Operations": "defensive cyber operations, telemetry, incident response, and authorised lab simulation",
    "Force Protection": "personnel/site risk awareness and defensive force-protection planning",
    "Battlefield Reconnaissance": "authorised multi-source situational awareness without weapons guidance",
    "Targeting & Tracking": "authorised object/event correlation and tracking with explicit no-weaponisation invariant",
    "Counter Narcotics": "lawful investigative pattern analysis over authorised evidence",
    "Suspect Surveillance": "warrant/authority-scoped surveillance-evidence fusion without covert device compromise",
    "Video & Vehicle Forensics": "video, image, metadata, and vehicle-evidence forensic analysis",
    "SWAT Support": "incident-team coordination, deconfliction, safety, and risk-awareness support without attack guidance",
    "Network Intelligence": "defensive network telemetry, topology, anomaly, and threat-context correlation",
    "Systems Access & Collection": "credentialled and explicitly authorised system inventory/evidence collection with least privilege",
    "Data Exfiltration": "data-egress detection plus controlled, authorised evidence export with provenance and DLP",
    "Covert Entry": "physical-security red-team simulation and access-control assessment without bypass instructions",
    "Site Security": "site-security sensor fusion, anomaly detection, alerting, and defensive response coordination",
    "Close Access Operations": "authorised proximity risk-awareness and field-support simulation without covert intrusion",
    "Strategic Intelligence": "strategic multi-source intelligence fusion from authorised data sources",
    "Tactical Operations": "authorised tactical decision-support simulation with no offensive access or weapons control",
    "Frictionless Surveillance": "privacy-governed low-friction observation over authorised sources without covert compromise",
    "Real-time access to intelligence at scale": "streaming evidence ingestion, event-time fusion, prioritisation, and bounded low-latency readback",
    "Rapid deployment with reduced investigator risk": "portable deployment profiles, preflight checks, sandboxing, and remote evidence workflows that reduce operator exposure",
    "Critical-data geographic and locality correlation": "geospatially bounded correlation of authorised data with provenance and uncertainty labels",
    "Automated tagging": "deterministic and model-assisted metadata enrichment with provenance",
    "Automated classification": "policy-aware classification with confidence, review, and calibration controls",
    "Expanded APIs": "provider-neutral typed API contracts and capability adapters",
    "First/third-party ecosystem interoperability": "schema-first interoperability across approved internal and external systems",
    "Customer database integration": "least-privilege database adapters with lineage, minimisation, and readback",
    "AI platform integration": "provider-neutral AI routing through existing authority, privacy, cost, and proof controls",
    "Hardened scalable architecture": "fault-isolated, horizontally scalable, observable architecture with fail-closed controls",
    "Privacy and security in high-stakes operations": "information-flow labels, minimisation, encryption boundaries, auditability, and policy enforcement",
    "Non-obvious link discovery": "evidence-to-concept graph analytics with confidence and provenance",
    "Enduring intelligence": "durable, versioned intelligence objects with freshness, provenance, and semantic aging",
    "Specialized tools": "mission-specific bounded tool adapters composed behind common capability contracts",
    "Foundational analytics": "reusable analytics primitives, scoring, correlation, uncertainty, and reproducible transforms",
    "Integrated intelligence cycle": "collect-ingest-enrich-correlate-analyse-decide-verify-learn workflow bound to proof gates",
    "Intuitive operator experience and outcome orientation": "operator-centred mission views, prioritised actions, explainable status, and reduced cognitive load",
    "Complex digital data to actionable intelligence": "normalise, correlate, score, explain, and route complex authorised data into decision-ready evidence products",
    "Increase Operational Capabilities": "capability-gap discovery, reuse-first composition, and measured capability uplift",
    "Reduce Friction and Risk": "automation, safe defaults, reduced manual burden, reversible actions, and explicit risk controls",
    "Support Strategic, Cyber, and Tactical Efforts": "shared mission contracts and evidence fabric across strategic, defensive-cyber, and authorised tactical-support lanes",
    "Lawful & Transparent Digital Intelligence Collection": "authority-scoped collection, provenance, audit logs, minimisation, retention rules, and transparent proof receipts",
}

PUBLIC_SIGNALS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("TKA-FAM-001", "MISSION_FAMILY", "Intelligence, Surveillance, and Reconnaissance (ISR)", ("intelligence surveillance and reconnaissance",)),
    ("TKA-FAM-002", "MISSION_FAMILY", "Criminal Investigations", ("criminal investigations",)),
    ("TKA-FAM-003", "MISSION_FAMILY", "Cyber Operations", ("cyber operations",)),
    ("TKA-FAM-004", "MISSION_FAMILY", "Force Protection", ("force protection",)),
    ("TKA-MSN-001", "MISSION_USE_CASE", "Battlefield Reconnaissance", ("battlefield reconnaissance",)),
    ("TKA-MSN-002", "MISSION_USE_CASE", "Targeting & Tracking", ("targeting tracking",)),
    ("TKA-MSN-003", "MISSION_USE_CASE", "Counter Narcotics", ("counter narcotics",)),
    ("TKA-MSN-004", "MISSION_USE_CASE", "Suspect Surveillance", ("suspect surveillance",)),
    ("TKA-MSN-005", "MISSION_USE_CASE", "Video & Vehicle Forensics", ("video vehicle forensics",)),
    ("TKA-MSN-006", "MISSION_USE_CASE", "SWAT Support", ("swat support",)),
    ("TKA-MSN-007", "MISSION_USE_CASE", "Network Intelligence", ("network intelligence",)),
    ("TKA-MSN-008", "MISSION_USE_CASE", "Systems Access & Collection", ("systems access collection",)),
    ("TKA-MSN-009", "MISSION_USE_CASE", "Data Exfiltration", ("data exfiltration",)),
    ("TKA-MSN-010", "MISSION_USE_CASE", "Covert Entry", ("covert entry",)),
    ("TKA-MSN-011", "MISSION_USE_CASE", "Site Security", ("site security",)),
    ("TKA-MSN-012", "MISSION_USE_CASE", "Close Access Operations", ("close access operations",)),
    ("TKA-OPS-001", "OPERATING_MODEL", "Strategic Intelligence", ("strategic intelligence",)),
    ("TKA-OPS-002", "OPERATING_MODEL", "Tactical Operations", ("tactical operations",)),
    ("TKA-OPS-003", "OPERATING_MODEL", "Frictionless Surveillance", ("frictionless surveillance",)),
    ("TKA-PLT-001", "PLATFORM_FEATURE", "Real-time access to intelligence at scale", ("real time access to intelligence at scale",)),
    ("TKA-PLT-002", "PLATFORM_FEATURE", "Rapid deployment with reduced investigator risk", ("deployed quickly", "reduced risk to investigators")),
    ("TKA-PLT-003", "PLATFORM_FEATURE", "Critical-data geographic and locality correlation", ("critical data across geographic territories and localities",)),
    ("TKA-PLT-004", "PLATFORM_FEATURE", "Automated tagging", ("automated tagging",)),
    ("TKA-PLT-005", "PLATFORM_FEATURE", "Automated classification", ("classification", "manual sorting")),
    ("TKA-PLT-006", "PLATFORM_FEATURE", "Expanded APIs", ("expanded apis",)),
    ("TKA-PLT-007", "PLATFORM_FEATURE", "First/third-party ecosystem interoperability", ("first and third party ecosystems", "interoperability")),
    ("TKA-PLT-008", "PLATFORM_FEATURE", "Customer database integration", ("customer databases",)),
    ("TKA-PLT-009", "PLATFORM_FEATURE", "AI platform integration", ("ai platforms",)),
    ("TKA-PLT-010", "PLATFORM_FEATURE", "Hardened scalable architecture", ("hardened scalable architecture",)),
    ("TKA-PLT-011", "PLATFORM_FEATURE", "Privacy and security in high-stakes operations", ("maintain privacy and security",)),
    ("TKA-PLT-012", "PLATFORM_FEATURE", "Non-obvious link discovery", ("non obvious links",)),
    ("TKA-PLT-013", "PLATFORM_FEATURE", "Enduring intelligence", ("enduring intelligence",)),
    ("TKA-PLT-014", "PLATFORM_FEATURE", "Specialized tools", ("specialized tools",)),
    ("TKA-PLT-015", "PLATFORM_FEATURE", "Foundational analytics", ("foundational analytics",)),
    ("TKA-PLT-016", "PLATFORM_FEATURE", "Integrated intelligence cycle", ("integrated intelligence cycle",)),
    ("TKA-PLT-017", "PLATFORM_FEATURE", "Intuitive operator experience and outcome orientation", ("deeply intuitive", "owning the outcome")),
    ("TKA-PLT-018", "PLATFORM_FEATURE", "Complex digital data to actionable intelligence", ("complex digital data into actionable intelligence",)),
    ("TKA-GOV-001", "OPERATING_PRINCIPLE", "Increase Operational Capabilities", ("increase operational capabilities",)),
    ("TKA-GOV-002", "OPERATING_PRINCIPLE", "Reduce Friction and Risk", ("reduce friction and risk",)),
    ("TKA-GOV-003", "OPERATING_PRINCIPLE", "Support Strategic, Cyber, and Tactical Efforts", ("support strategic cyber and tactical efforts",)),
    ("TKA-GOV-004", "OPERATING_PRINCIPLE", "Lawful & Transparent Digital Intelligence Collection", ("lawful transparent digital intelligence collection",)),
)

@dataclass(frozen=True, slots=True)
class PublicCapability:
    capability_id: str
    category: str
    public_name: str
    safe_fuse_mechanism: str
    restricted_direct_replication: bool
    evidence_phrases: tuple[str, ...]
    fuse_targets: tuple[str, ...]
    source_urls: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value).lower()))


def canonical_hash(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("utf-8")
    ).hexdigest()


def load_capabilities() -> tuple[PublicCapability, ...]:
    source_urls = tuple(PUBLIC_SOURCES.values())
    return tuple(
        PublicCapability(
            capability_id=capability_id,
            category=category,
            public_name=public_name,
            safe_fuse_mechanism=SAFE_MECHANISMS[public_name],
            restricted_direct_replication=public_name in RESTRICTED_DIRECT_REPLICATION,
            evidence_phrases=phrases,
            fuse_targets=FUSE_TARGETS,
            source_urls=source_urls,
        )
        for capability_id, category, public_name, phrases in PUBLIC_SIGNALS
    )


def validate_corpus() -> dict[str, Any]:
    items = load_capabilities()
    ids = [item.capability_id for item in items]
    names = [item.public_name for item in items]
    if len(items) != 41:
        raise ValueError("TOKA_PUBLIC_CORPUS_EXPECTED_41_SIGNALS")
    if len(ids) != len(set(ids)) or len(names) != len(set(names)):
        raise ValueError("TOKA_PUBLIC_CORPUS_DUPLICATE_ID_OR_NAME")
    required_use_cases = {
        "Battlefield Reconnaissance", "Targeting & Tracking", "Counter Narcotics",
        "Suspect Surveillance", "Video & Vehicle Forensics", "SWAT Support",
        "Network Intelligence", "Systems Access & Collection", "Data Exfiltration",
        "Covert Entry", "Site Security", "Close Access Operations",
    }
    present = {item.public_name for item in items if item.category == "MISSION_USE_CASE"}
    if present != required_use_cases:
        raise ValueError("TOKA_PUBLIC_MISSION_USE_CASE_COVERAGE_INCOMPLETE")
    forbidden_mechanism_terms = (
        "credential theft", "steal credentials", "weapon targeting", "malware payload",
        "bypass access control", "exfiltrate data", "covertly enter",
    )
    for item in items:
        if not item.safe_fuse_mechanism.strip() or not item.evidence_phrases:
            raise ValueError("TOKA_PUBLIC_CAPABILITY_MAPPING_INCOMPLETE")
        if item.restricted_direct_replication and item.public_name not in RESTRICTED_DIRECT_REPLICATION:
            raise ValueError("TOKA_PUBLIC_RESTRICTED_MAPPING_INVALID")
        mechanism = item.safe_fuse_mechanism.lower()
        if any(term in mechanism for term in forbidden_mechanism_terms):
            raise ValueError("TOKA_PUBLIC_UNSAFE_DIRECT_REPLICATION")
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "capability_count": len(items),
        "restricted_transform_count": sum(i.restricted_direct_replication for i in items),
        "source_count": len(PUBLIC_SOURCES),
        "external_effect_authorized": False,
        "inheritance_scope": INHERITANCE_SCOPE,
        "corpus_sha256": canonical_hash([item.to_dict() for item in items]),
    }


def compile_cfbe_dna() -> tuple[Any, ...]:
    from benchmarking.cfbe_omega.scientific_capability_compiler_v2 import compile_capability_dna

    genes = []
    for item in load_capabilities():
        genes.append(
            compile_capability_dna({
                "capability_id": item.capability_id,
                "objective": item.safe_fuse_mechanism,
                "triggers": ("public capability delta", "mission capability gap", "hypercube harvest"),
                "inputs": ("authorised public or owner-controlled data", "mission contract", "authority envelope"),
                "outputs": ("bounded intelligence product", "proof receipt", "capability route"),
                "primitives": ("provenance", "classification", "correlation", "proof-before-claim", "authority-gating"),
                "invariants": (
                    "no proprietary implementation copying",
                    "no unauthorised surveillance or access",
                    "no weaponisation",
                    "external effects require separate authority",
                ),
                "failure_modes": ("source drift", "authority ambiguity", "privacy breach", "false-positive correlation"),
                "recovery_controls": ("source readback", "hold on unknown authority", "privacy minimisation", "independent proof"),
                "authority_requirements": ("A0/A1 for harvest", "separate exact authority for any external effect"),
                "proof_requirements": ("official public source", "clean-room mapping", "regression tests", "semantic readback"),
                "value_hypothesis": "Reduce time-to-evidence and owner burden while improving interoperability, safety and proof density.",
                "provenance_refs": item.source_urls,
                "license_class": "PUBLIC_FUNCTIONAL_DESCRIPTION_CLEAN_ROOM",
            })
        )
    return tuple(genes)


def hypercube_pattern_specs() -> tuple[dict[str, Any], ...]:
    return (
        {
            "pattern_id": "TOKA_REALTIME_INTELLIGENCE_FUSION",
            "source_family": "Toka public platform (clean-room mechanism abstraction)",
            "mechanism": "Fuse time-sensitive authorised data into a current evidence view with provenance, event-time handling and bounded latency.",
            "tags": ("runtime", "dynamic", "observability", "latency", "parallel"),
            "commercial_effect": ("lower time to evidence", "current situational context", "less manual fusion"),
            "clean_room_only": True,
        },
        {
            "pattern_id": "TOKA_AUTOMATED_TAG_CLASSIFY",
            "source_family": "Toka public platform (clean-room mechanism abstraction)",
            "mechanism": "Automate metadata tagging and classification with confidence, policy, provenance and review controls.",
            "tags": ("quality", "test", "proof", "dynamic", "observability"),
            "commercial_effect": ("less manual sorting", "faster triage", "consistent metadata"),
            "clean_room_only": True,
        },
        {
            "pattern_id": "TOKA_API_INTEROPERABILITY_FABRIC",
            "source_family": "Toka public platform (clean-room mechanism abstraction)",
            "mechanism": "Expose typed provider-neutral APIs and adapters for approved first-party, third-party, database and AI ecosystems.",
            "tags": ("runtime", "dependency", "dynamic", "resource", "quality"),
            "commercial_effect": ("faster integration", "provider portability", "lower connector friction"),
            "clean_room_only": True,
        },
        {
            "pattern_id": "TOKA_LINK_GRAPH_ANALYTICS",
            "source_family": "Toka public platform (clean-room mechanism abstraction)",
            "mechanism": "Connect authorised evidence into a provenance-bearing graph to surface non-obvious relationships with uncertainty labels.",
            "tags": ("unknown", "observability", "proof", "quality", "dependency"),
            "commercial_effect": ("faster relationship discovery", "explainable correlation", "higher analyst leverage"),
            "clean_room_only": True,
        },
        {
            "pattern_id": "TOKA_HARDENED_SCALABLE_PRIVACY_ARCH",
            "source_family": "Toka public platform (clean-room mechanism abstraction)",
            "mechanism": "Scale isolated workloads behind privacy, security, least-privilege, audit and fail-closed boundaries.",
            "tags": ("runtime", "resource", "recovery", "quality", "proof"),
            "commercial_effect": ("safer scale", "higher reliability", "lower operational risk"),
            "clean_room_only": True,
        },
        {
            "pattern_id": "TOKA_INTEGRATED_INTELLIGENCE_CYCLE",
            "source_family": "Toka public platform (clean-room mechanism abstraction)",
            "mechanism": "Compose collection, ingestion, enrichment, correlation, analysis, decision support, verification and learning into one evidence-bound cycle.",
            "tags": ("workflow", "runtime", "proof", "dependency", "quality"),
            "commercial_effect": ("end-to-end workflow", "lower handoff friction", "faster decision support"),
            "clean_room_only": True,
        },
        {
            "pattern_id": "TOKA_FRICTION_RISK_REDUCTION",
            "source_family": "Toka public platform (clean-room mechanism abstraction)",
            "mechanism": "Prefer remote, automated, reversible and evidence-rich routes that reduce operator burden and exposure while preserving authority boundaries.",
            "tags": ("risk", "dynamic", "recovery", "parallel", "commercial"),
            "commercial_effect": ("lower owner burden", "reduced operational risk", "faster safe execution"),
            "clean_room_only": True,
        },
    )


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def _html_to_text(raw: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(raw)
    return " ".join(parser.parts)


def fetch_public_sources(timeout: float = 12.0) -> dict[str, str]:
    result: dict[str, str] = {}
    headers = {"User-Agent": "FUSE-Toka-Public-Harvest/1.0 (+clean-room public-source verification)"}
    for source_id, url in PUBLIC_SOURCES.items():
        request = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")
        result[source_id] = _html_to_text(raw)
    return result


def evaluate_source_text(source_text: Mapping[str, str]) -> dict[str, Any]:
    corpus = " ".join(source_text.values())
    norm = _norm(corpus)
    covered: list[str] = []
    missing: list[str] = []
    for item in load_capabilities():
        if any(_norm(phrase) in norm for phrase in item.evidence_phrases):
            covered.append(item.capability_id)
        else:
            missing.append(item.capability_id)

    source_hashes = {
        source_id: sha256(text.encode("utf-8")).hexdigest()
        for source_id, text in sorted(source_text.items())
    }
    validation = validate_corpus()
    terminal = not missing and len(source_text) == len(PUBLIC_SOURCES)
    body = {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "COMPLETE_VERIFIED_PUBLIC_PARITY" if terminal else "NONTERMINAL_REHARVEST_REQUIRED",
        "terminal": terminal,
        "covered_count": len(covered),
        "expected_count": len(load_capabilities()),
        "covered_capability_ids": covered,
        "missing_capability_ids": missing,
        "source_hashes": source_hashes,
        "source_count": len(source_text),
        "expected_source_count": len(PUBLIC_SOURCES),
        "restricted_transform_count": validation["restricted_transform_count"],
        "cfbe_gene_count": len(compile_cfbe_dna()),
        "hypercube_pattern_count": len(hypercube_pattern_specs()),
        "external_effect_authorized": False,
        "next_action": "WATCH_PUBLIC_SOURCE_DELTA" if terminal else "REPEAT_PUBLIC_READ_AND_REHARVEST_MISSING_SIGNALS",
        "truth_boundary": "Public-source parity proves only clean-room functional mapping; it does not prove or reproduce proprietary Toka implementations or authorise offensive/surveillance effects.",
    }
    body["report_sha256"] = canonical_hash(body)
    return body


def run_live_harvest(timeout: float = 12.0) -> dict[str, Any]:
    return evaluate_source_text(fetch_public_sources(timeout=timeout))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", default="")
    parser.add_argument("--timeout", type=float, default=12.0)
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.live:
        report = run_live_harvest(timeout=args.timeout)
    else:
        report = {
            **validate_corpus(),
            "cfbe_gene_count": len(compile_cfbe_dna()),
            "hypercube_pattern_count": len(hypercube_pattern_specs()),
            "state": "SOURCE_CORPUS_COMPILED",
            "terminal": False,
            "truth_boundary": "Offline compile does not prove live public-source parity.",
        }
        report["report_sha256"] = canonical_hash(report)

    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        from pathlib import Path
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if report.get("state") != "SOURCE_READ_FAILED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
