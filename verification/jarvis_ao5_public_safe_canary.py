"""Public-safe deterministic ΑΩ5 fixture with no private matter facts."""

from __future__ import annotations

from ao_harmonic_v3.jarvis_ao5 import (
    AlphaRecord,
    ConclusionRecord,
    ConfidenceVector,
    ForensicRunRequest,
    GapRecord,
    OmegaRecord,
    PathRecord,
    PreflightInput,
    SourceRecord,
    StreamRecord,
    TheoryRecord,
    TruthState,
)


def build_public_safe_request() -> ForensicRunRequest:
    sources = (
        SourceRecord("SRC-1", "Accommodation process index", "CONTROL", TruthState.VERIFIED, "CONTROL", "private:pointer:1"),
        SourceRecord("SRC-2", "Employer process records", "PRIMARY_RECORD_FAMILY", TruthState.VERIFIED, "EMPLOYER", "private:pointer:2", True, "EMPLOYER"),
        SourceRecord("SRC-3", "Charge/decision record family", "PRIMARY_RECORD_FAMILY", TruthState.VERIFIED, "EMPLOYER", "private:pointer:3", True, "CHARGES"),
        SourceRecord("SRC-4", "Specialist legal-medical control", "CONTROL", TruthState.VERIFIED, "SPECIALIST", "private:pointer:4"),
    )
    alphas = (
        AlphaRecord(
            "A1", "KNOWLEDGE_EVENT", "T0", "SRC-2", "institution",
            "managed reintegration process", "Relevant institutional knowledge predated later discipline.",
            "primary records", TruthState.VERIFIED, "earliest decision-relevant process origin",
            "earlier origins remain searchable", downstream_paths=("P1", "P2", "P3"),
        ),
        AlphaRecord(
            "A2", "PROCESS_STATE", "T1", "SRC-2", "institution",
            "review point contemplated", "The later transition decision is material to classification.",
            "primary records", TruthState.VERIFIED, "process hinge", "review outcome remains missing",
            downstream_paths=("P1", "P2"),
        ),
    )
    omegas = (
        OmegaRecord(
            "O1", "PRIMARY", "Charge-specific correct process classification", "neutral decision-maker",
            "decide on proven facts and correct process", ("instruction", "knowledge", "causation", "process"),
            "charge-specific", ("transition", "attendance", "decision trail"),
            ("G1", "G2", "G3"), ("disclosure",), "fair determination",
            "separate proven misconduct from unresolved capability/accommodation questions",
            ("missing decision trail",), "MATERIAL_GAPS", ("P1", "P2", "P3"), ("P4", "P5"),
        ),
        OmegaRecord(
            "O2", "EVIDENTIARY", "Recover or bound decision-critical records", "record custodian",
            "produce or account", ("record", "custodian", "result"), "records remain missing",
            ("identity", "relevance"), ("search receipt",), ("minimum necessary",),
            "production or bounded unknown", "each record produced, disproved or bounded",
            ("access",), "P0_ACQUISITION", ("P1",), ("P5",),
        ),
    )
    common = "TRANSITION_DECISION_TRAIL"
    paths = (
        PathRecord("P1", "O2", "EVIDENCE", "Acquire P0 records", dependencies=[common, "DATE_RECORDS"], shared_dependencies=[common], required_streams=["ST-01", "ST-03"], legal_viability=.95, factual_strength=.85, evidence_strength=.8, decision_impact=1, remedy_value=.9, timeliness=1, risk=.25, dependency_cost=.5, execution_cost=.4),
        PathRecord("P2", "O1", "MERITS", "Build process-election crosswalk", dependencies=[common, "DECISION_REASONING"], shared_dependencies=[common], required_streams=["ST-07", "ST-11", "ST-12"], legal_viability=.9, factual_strength=.75, evidence_strength=.7, decision_impact=1, remedy_value=.95, timeliness=.95, risk=.35, dependency_cost=.65, execution_cost=.4),
        PathRecord("P3", "O1", "REBUTTAL", "Prepare adverse and neutral hearing-use matrix", dependencies=[common, "DATE_RECORDS"], shared_dependencies=[common], required_streams=["ST-14", "ST-22", "ST-23"], legal_viability=.9, factual_strength=.78, evidence_strength=.72, decision_impact=.95, remedy_value=.9, timeliness=1, risk=.35, dependency_cost=.6, execution_cost=.45),
        PathRecord("P4", "O1", "DISCOVERY", "Seek expert clarification if material", dependencies=["EXPERT"], required_streams=["ST-15"], legal_viability=.75, factual_strength=.65, evidence_strength=.68, decision_impact=.72, remedy_value=.65, timeliness=.65, risk=.45, dependency_cost=.75, execution_cost=.7),
        PathRecord("P5", "O2", "GOVERNANCE", "Frame bounded governance request", dependencies=["DECISION_REASONING"], required_streams=["ST-25"], legal_viability=.7, factual_strength=.7, evidence_strength=.6, decision_impact=.65, remedy_value=.65, timeliness=.6, risk=.55, dependency_cost=.75, execution_cost=.65),
        PathRecord("P6", "O1", "SETTLEMENT", "Preserve practical resolution route", dependencies=["OWNER_DECISION"], required_streams=["ST-27"], legal_viability=.6, factual_strength=.55, evidence_strength=.5, decision_impact=.55, remedy_value=.7, timeliness=.45, risk=.65, dependency_cost=.6, execution_cost=.55, owner_gate=True),
        PathRecord("P7", "O1", "CONTINGENCY", "Hold low-evidence theory", dependencies=["UNPROVEN_MOTIVE"], required_streams=["ST-16"], legal_viability=.2, factual_strength=.2, evidence_strength=.15, decision_impact=.2, remedy_value=.2, timeliness=.2, risk=.9, dependency_cost=.9, execution_cost=.8),
    )
    streams = (
        StreamRecord("ST-01", "SOURCE", ("SRC-1",), ("F1",), (), "PRIMARY", "HIGH", (), True),
        StreamRecord("ST-03", "SOURCE-RECOVERY", ("SRC-1",), ("F2",), (), "P0", "HIGH", ("negative search is not non-existence",), True),
        StreamRecord("ST-07", "PROPOSITIONS", ("SRC-1",), ("F3",), ("mixed classification possible",), "CROSSWALK", "MODERATE", (), True),
        StreamRecord("ST-11", "LAW", ("SRC-4",), ("F4",), (), "AUTHORITY", "MODERATE", ("current authority required before external reliance",), True),
        StreamRecord("ST-12", "POLICY", ("SRC-1",), ("F5",), (), "POLICY", "HIGH", (), True),
        StreamRecord("ST-14", "MERITS", ("SRC-3",), ("F6",), (), "CHARGE", "MODERATE", (), True),
        StreamRecord("ST-15", "CAUSATION", ("SRC-1",), (), ("causal link remains charge-specific",), "CAUSATION", "LOW", (), True),
        StreamRecord("ST-22", "RED-TEAM", ("SRC-3",), (), ("ordinary misconduct may be independently proved",), "OPPOSITION", "HIGH", (), True),
        StreamRecord("ST-23", "NEUTRAL", ("SRC-1", "SRC-3"), (), ("both cases may partly succeed",), "NEUTRAL", "MODERATE", (), True),
        StreamRecord("ST-25", "GOVERNANCE", ("SRC-1",), (), (), "GOV", "MODERATE", (), False),
        StreamRecord("ST-27", "OUTCOME", ("SRC-1",), (), (), "VALUE", "MODERATE", (), False),
    )
    gaps = (
        GapRecord("G1", "Review and transition decision with reasons", "management/HR", "records", "targeted search", 1, 1, .95, .45),
        GapRecord("G2", "Exact instruction and acknowledgement", "management", "records", "targeted search", .95, 1, .95, .4),
        GapRecord("G3", "Date-specific attendance/work records", "operations/HR", "systems", "multi-source retrieval", .95, 1, 1, .55),
        GapRecord("G4", "Decision and charge-framing reasoning", "HR/legal", "records", "targeted search", .92, .95, .95, .6),
    )
    confidence = ConfidenceVector("HIGH", "MIXED", "HIGH", "MODERATE", "MODERATE", "LOW_TO_MODERATE", "MODERATE", "MODERATE", "MODERATE", "MODERATE")
    theory = TheoryRecord(
        "T1",
        "The proof-safe position is an event-specific process-classification inquiry, not an automatic entitlement or blanket defence.",
        ("F1", "F2", "F3"),
        ("non-approval evidence", "ordinary misconduct alternative"),
        "The institution properly separated health/capability questions from clear, independently provable misconduct.",
        ("complete reasoned transition trail", "date-specific records", "proper route-selection record"),
        confidence,
    )
    conclusions = (
        ConclusionRecord("C1", "Relevant institutional knowledge predated later discipline.", "T1", "KNOWLEDGE", ("F1",), "knowledge existed", ("SRC-2",), TruthState.VERIFIED),
        ConclusionRecord("C2", "The transition and decision trail remains decision-critical.", "T1", "PROCESS", ("F2",), "missing record", ("SRC-1",), TruthState.MISSING_PRIMARY_RECORD),
        ConclusionRecord("C3", "The evidence supports a charge-specific inquiry but does not exclude independently proved misconduct.", "T1", "CLASSIFICATION", ("F3", "F6"), "mixed and falsifiable theory", ("SRC-1", "SRC-3", "SRC-4"), TruthState.INFERENCE),
    )
    return ForensicRunRequest(
        "JARVIS-AO5-PUBLIC-SAFE-CANARY-001",
        "SYNTHETIC-EMPLOYMENT-PROJECT",
        "employment-accommodation-canary",
        "Run a bounded replayable Alpha-to-Omega decision programme.",
        sources,
        alphas,
        omegas,
        paths,
        streams,
        gaps,
        theory,
        conclusions,
        ("non-approval evidence", "ordinary misconduct remains possible"),
        "A neutral decision-maker may accept parts of both cases and require a charge-specific classification.",
        ("WORLD-A mixed process required", "WORLD-B ordinary misconduct applied", "WORLD-C mixed findings by date/charge"),
        PreflightInput(file_count=6, page_count=42, annexure_count=6, format_count=3, nested_object_count=3, domain_count=3, legal_research_load=2, tool_complexity=3, path_count=7, stream_count=11, context_risk=2, failure_risk=2),
        "Synthetic public-safe fixture; no private matter facts; no external effect.",
        False,
        False,
        "LOCAL_TEST_RECEIPT",
    )
