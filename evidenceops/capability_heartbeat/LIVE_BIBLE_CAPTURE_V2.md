# Live Bible Capture Fabric v2

## Purpose

Live Bible Capture Fabric v2 closes the gap between active-turn capture and provider-backed between-turn reconciliation without claiming invisible access to ChatGPT conversations.

## Capture lanes

1. **Active-turn lane** — material user directives and completed work are appended during the authorised response.
2. **Scheduled connector lane** — a ChatGPT automation checks connected Drive, Gmail and GitHub sources using stored cursors and appends only material, deduplicated deltas.
3. **GitHub provider lane** — an hourly GitHub Actions worker records repository commits with provider receipts and persistent cursors.
4. **Recovery lane** — missed provider events can be replayed from the last verified cursor; raw chat text cannot be recovered unless a real source adapter supplies it.

## Controls

- append-only correction and supersession;
- content-fingerprint deduplication;
- source cursors and replay resistance;
- provider receipt requirement for between-turn sources;
- privacy ceilings and P2-local default;
- P0/P1-only automatic Master promotion eligibility;
- conflict quarantine for cursor/content mismatch;
- dead-letter and held-source states;
- no raw content or credentials in event envelopes;
- exact state and receipt hashes;
- zero external-effect authority;
- no invisible future-message claim.

## Current source matrix

| Source | Active turn | Between turn | Proof required | Master promotion |
|---|---:|---:|---|---:|
| ChatGPT active turn | Yes | No | Current authorised turn | No, P2 local |
| Federation GitHub | No | Yes | GitHub commit/provider reference | P1-safe deltas only |
| Google Drive | On demand | Yes through scheduled connector | Drive file/revision readback | No by default |
| Gmail | On demand | Yes through scheduled connector | Message/thread identifier | No by default |
| Local runtime | Yes | Yes when a worker receipt exists | Runtime receipt and target readback | No by default |

## Truth boundary

The system can remain operational between user turns for registered provider sources. It still cannot see future ChatGPT messages unless the user sends them into an authorised turn or a separately proven conversation-source adapter becomes available.
