# AI Handoff

Run the dedicated tests before generating a scorecard. Supply only a public-safe observation manifest matching the four profile contract hashes. Do not copy connector responses, emails, file IDs, design IDs, continuation tokens, or credentials into source or scorecards.

Verify generated scorecards with the independent `verify` module. Preserve `NOT_EXECUTED`, zero-effect counters, and `stablePromotionAllowed: false`. Provider registration, deployment, and merge require separate current authority and exact provider readback.
