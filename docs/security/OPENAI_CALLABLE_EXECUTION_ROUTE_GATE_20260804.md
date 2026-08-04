# OpenAI Callable Execution Route Gate — 4 August 2026

Status: `BUILT / REVIEW_PENDING`

## Defect corrected

Three bounded OpenAI rotation probes were written to the Sovereign Federation CloudOps Command Center through the Google Sheets API. The rows were read back as `READY`, but no processor execution followed.

Google Apps Script documentation states that script executions and API requests do not cause simple or installable edit/change triggers to run. Therefore an API-written command row is queue state only. It is not a callable execution route and cannot prove provider action.

## Permanent rule

A credential-rotation closure receipt must identify a provider-callable execution route for each destination. Accepted route classes are:

- direct Google Cloud API authority;
- Apps Script Execution API authority;
- an authenticated deployed Apps Script web app;
- a verified time-driven Apps Script trigger with a current execution receipt;
- a private provider operator with action-specific readback.

The following are never execution proof:

- a Google Sheets API write that expects an edit or change trigger;
- a queue row without processor timestamps and semantic output;
- a source or deployment pack without an installed endpoint;
- a historical trigger identifier without current execution evidence;
- a generic runtime health or status payload returned for a different requested action.

## Machine gate

`ops/openai_callable_route_gate.py` validates the existing redacted closure receipt and additionally requires, for each destination:

- an allowed route type;
- `depends_on_api_write_trigger=false`;
- provider-callable readback;
- a provider proof reference;
- an execution timestamp;
- confirmation that the result is not generic runtime health.

The gate does not accept or print credential values.

## Current matter state

The staged commands remain useful evidence but are not retried or duplicated:

- `OPENAI-ROTATION-LIST-SECRETS-20260804-001`
- `OPENAI-ROTATION-READ-LIVE-THREAD-20260804-001`
- `OPENAI-ROTATION-RUN-QUEUE-20260804-001`

No destination binding, canary, old-key revocation or old-key rejection is proven by those rows.
