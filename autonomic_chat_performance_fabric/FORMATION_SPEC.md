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
