# ADR — GitHub Surface Omega v2

Status: candidate / source-only

Decision: extend the existing Federation Omega GitHub Control Plane rather than create a new GitHub authority plane.

Rationale: the estate already has strong Airlock, ProofOS, FDOF fencing, CODEOWNERS and security doctrine. The highest-value missing frontier controls are policy ratcheting over workflow/agent/hook privilege, an auditable estate scorecard, least-privilege GitHub agent profiles, explicit OIDC registration, immutable Action references, and provider/supply-chain target contracts.

Rejected alternatives:
- another autonomous GitHub scheduler — conflicts with owner no-schedule policy and duplicates FDOF/FUSE;
- another proof database — duplicates ProofOS/FDOF and increases state cardinality;
- merge queue as current target — unavailable for the current user-owned public repository topology;
- blanket full-estate blocking on day one — would turn historical debt into an outage rather than a controlled ratchet.

Consequences: changed GitHub control surfaces become materially stricter immediately after admission; legacy debt remains visible through the scorecard and must converge through dedicated, exact-current tranches.
