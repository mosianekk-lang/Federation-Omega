# Security boundary

This service is designed for resilience without bypassing provider or platform safeguards.

- Provider policy/refusal is a classified boundary event.
- The service may reroute only to independently authorized providers/local lanes.
- Raw credentials never enter prompts, model inputs, mission state, logs, receipts or repository files.
- Secret-shaped source is blocked from external transmission by default.
- External models never receive source-mutation authority.
- Canonical source changes require separate SLOS/regression/release admission.
