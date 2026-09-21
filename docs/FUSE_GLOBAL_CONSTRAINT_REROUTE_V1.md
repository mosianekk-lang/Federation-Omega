# FUSE Global Constraint Re-route v1

This is a companion adapter to the existing OF50/Alpha-Omega/FDOF routing lineage, not a new controller.

## Trigger
Any message indicating task-slot limits, quota exhaustion, rate limiting, concurrency ceilings, storage ceilings, provider overload/capacity or equivalent execution-surface constraints is intercepted as route friction.

The exact ChatGPT task-cap message — "You've reached your limit of 20 active tasks" — maps to ACTIVE_TASK_LIMIT.

## Canonical behavior
1. Preserve mission identity, objective, timing/condition semantics, privacy and effect authority.
2. Map the event to OF50 FrictionClass.RATE_OR_QUOTA_PRESSURE and CycleDecision.CHANGED_ROUTE_REQUIRED.
3. Reuse an existing semantically equivalent scheduled task when available.
4. Consolidate only exact-equivalent duplicates; never pause/delete unrelated work merely to free capacity.
5. Re-route to a qualified FUSE internal scheduler, provider-native scheduler, local scheduler, alternate provider/local runtime or other changed mechanism.
6. On the second same-semantic failure, the same route family is ineligible unless conditions materially changed.
7. If no equivalent live route exists, retain the mission in the durable mission queue and continue capacity/route recovery. Durable queue is not a completion claim.

A platform quota remains a real boundary on that platform; this control prevents the boundary from becoming a mission-level dead end.
