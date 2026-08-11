# Live Bible v2 Core — Current-Main Promotion Slice

This branch reconstructs the Live Bible v2 core directly from current `main` to eliminate stale-branch deletions and unrelated workflow history from PR #149.

Included:
- capture contract;
- fail-closed event, cursor, deduplication and receipt engine;
- repository reconciliation adapter;
- adversarial tests;
- architecture and truth boundary;
- source-only promotion receipt.

Excluded:
- workflow additions or modifications;
- committed runtime state;
- deployment receipts;
- browser installation;
- provider mutation;
- external communication;
- consequential authority.

Promotion requires GitHub Airlock and repository leak-guard success, current-main mergeability, and post-merge file readback. The larger v2 release package remains preserved in PR #149 until this core slice is admitted and the release-artifact lane is reconciled separately.
