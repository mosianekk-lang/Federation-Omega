# Do not expose internal control planes

FUSE Mobile Gateway must never provide a generic pass-through to `federation-omega-operator /execute`, Cloud Run admin APIs, Secret Manager, IAM mutation APIs, or provider credential-management APIs. Mobile-visible operations are capability-scoped contracts only.
