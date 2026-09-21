from __future__ import annotations

OFFERINGS = (
    {"id":"intelligence-fusion","name":"FUSE Toka Intelligence Fusion","summary":"Fuse structured, unstructured, sensor and open-source data into a governed operational picture.","benchmark":"Toka integrated intelligence cycle + Palantir ontology/data operations"},
    {"id":"isr-edge","name":"FUSE Toka ISR & Edge Awareness","summary":"Ingest authorized IoT, telemetry, imagery and field feeds with geospatial/time correlation and offline-edge continuity.","benchmark":"Toka IoT-age ISR + Esri AllSource disconnected GEOINT"},
    {"id":"investigations","name":"FUSE Toka Investigations","summary":"Case-centric evidence intake, timelines, relationship mapping, collaboration, reporting and chain-of-custody.","benchmark":"Cellebrite case-to-closure + Magnet One"},
    {"id":"osint-risk","name":"FUSE Toka OSINT & Risk Intelligence","summary":"Rights-cleared open-source collection, multilingual enrichment, entity resolution, citations and analyst-directed AI research.","benchmark":"Babel Street agentic OSINT"},
    {"id":"geoint-link","name":"FUSE Toka GEOINT & Link Analysis","summary":"2D/3D map, temporal, relational, movement and knowledge-graph analysis across mission data.","benchmark":"Esri AllSource + Palantir Gotham patterns"},
    {"id":"video-vehicle","name":"FUSE Toka Video & Vehicle Intelligence","summary":"Authorized video ingest, searchable metadata, object/vehicle event correlation, evidence authentication and review workflows.","benchmark":"Toka video/vehicle forensics + Axon Fusus + Magnet media workflows"},
    {"id":"cyber-defense","name":"FUSE Toka Cyber Defense Intelligence","summary":"Network telemetry, asset context, threat intelligence, incident timelines and authorized evidence collection for defensive operations.","benchmark":"Toka network intelligence reframed for authorized defense + modern CTI/DFIR"},
    {"id":"force-protection","name":"FUSE Toka Force & Site Protection","summary":"Unify site sensors, access-control, live alerts, responder locations and operational procedures with explicit authorization controls.","benchmark":"Toka force protection + Motorola/Avigilon + Axon Fusus"},
    {"id":"ai-investigator","name":"FUSE Toka AI Investigator","summary":"Grounded natural-language analysis over evidence with citations, structured plans, human governance and reproducible evals.","benchmark":"Cellebrite Genesis/Guardian Investigate + Palantir AIP + Babel Street Investigator"},
    {"id":"operations-center","name":"FUSE Toka Operations Center","summary":"Real-time common operational picture, alert triage, tasking, incident collaboration and decision audit trail.","benchmark":"Axon Fusus + Palantir Gotham operational handoff"},
    {"id":"interoperability","name":"FUSE Toka Integration Fabric","summary":"Provider-neutral APIs, data contracts, connectors, provenance, feature flags and policy-enforced data exchange.","benchmark":"Toka expanded APIs + Palantir interoperability"},
    {"id":"support-update","name":"FUSE Toka LiveCare & Update Plane","summary":"Outbound-only health heartbeat, privacy-minimized diagnostics, signed release manifests, feature-pack hot reload and rollback.","benchmark":"Palantir Apollo-style continuous delivery + TUF secure-update principles"},
)

RESTRICTED_CAPABILITIES = {
    "unauthorized_system_access":"Not implemented. Use explicitly authorized connectors and isolated lab adapters only.",
    "covert_entry_bypass":"Not implemented. Physical-security workflows are limited to lawful site-protection integrations.",
    "data_exfiltration":"Not implemented as an offensive capability. Export requires authorized evidence/data workflows and audit logging.",
}
