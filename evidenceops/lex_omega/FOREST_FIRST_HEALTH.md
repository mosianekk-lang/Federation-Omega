# Forest-First Health Contract

Forest-First must be understandable without requiring the user to know its implementation details.

## User-visible states

- `FOREST-FIRST: ACTIVE_VERIFIED` — canonical doctrine, runtime source, private state, current-session restore, mandatory legal controls and latest regression evidence are all present.
- `FOREST-FIRST: SYSTEM_READY_SESSION_NOT_RESTORED` — the system exists and has verified source/state, but this chat/session has not proved that the Forest-First controls were restored.
- `FOREST-FIRST: DEGRADED` — some non-critical control or proof is missing. Continue only within verified scope and repair before consequential release.
- `FOREST-FIRST: BLOCKED_HIGH_STAKES` — a critical safeguard such as JFRIE, Legal Route Card, Teach-Back or risk-vs-proof separation is missing during consequential legal work. Do not call a filing release-ready.
- `FOREST-FIRST: NOT_LOADED` — neither canonical doctrine nor executable runtime is evidenced in the current context. Restore before relying on Forest-First.

## Silent preflight, visible failure

For consequential legal/self-representation work, a Forest-First-aware runtime should evaluate health before release. Healthy preflight need not clutter every response. Any `DEGRADED`, `BLOCKED_HIGH_STAKES`, `SYSTEM_READY_SESSION_NOT_RESTORED` or `NOT_LOADED` state must be surfaced when it materially affects the user's ability to rely on the work.

If the user asks `forest-first status`, `is Forest-First working?`, or equivalent, return the state, missing controls and recommended repair path.

## Health is not merits

A healthy Forest-First stack does not prove that the user's case is meritorious, that current law has been verified, that an accusation is true, or that any external provider action occurred. Those remain separate proof gates.
