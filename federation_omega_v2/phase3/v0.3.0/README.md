# Federation Omega v2.0 Core — Phase 3

Phase 3 introduces a read-only real-matter adapter for the registered TUT 21 August disciplinary node.

The adapter imports only source identities and control metadata. It does not copy raw P2 evidence, message bodies, attachments, medical content, legal conclusions or external-action authority into the federation graph.

It executes ten A1 internal stages:

1. SOURCE_LOCK
2. CASE_WALL
3. PROVENANCE_IMPORT
4. CHRONOLOGY_CONTROL
5. CHARGE_ELEMENT_MAP
6. CONTRADICTION_CONTROL
7. GAP_SCHEDULE
8. READINESS_COMPARISON
9. OWNER_BRIEF
10. RESTART_VERIFY

All outputs are internal, restart-safe and proof-carrying. Sending, filing, settlement action, evidence deletion and other consequential effects remain disabled.

## Source dependency

This Phase 3 overlay extends the canonical Phase 2 event-store and system-graph core under `federation_omega_v2/phase2/v0.2.0/source`. The governed binary release is stored outside the source repository in the user Library.
