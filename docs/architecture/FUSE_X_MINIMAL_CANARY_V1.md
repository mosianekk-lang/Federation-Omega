# FUSE-X Minimum-Cost Live Canary v1

The first live provider court is intentionally tiny: one authenticated-user read and one Home-timeline Post read, no expansions and no write effects. At the 2026-09-19 X documentation pricing epoch, the resource estimate is $0.010 + $0.005 = $0.015, capped by policy at $0.020. Current Developer Console rates override this static estimate if they change.

The proof receipt contains only presence/count/hash evidence, not post text. This can close transport/read-only/Home-timeline canary predicates only; it cannot promote recovery, continuous harvesting, value or overall finality.
