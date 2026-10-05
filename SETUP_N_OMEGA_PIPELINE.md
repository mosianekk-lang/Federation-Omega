# N-Omega Pipeline Setup Guide

This document outlines all required setup steps to activate the N-Omega Supervisor + AI Engineering Team pipeline.

## What You're Setting Up

Two coordinated workflows that automate issue detection and remediation:

```
N-Omega Supervisor (daily audit)
  → Detects CI failures, governance drift, missing capabilities
  → Opens GitHub issues with `automation/n-omega` label
  
AI Engineering Team Workflow (triggered by issues)
  → Gates issues (verifies label, author, state)
  → Assigns Copilot coding agent
  → Posts work-order comment
  → Copilot authors branch + PR
  
Owner Review
  → Approves/merges PR
```

## Prerequisites

1. **GitHub Copilot coding agent enabled** in Settings > Integrations
2. **Governance approval** for both workflow PRs
3. **Permission to create labels** in this repository

## Step 1: Create Repository Labels

Run the label setup script:

```bash
bash scripts/setup-labels.sh mosianekk-lang/Federation-Omega
```

Or manually create these 8 labels in Settings > Labels:

| Label | Color | Description |
|-------|-------|-------------|
| `automation/n-omega` | `0366d6` | Issue from N-Omega Supervisor audit |
| `ai-team/in-progress` | `ffd700` | AI team is actively working on this issue |
| `ai-team/needs-human` | `ff0000` | AI team escalated - needs human review and decision |
| `ai-team/attempt` | `a0826d` | Marker for AI team attempt counter (internal use) |
| `governance-change` | `8f1493` | Governance policy or authorization change - requires review |
| `audit/superior-logic` | `1d76db` | N-Omega audit finding: Superior Logic domain |
| `audit/evidenceops` | `0e8a16` | N-Omega audit finding: EvidenceOps domain |
| `audit/alpha-omega-commercial` | `c5def5` | N-Omega audit finding: Alpha-Omega Commercial domain |
| `severity/low` | `d4c5f9` | Audit finding: low priority |
| `severity/medium` | `fbca04` | Audit finding: medium priority |
| `severity/high` | `b60205` | Audit finding: high priority |

## Step 2: Verify Copilot Agent Configuration

Check Settings > Integrations:
- [ ] Copilot coding agent is enabled
- [ ] Copilot has `contents: write` permission (for authoring branches)
- [ ] Copilot has `pull_requests: write` permission (for opening PRs)

If Copilot cannot be assigned via API, the workflow will fall back to a manual assignment comment.

## Step 3: Verify Actions Settings

Navigate to Settings > Actions > General:
- [ ] Confirm that workflow-triggered-by-`issues`-event is permitted
- [ ] Note: `github_actions_execution_policy.json` doesn't list `issues` for other workflows either

## Step 4: Merge the Two PRs

### PR #1776: N-Omega Supervisor Workflow

Before merging, **owner must approve the governance change** in `governance/github_airlock_policy.json`. The workflow requires entries in:
- `active_workflow_allowlist`
- `execution_quarantine.keep_active`
- `allowed_events` (`schedule`, `workflow_dispatch`, `workflow_run`)

**Merge:** Once governance is approved.

### PR #1777: AI Engineering Team Workflow & Mandate

Before merging, **owner must approve the governance change** in `governance/github_airlock_policy.json`. The workflow requires entries in:
- `active_workflow_allowlist`
- `execution_quarantine.keep_active`
- `allowed_events` (`issues`, `workflow_dispatch`)

**Merge:** Once governance is approved and labels are created.

## Step 5: Test the Pipeline

### Test N-Omega Supervisor

1. Go to Actions > N-Omega Supervisor
2. Click "Run workflow" (`workflow_dispatch`)
3. Set `scope: audit-ci-tests` (test CI only, not drift)
4. Set `drift_threshold: 100` (suppress drift findings)
5. Run and monitor

Expected: The job completes and produces `n-omega-audit-report.json` artifact.

### Test AI Engineering Team Workflow

1. Manually create a test issue with:
   - Title: `[Test] Sample remediation work`
   - Body: `Test description`
2. Add the `automation/n-omega` label
3. Go to Actions > AI Engineering Team Workflow
4. Click "Run workflow" (`workflow_dispatch`)
5. Enter the test issue number
6. Run and monitor

Expected: The workflow:
- Labels the issue with `ai-team/in-progress`
- Posts a work-order comment
- Attempts to assign Copilot (or posts fallback comment if assignment fails)

### Test Full Loop (Optional)

Once both workflows are stable, trigger Supervisor and watch it auto-create an issue, which triggers the AI Engineering Team workflow.

## Troubleshooting

### Issue: Workflow fails with "not permitted to write to governance/github_airlock_policy.json"

**Fix:** Confirm that the governance change in the PR was approved and merged before running the workflows.

### Issue: "GITHUB_TOKEN" doesn't have permission to assign Copilot

**Fix:** This is expected in some configurations. The workflow falls back to a comment asking for manual assignment. Manually assign `copilot-swe-agent[bot]` to the issue.

### Issue: N-Omega Supervisor finds 65+ "no version key" drifts on first run

**Fix:** This is expected. The initial audit finds gaps in the current codebase. Prioritize governance changes first (via circuit breaker + `ai-team/needs-human`), then fix individual documents.

### Issue: AI Engineering Team Workflow doesn't trigger on labeled issues

**Fix:** Verify that:
1. The issue has the exact label `automation/n-omega`
2. The issue was opened by `github-actions[bot]` or the repo owner
3. Settings > Actions > General allows `issues`-triggered workflows

## Known Limitations

1. **Supervisor workflow list is manual:** The 61 audited workflows are hardcoded. When you add/rename workflows, update the list in `n-omega-supervisor.yml`.

2. **CI failure classification is heuristic:** Pattern matching can catch incidental log text. If you see misclassifications, update the patterns in the `investigate-failures` job.

3. **No auto-merge:** All Copilot-authored PRs require owner review before merge. This is by design.

4. **Circuit breaker escalates to `ai-team/needs-human`:** If Copilot fails twice on an issue, it adds this label and stops. You must manually review and decide.

## Support

- **Workflow logs:** Actions tab in the repository
- **Audit reports:** Artifacts from the Supervisor workflow (30-day retention)
- **Mandate:** `.github/instructions/ai-team-mandate.md`
- **Authority:** Workflows are subordinate to `AGENTS.md`

---

**Pipeline Status:** ✅ Ready to activate  
**Governance Status:** ⏳ Awaiting owner approval  
**Setup Status:** ⏳ Awaiting label creation + Copilot configuration
