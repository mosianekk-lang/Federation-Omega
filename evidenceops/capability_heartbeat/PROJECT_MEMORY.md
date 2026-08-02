# Project Memory

The repository already contained independent capability, lane, scheduler and runtime controls. This build extends the existing sovereign control plane with transactional surface, chat, outbox, remediation and connector-seed state.

Core invariants:

- current source bytes determine the heartbeat fingerprint;
- one primary route per requirement;
- no more than one effectful path;
- external effects require a separate current Formation permit;
- safety cannot regress for a quality improvement;
- missing or runtime-dependent capabilities remain held;
- GitHub schedule artifacts are not direct chat injection or execution proof.
- only a supported turn/event adapter can mark a chat visible;
- unsupported surfaces continuously produce ranked remediation cases;
- Kimmie Seeds contain no secrets or chat content and require PRE/POST receipts;
- a direct connector call outside a participating adapter cannot be intercepted;
- source complete, tested, deployed and live-proven are separate completion states.
