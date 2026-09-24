# FUSE Codex Capability Harvest v1

Status: SOURCE_CANDIDATE / provider-neutral clean-room mechanism harvest.

This harvest imports no OpenAI source code, prompts, weights, credentials, hidden system instructions, or proprietary internals. It generalizes publicly documented product/runtime mechanisms into the existing FUSE architecture.

## Public source set

- https://openai.com/index/introducing-the-codex-app/
- https://openai.com/codex/
- https://developers.openai.com/api/docs/guides/agents
- https://developers.openai.com/api/docs/guides/agents-api/overview
- https://developers.openai.com/api/docs/guides/agents-api/environments/self-hosted
- https://developers.openai.com/api/docs/guides/agents-api/environments/security
- https://developers.openai.com/api/docs/guides/tools-skills
- https://developers.openai.com/api/docs/guides/tools-connectors-mcp
- https://developers.openai.com/api/docs/guides/agents/guardrails-approvals
- https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra
- https://developers.openai.com/blog/mastering-codex-remote-for-engineering
- https://developers.openai.com/cookbook/topic/codex

## Overlap-collapse rule

Codex mechanisms are capability genes, not a new sovereign controller.

- Multi-agent/worktree mechanisms -> FDOF + Work Plane + Forest v2 + GitHub Airlock.
- Durable managed harness/session recovery -> FUSE Sovereign Plane + SOL 6.2 + Genesis + Portable State.
- Skills -> SkillForge + Capability Market + lazy context hydration.
- MCP/programmatic tool calling -> FIO + MCP + action-specific FDOF/SICF authority.
- Hosted/self-hosted/no-sandbox execution -> Execution Power Pools + FUSE Workspace + local carriers.
- Approvals/interruption -> FDOF/SICF + SOL exact-state resume.
- Automations/triggers -> existing Alpha-Omega/FO-GAS/Genesis scheduling path; no second scheduler.
- Review queue/diff review -> DeliveryJournal + ProofOS + Reality Judge + GitHub Airlock.
- Remote/mobile steering -> FUSE Mobile + Workspace + ChatBridge.
- Context compaction -> ChatBridge + Memory Continuum + Portable State + SOL checkpointing.
- Trace/eval improvement -> CFBE + Failure Harvest + RAEFI + ProofOS/Judge.
- Instruction/skill simplification -> SkillForge + Harness Tournament + CFBE.

## Residual capability cohort

The canonical source cohort is HG-CODEX-001..024 in federation/codex_capability_harvest_v1.py.

The corresponding SOL 6.2 runtime upgrade residuals are HG-SOL62-201..224 in services/sol62_client_runtime/runtime_upgrade_genome.py.

Those entries become selectable by the existing SOL autonomous harvester. Registration alone grants no source mutation, provider execution, authority, runtime maturity, or owner-value claim.

## Highest-value residuals

1. Isolated parallel worktree lanes with exact fan-in.
2. Queued steering for already-running work.
3. Speculative side-branch analysis with explicit merge-back.
4. Durable goal subgraphs.
5. Inline diff review receipts.
6. Automation review inbox.
7. Managed harness as an optional provider cell.
8. Automatic context compaction after a resumable checkpoint.
9. Lazy skill-directory hydration.
10. Hosted/self-hosted/no-sandbox carrier compatibility.
11. Outbound-only self-hosted executor reconnect.
12. Restricted environment-key separation.
13. Approval interruption with serialized same-run resume.
14. Cross-client session portability.
15. Remote owner steering/review.
16. Instruction de-bloating by matched-outcome evidence.
17. Trace/eval self-improvement loop.
18. Long-run disconnect recovery with no effect replay.

## Security boundary

The self-hosted executor pattern is adopted only as an outbound carrier pattern. It does not create an inbound remote-control bypass.

Environment-connect credentials and provider/application credentials remain separate. Long-lived provider secrets stay outside agent-generated code and are mediated through existing FUSE credential boundaries.

Remote MCP/tool calls remain action-specific and privacy scoped. Approval bypass is never inferred from prior success or capability presence.

## Proof boundary

PUBLIC_MECHANISM_HARVEST
!= SOURCE_IMPLEMENTED
!= DETERMINISTIC_TEST_PASS
!= MATCHED_BENCHMARK_PASS
!= SOURCE_ADMITTED
!= PROVIDER_BOUND
!= LIVE_RUNTIME
!= OWNER_VALUE_VERIFIED
!= COMPLETE_VERIFIED

Promotion requires current provider/source identity, regression/falsifier evidence, independent ProofOS/Reality Judge where material, and live semantic readback for any runtime claim.
