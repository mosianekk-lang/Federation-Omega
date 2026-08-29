# Formation specification

- Owner: Kagiso Kim Mosiane
- Maturity: PROD FOUNDATION / SHADOW ONLY
- Authority: existing repository branch authority; no IAM or runtime expansion
- Cost: zero new recurring cost
- Terminal fruit: tests pass, isolated branch readback matches, main remains unchanged
- Stop conditions: test failure, semantic mismatch, non-zero cost, authority drift,
  live-browser mutation, privacy regression
- Promotion: CFBE champion/challenger proof followed by a separate Formation permit
- CI admission: deterministic work-unit superiority is blocking; wall-clock timing is informational
- Browser canary: configuration present but `enabled: false`; one chat, 15 minutes,
  aggregate-only telemetry, automatic rollback on any stop condition
- Native Edge adapter: implemented and deterministic-testable, but disabled with
  `authorizedEdgeHookPresent: false`; activation remains a separately permitted act
- Route regulator: accepts only `ACTIVE`/`PASSIVE` as input modes and derives
  `HEALTHY`/`DEGRADED`/`OPEN` from aggregate metrics
- Privacy implementation: emitted sentinel and browser-probe telemetry contains no
  message text, per-message identifier/hash, raw DOM, URL, entry name or attribution;
  rollback clears the bounded in-memory state
